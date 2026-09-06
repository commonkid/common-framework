#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cc_statusline.py — iStat-style statusline for Claude Code.

Renders a 3-line panel (plus an optional deploy row):

  <dir> (<branch>)                     │ ▂▅█▃▁▂▃▅▇█▅▃▂▄▆▇█▆  Σ 12.9M │          session ctx
  plan Max20        Opus 5 (1M) · High │ ━━━━━━━──── 5h · 41% left cache 95% │ ███░░░░░░░░░░  18%
                                                                              session $1.84  t 1h 23m 05s

The third row carries no frame and no separator: it is a bare price line
aligned under the right column. "session" is the cost of this chat, "t" is
how long this chat has been running (hours, minutes, seconds, wall clock).

The middle panel is one chart: total token spend of this session per minute
(input + cache + output together), with the running total and the current
rate underneath. "agents" mode shows the per-subagent cost split instead.
The left panel shows the model's reasoning effort (from Claude Code settings)
or, in API-key mode, how many tokens are left.

Data sources
  * stdin JSON        — Claude Code statusline protocol (model, cwd, cost, session)
  * transcript JSONL  — per-agent cost split, context window usage (incremental parse)
  * ~/.claude/projects/**/*.jsonl — rolling 5h / 7d spend (background refresh)
  * ~/.claude/statusline-tree/<repo>.json — per-branch cost ledger of the repo
  * Anthropic Admin API — optional, org/key cost (background refresh)
  * Custom router / gateway — optional, key balance (background refresh)

Modes
  (no args)   render one frame from stdin JSON   <- what Claude Code calls
  --refresh   background job: update the slow cache, print nothing
              (--root <repo> also refreshes that repo's tree-cost ledger)
  --demo      render with fake data, for eyeballing the layout
  --doctor    print what it can and cannot see, for debugging

Config: ~/.claude/statusline.json  (see --doctor for the effective config)
No third-party dependencies.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import providers as PROV
except Exception:            # keep the prompt alive even if the module is missing
    PROV = None

HOME = Path.home()
CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (HOME / ".claude"))
CONFIG_PATH = CLAUDE_DIR / "statusline.json"
CACHE_PATH = CLAUDE_DIR / "statusline-cache.json"
LOCK_PATH = CLAUDE_DIR / "statusline-refresh.lock"
STATE_DIR = CLAUDE_DIR / "statusline-state"
TREE_DIR = CLAUDE_DIR / "statusline-tree"

# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #

DEFAULT_CONFIG = {
    # Which plan you are on. Free text, shown next to the billing mode.
    "plan": "",
    # Subscription limits for the thin limit line: USD of "equivalent" spend
    # computed locally from the transcripts over the last `session_hours` and
    # over 7 days (Anthropic does not expose the real numbers — calibrate
    # against /usage). Set one to 0 to ignore it.
    "limits": {"session_usd": 25.0, "session_hours": 5, "week_usd": 250.0},
    # API-key mode shows TOKENS LEFT instead of the 5h / week bars. The
    # remainder comes from the first source that is configured:
    #   key_budget_tokens  — a token budget; used = tokens spent in the last
    #                        `limits.session_hours` across all projects
    #   router balance     — credits / usd_per_token (see "router" below)
    #   key_budget_usd     — USD budget minus spent (router / admin / local scan)
    # usd_per_token is this session's real blended rate when it has cost
    # something, otherwise the model's input price from "pricing".
    # Whose limits the thin line shows: "auto" or one of
    # anthropic, codex, gemini, copilot, openrouter, deepseek, moonshot,
    # kimi-code, zai, minimax (see providers.py).
    "provider": "auto",
    "key_budget_tokens": 0,
    "key_budget_usd": 0.0,
    # Context window size. 0 = autodetect (200k, or 1M if usage exceeds 200k).
    "context_limit": 0,
    # Seconds between background refreshes of the slow sources.
    "refresh_seconds": 90,
    # Terminal width. 0 = autodetect, clamped to [40, 240].
    "width": 0,
    # Columns Claude Code keeps for itself; the panel is drawn `margin`
    # narrower than the terminal so nothing is cut off on the right.
    "margin": 4,
    # "dark" | "light" | "mono"
    "theme": "dark",
    # Middle panel: "tokens" (total token spend per minute) or "agents" (cost sparkline)
    "center": "tokens",
    # Deploy pipeline row, fed by pipeline.py via <repo>/.pipeline/run.json
    "pipeline": {"enabled": True, "show_finished_minutes": 10, "stale_hours": 6},
    # Max agents to draw in the middle panel.
    "max_agents": 8,
    # Tree cost: what every session of this repository spent on the branch
    # that is checked out right now. Off -> the price row shows session only.
    "tree": {"enabled": True},
    # Optional: Anthropic Admin API (org-level cost). Needs an sk-ant-admin key.
    "admin": {
        "enabled": False,
        "key_env": "ANTHROPIC_ADMIN_KEY",
        "window_days": 7,
        "url": "https://api.anthropic.com/v1/organizations/cost_report",
    },
    # Optional: your own router / gateway balance endpoint.
    "router": {
        "enabled": False,
        "url": "",
        "token_env": "ROUTER_API_KEY",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        # dotted paths into the JSON response; first one that resolves wins
        "balance_paths": ["balance", "data.balance", "credits", "data.credits"],
        "spent_paths": ["spent", "data.spent", "used", "data.used"],
    },
    # Per-MTok prices used when the transcript has no cost field.
    # Unknown families fall back to "sonnet"; fable / mythos use the opus row
    # unless you add their own.
    "pricing": {
        "opus":   {"in": 15.0, "out": 75.0, "cache_write": 18.75, "cache_read": 1.50},
        "sonnet": {"in": 3.0,  "out": 15.0, "cache_write": 3.75,  "cache_read": 0.30},
        "haiku":  {"in": 0.80, "out": 4.0,  "cache_write": 1.00,  "cache_read": 0.08},
    },
}


def deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config():
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    return deep_merge(DEFAULT_CONFIG, raw)


# --------------------------------------------------------------------------- #
# colors
# --------------------------------------------------------------------------- #

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class Theme:
    def __init__(self, name):
        self.mono = name == "mono" or os.environ.get("NO_COLOR")
        light = name == "light"
        # r,g,b
        self.frame = (92, 99, 112) if not light else (170, 176, 186)
        self.label = (122, 130, 144)
        self.value = (232, 236, 242) if not light else (32, 36, 44)
        self.accent = (96, 165, 250)     # blue   — model / branch
        self.accent2 = (167, 139, 250)   # violet — agents
        self.good = (74, 222, 128)       # green
        self.warn = (250, 204, 21)       # yellow
        self.bad = (248, 113, 113)       # red
        self.dim = (78, 85, 97)
        self.money = (94, 234, 212)      # teal

    def c(self, rgb, s):
        if self.mono or not s:
            return s
        r, g, b = rgb
        return "\x1b[38;2;%d;%d;%dm%s\x1b[0m" % (r, g, b, s)

    def by_load(self, frac):
        if frac >= 0.85:
            return self.bad
        if frac >= 0.6:
            return self.warn
        return self.good


# --------------------------------------------------------------------------- #
# width-aware string helpers
# --------------------------------------------------------------------------- #

def vlen(s):
    """Display width: strips ANSI, counts wide/fullwidth glyphs (emoji) as 2."""
    import unicodedata
    s = ANSI_RE.sub("", s)
    w = 0
    for ch in s:
        if unicodedata.combining(ch) or ch == "️":
            continue
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def vclip(s, width):
    """Truncate to `width` visible chars, keeping ANSI sequences intact."""
    if vlen(s) <= width:
        return s
    out, seen, i = [], 0, 0
    while i < len(s) and seen < width:
        m = ANSI_RE.match(s, i)
        if m:
            out.append(m.group(0))
            i = m.end()
            continue
        out.append(s[i])
        seen += 1
        i += 1
    out.append("\x1b[0m")
    return "".join(out)


def pad(s, width, align="<"):
    d = width - vlen(s)
    if d <= 0:
        return vclip(s, width)
    if align == ">":
        return " " * d + s
    if align == "^":
        left = d // 2
        return " " * left + s + " " * (d - left)
    return s + " " * d


def fit(left, right, width):
    """Left text, right text, single line of exactly `width` visible chars."""
    gap = width - vlen(left) - vlen(right)
    if gap < 1:
        left = vclip(left, max(0, width - vlen(right) - 1))
        gap = width - vlen(left) - vlen(right)
    return left + " " * max(gap, 0) + right


# --------------------------------------------------------------------------- #
# bars & sparklines
# --------------------------------------------------------------------------- #

FULL, EMPTY = "█", "░"
SPARK = "▁▂▃▄▅▆▇█"

# A line made only of spaces up to its text loses that indent: whoever prints
# the statusline strips leading whitespace, and the row snaps to column 0. A
# zero-width space is not whitespace, takes no cell, and stops the trim, so the
# padding behind it survives and the row stays under the column it belongs to.
GUARD = "\u200b"


def bar(theme, frac, width):
    frac = max(0.0, min(1.0, frac))
    n = int(round(frac * width))
    n = min(width, max(0, n))
    filled = theme.c(theme.by_load(frac), FULL * n)
    rest = theme.c(theme.dim, EMPTY * (width - n))
    return filled + rest


def spark(theme, values, rgb):
    if not values:
        return ""
    top = max(values) or 1.0
    out = []
    for v in values:
        idx = int(round((v / top) * (len(SPARK) - 1)))
        out.append(SPARK[max(0, min(len(SPARK) - 1, idx))])
    return theme.c(rgb, "".join(out))


def inv(theme, rgb, ch):
    """Reverse video: the glyph's pixels take the terminal's own background,
    the rest takes `rgb`. Lets a downward bar use the lower-block glyphs
    without assuming what colour the terminal background is."""
    if theme.mono:
        return ch
    return "\x1b[7m\x1b[38;2;%d;%d;%dm%s\x1b[27m\x1b[0m" % (rgb[0], rgb[1], rgb[2], ch)


def _resample(seq, width):
    """Average `seq` into exactly `width` columns."""
    if not seq:
        return [0.0] * width
    if len(seq) == width:
        return [float(v) for v in seq]
    out = []
    for i in range(width):
        a, b = i * len(seq) / width, (i + 1) * len(seq) / width
        lo, hi = int(a), max(int(a) + 1, int(b + 0.999))
        chunk = seq[lo:min(hi, len(seq))] or [seq[min(lo, len(seq) - 1)]]
        out.append(float(sum(chunk)) / len(chunk))
    return out


def mini_total(theme, values, width):
    """Two stacked rows (16 sub-levels) of one series: total tokens per
    column. Returns (upper_row, lower_row)."""
    v = _resample(values, width)
    top = max(v) or 1.0
    hi, lo = [], []
    for x in range(width):
        n = max(0, min(16, int(round(v[x] / top * 16))))
        lo.append(theme.c(theme.accent, SPARK[min(n, 8) - 1]) if n else " ")
        m = n - 8
        hi.append(theme.c(theme.accent, SPARK[m - 1]) if m > 0 else " ")
    return "".join(hi), "".join(lo)


def money(v):
    if v is None:
        return "—"
    if v >= 100:
        return "$%.0f" % v
    if v >= 10:
        return "$%.1f" % v
    return "$%.2f" % v


def money_short(v):
    if v is None:
        return "—"
    if v >= 10:
        return "%.0f" % v
    if v >= 1:
        return "%.1f" % v
    return ("%.2f" % v).lstrip("0") or "0"


def pct(frac):
    """Always 4 visible chars: ' 41%', '126%', '999%'."""
    return "%3d%%" % min(999, max(0, int(round((frac or 0) * 100))))


def toks(n):
    if n is None:
        return "—"
    if n >= 1_000_000:
        return "%.1fM" % (n / 1_000_000)
    if n >= 1000:
        return "%.0fk" % (n / 1000)
    return str(int(n))


# --------------------------------------------------------------------------- #
# pricing
# --------------------------------------------------------------------------- #

def price_table(cfg, model_id):
    m = (model_id or "").lower()
    for key in ("opus", "sonnet", "haiku", "fable", "mythos"):
        if key in m:
            tbl = cfg["pricing"].get(key)
            if tbl is None and key in ("fable", "mythos"):
                tbl = cfg["pricing"].get("opus")
            if tbl:
                return tbl
    return cfg["pricing"]["sonnet"]


def usage_cost(cfg, model_id, u):
    if not isinstance(u, dict):
        return 0.0
    p = price_table(cfg, model_id)
    i = u.get("input_tokens", 0) or 0
    o = u.get("output_tokens", 0) or 0
    cw = u.get("cache_creation_input_tokens", 0) or 0
    cr = u.get("cache_read_input_tokens", 0) or 0
    return (i * p["in"] + o * p["out"] + cw * p["cache_write"] + cr * p["cache_read"]) / 1e6


def usage_context(u):
    if not isinstance(u, dict):
        return 0
    return (
        (u.get("input_tokens", 0) or 0)
        + (u.get("cache_read_input_tokens", 0) or 0)
        + (u.get("cache_creation_input_tokens", 0) or 0)
        + (u.get("output_tokens", 0) or 0)
    )


# --------------------------------------------------------------------------- #
# transcript parsing (incremental)
# --------------------------------------------------------------------------- #

def _short_label(text, n=9):
    if not text:
        return "agent"
    text = re.sub(r"[^a-zA-Z0-9а-яА-Я _\-/]", "", str(text)).strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return "agent"
    text = text.lower()
    if len(text) <= n:
        return text
    words = [w for w in text.split(" ") if w]
    out = words[0][:n] if words else text[:n]
    if len(out) < 2 and len(words) > 1:
        out = (words[0] + "-" + words[1])[:n]
    return out


def blank_state():
    return {
        "offset": 0,
        "sig": "",
        "main_cost": 0.0,
        "chains": {},          # root_uuid -> {label, cost, order}
        "parents": {},         # sidechain uuid -> parent uuid
        "roots": {},           # sidechain uuid -> root uuid (memo)
        "tasks": [],           # pending Task labels, in order of appearance
        "task_texts": {},      # first 60 chars of prompt -> label
        "ctx_tokens": 0,
        "ctx_model": "",
        "n_msgs": 0,
        "tok_in": 0,
        "tok_out": 0,
        "tok_cache": 0,         # cache-read share of tok_in
        "n_tools": 0,           # tool events seen, ever (for phase-signal age)
        "fw_phase": "",         # last Common Framework phase signal
        "fw_at": 0,             # n_tools when that signal was seen
        "tools": [],            # [name, is_error] for the last N tool events
        "deploy_seen": 0,       # unix ts of the first deploy-ish command
        "buckets": {},          # "<unix minute>" -> [input_tokens, output_tokens]
    }


def state_path(session_id):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")[:80]
    return STATE_DIR / (safe + ".json")


def anchor_path(session_id):
    """Per-session file remembering the last `total_duration_ms` seen and when
    (see session_seconds); lives beside the transcript state."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "default")
    return STATE_DIR / (safe + ".clock.json")


def load_state(session_id, sig):
    p = state_path(session_id)
    try:
        st = json.loads(p.read_text(encoding="utf-8"))
        if st.get("sig") == sig:
            return st
    except Exception:
        pass
    return blank_state()


BUCKET_KEEP = 300          # minutes of token history kept per session
TOOLS_KEEP = 80            # tool events kept, for the work-phase heuristic


def save_state(session_id, st):
    try:
        b = st.get("buckets") or {}
        if len(b) > BUCKET_KEEP:
            for k in sorted(b, key=int)[:-BUCKET_KEEP]:
                b.pop(k, None)
        if len(st.get("tools") or []) > TOOLS_KEEP:
            st["tools"] = st["tools"][-TOOLS_KEEP:]
        state_path(session_id).write_text(json.dumps(st), encoding="utf-8")
    except Exception:
        pass


def chain_root(st, uuid):
    memo = st["roots"]
    if uuid in memo:
        return memo[uuid]
    path, cur = [], uuid
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        path.append(cur)
        if cur in memo:
            break
        nxt = st["parents"].get(cur)
        if not nxt or nxt not in st["parents"]:
            # nxt is either absent or a non-sidechain parent -> cur is the root
            break
        cur = nxt
    root = memo.get(cur, cur)
    for u in path:
        memo[u] = root
    return root


def parse_transcript(cfg, transcript_path, session_id):
    """Incrementally parse the session transcript. Returns a summary dict."""
    st = blank_state()
    if not transcript_path:
        return summarize(st)
    p = Path(transcript_path)
    try:
        size = p.stat().st_size
    except Exception:
        return summarize(st)

    sig = "%s:%d" % (p.name, 0)
    st = load_state(session_id, sig)
    if st["offset"] > size:      # file rotated / truncated
        st = blank_state()
    st["sig"] = sig

    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(st["offset"])
            for line in fh:
                if not line.endswith("\n"):
                    break                      # partial last line; re-read next time
                st["offset"] += len(line.encode("utf-8", "replace"))
                line = line.strip()
                if not line or line[0] != "{":
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                ingest(cfg, st, e)
    except Exception:
        pass

    save_state(session_id, st)
    return summarize(st)


def ingest(cfg, st, e):
    et = e.get("type")
    uuid = e.get("uuid")
    side = bool(e.get("isSidechain"))
    msg = e.get("message") or {}

    if side and uuid:
        st["parents"][uuid] = e.get("parentUuid")

    # --- tool events, for the work-phase heuristic ---------------------------
    if et == "assistant":
        content = msg.get("content")
        if isinstance(content, list):
            for blk in content:
                if not (isinstance(blk, dict) and blk.get("type") == "tool_use"):
                    continue
                name = blk.get("name") or "?"
                inp = blk.get("input") or {}
                st["tools"].append([name, 0])
                st["n_tools"] = st.get("n_tools", 0) + 1
                if name == "Bash":
                    cmd = (inp.get("command") or "")[:400]
                    if TEST_RE.search(cmd):
                        st["tools"].append(["test", 0])
                    if not st.get("deploy_seen") and DEPLOY_RE.search(cmd):
                        st["deploy_seen"] = parse_ts(e.get("timestamp")) or time.time()
                ph = framework_phase(name, inp)
                if ph:
                    st["fw_phase"] = ph
                    st["fw_at"] = st["n_tools"]
    if et == "user":
        c = msg.get("content")
        if isinstance(c, list):
            for blk in c:
                if isinstance(blk, dict) and blk.get("type") == "tool_result":
                    st["tools"].append(["result", 1 if blk.get("is_error") else 0])

    # --- collect Task launches so sidechains can be named -------------------
    if et == "assistant" and not side:
        content = msg.get("content")
        if isinstance(content, list):
            for blk in content:
                if isinstance(blk, dict) and blk.get("type") == "tool_use" and blk.get("name") == "Task":
                    inp = blk.get("input") or {}
                    label = _short_label(inp.get("description") or inp.get("subagent_type"))
                    st["tasks"].append(label)
                    prompt = (inp.get("prompt") or "")[:60]
                    if prompt:
                        st["task_texts"][prompt] = label

    # --- name a new sidechain root ------------------------------------------
    if side and et == "user" and not st["parents"].get(uuid):
        text = ""
        c = msg.get("content")
        if isinstance(c, str):
            text = c
        elif isinstance(c, list):
            for blk in c:
                if isinstance(blk, dict) and blk.get("type") == "text":
                    text = blk.get("text") or ""
                    break
        label = None
        key = text[:60]
        if key and key in st["task_texts"]:
            label = st["task_texts"].pop(key)
            if label in st["tasks"]:
                st["tasks"].remove(label)
        if label is None and st["tasks"]:
            label = st["tasks"].pop(0)
        if label is None:
            label = "agent%d" % (len(st["chains"]) + 1)
        taken = {c["label"] for c in st["chains"].values()}
        if label in taken:
            k = 2
            while "%s%d" % (label, k) in taken:
                k += 1
            label = "%s%d" % (label, k)
        st["chains"][uuid] = {"label": label, "cost": 0.0, "tin": 0, "tout": 0,
                              "order": len(st["chains"])}
        st["roots"][uuid] = uuid

    # --- cost + context ------------------------------------------------------
    if et != "assistant":
        return
    u = msg.get("usage")
    if not u:
        return
    st["n_msgs"] += 1
    model_id = msg.get("model") or ""
    c = e.get("costUSD")
    if not isinstance(c, (int, float)):
        c = usage_cost(cfg, model_id, u)

    inp = ((u.get("input_tokens", 0) or 0)
           + (u.get("cache_read_input_tokens", 0) or 0)
           + (u.get("cache_creation_input_tokens", 0) or 0))
    outp = u.get("output_tokens", 0) or 0
    st["tok_in"] += inp
    st["tok_out"] += outp
    st["tok_cache"] = st.get("tok_cache", 0) + (u.get("cache_read_input_tokens", 0) or 0)
    t = parse_ts(e.get("timestamp"))
    if t:
        key = str(int(t // 60))
        prev = st["buckets"].get(key) or [0, 0]
        st["buckets"][key] = [prev[0] + inp, prev[1] + outp]

    if side:
        root = chain_root(st, uuid) if uuid else None
        entry = st["chains"].get(root)
        if entry is None:
            entry = {"label": "agent%d" % (len(st["chains"]) + 1), "cost": 0.0,
                     "tin": 0, "tout": 0, "order": len(st["chains"])}
            st["chains"][root or ("orphan%d" % len(st["chains"]))] = entry
        entry["cost"] += c
        entry["tin"] = entry.get("tin", 0) + inp
        entry["tout"] = entry.get("tout", 0) + outp
    else:
        st["main_cost"] += c
        ctx = usage_context(u)
        if ctx:
            st["ctx_tokens"] = ctx
            st["ctx_model"] = model_id


DEPLOY_RE = re.compile(
    r"(pipeline(\.py)?\s+(init|stage|at|gate|done)|make\s+(deploy|ship|prod|release|all)\b"
    r"|\./deploy|docker\s+push|kubectl\s+(apply|rollout)|helm\s+upgrade"
    r"|fly\s+deploy|vercel\s+(deploy|--prod)|netlify\s+deploy|serverless\s+deploy"
    r"|eb\s+deploy|gcloud\s+run\s+deploy|ansible-playbook)", re.I)

# Common Framework work phases: Architect -> Code -> QA -> Debug. The root
# agent announces the phase through the skill / subagent it invokes; when
# nothing was announced (plain Claude Code session) a tool heuristic decides.
WORK_PHASES = ["architect", "code", "qa", "debug"]
FRAMEWORK_SIGNALS = (
    ("mode-architect", "architect"), ("devplan", "architect"), ("develop", "architect"),
    ("ultraprompt", "architect"), ("master-prompt", "architect"),
    ("mode-code", "code"), ("dev-base", "code"),
    ("mode-qa", "qa"), ("version-test", "qa"),
    ("mode-debug", "debug"),
)
FW_SIGNAL_TTL = 60         # tool events after which an announced phase goes stale
TEST_RE = re.compile(
    r"\b(pytest|python3?\s+-m\s+(pytest|unittest)|npm\s+test|pnpm\s+test|yarn\s+test"
    r"|go\s+test|cargo\s+test|mvn\s+test|gradle\s+test|jest|vitest|make\s+test)\b", re.I)

DEPLOY_PHASES = ["pre", "tests", "push", "stand", "ready", "QA",
                 "prod", "sec", "seo", "clean"]
# Display names. "stand" is the test stand, kept distinct from "tests" (the
# local autotest run) so the two never read as the same step.
PHASE_LABEL = {"architect": "arch", "code": "code", "qa": "qa", "debug": "debug",
               "pre": "pre", "tests": "tests", "push": "push",
               "stand": "stand", "ready": "ready", "QA": "QA", "prod": "prod",
               "sec": "sec", "seo": "seo", "clean": "clean"}
# pipeline.py phase name -> roadmap phase
PIPELINE_MAP = {"pre": "pre", "build": "pre", "tests": "tests",
                "push": "push", "test": "stand", "ready": "ready", "qa": "QA",
                "QA": "QA", "prod": "prod", "sec": "sec", "seo": "seo",
                "clean": "clean"}


def framework_phase(tool_name, inp):
    """Map a Skill / Task invocation onto a Common Framework phase, or ''."""
    if tool_name == "Skill":
        key = str(inp.get("skill") or inp.get("name") or "")
    elif tool_name in ("Task", "Agent"):
        key = "%s %s" % (inp.get("subagent_type") or "", inp.get("description") or "")
    else:
        return ""
    key = key.lower()
    for needle, phase in FRAMEWORK_SIGNALS:
        if needle in key:
            return phase
    return ""


def work_phase(tools, fw_phase="", fw_age=None):
    """What this branch is busy with right now.

    An announced Common Framework phase wins while it is fresh. Otherwise a
    heuristic over the last ~14 tool events:
      architect — reading, searching, delegating; no edits yet
      code      — files are being written
      qa        — tests are being run and nothing is being edited
      debug     — files are being written right after something failed
    """
    if fw_phase in WORK_PHASES and (fw_age is None or fw_age <= FW_SIGNAL_TTL):
        return fw_phase
    recent = (tools or [])[-14:]
    edits = sum(1 for t in recent
                if t[0] in ("Edit", "Write", "MultiEdit", "NotebookEdit"))
    errs = sum(1 for t in recent if t[0] == "result" and t[1])
    tests = sum(1 for t in recent if t[0] == "test")
    if edits and errs:
        return "debug"
    if edits:
        return "code"
    if tests:
        return "qa"
    return "architect"


def roadmap(tr, run, session_started=None):
    """Roadmap rows: the work group is always on; the deploy group only turns
    on once a deploy actually started in this chat."""
    cur_work = work_phase(tr.get("tools"), tr.get("fw_phase", ""), tr.get("fw_age"))
    wi = WORK_PHASES.index(cur_work)

    deploy_on = False
    dep_cur = None
    dep_done = set()
    dep_skipped = set()
    note = ""
    if run and run.get("phases"):
        status = run.get("status", "running")
        deploy_on = True
        dep_cur = PIPELINE_MAP.get(run.get("current") or "", None)
        dep_done = {PIPELINE_MAP[p] for p in (run.get("done") or []) if p in PIPELINE_MAP}
        dep_skipped = {PIPELINE_MAP[p] for p in (run.get("skipped") or []) if p in PIPELINE_MAP}
        el = (run.get("finished") or time.time()) - (run.get("started") or time.time())
        m, sec = divmod(int(el), 60)
        el_txt = "%dm%02ds" % (m, sec) if m else "%ds" % sec
        if status == "gate":
            note = "gate · %s" % ((run.get("gate") or {}).get("question") or "?")
        elif status == "failed":
            note = "failed · %s" % (run.get("message") or "")
        elif status == "ok":
            note = "deploy done · %s" % el_txt
        else:
            note = "%s · %s" % (dep_cur or "-", el_txt)
    elif tr.get("deploy_seen"):
        deploy_on = True
        dep_cur = "pre"
        note = "deploy started"
    else:
        note = "no deploy in this chat"

    phases = []
    for i, p in enumerate(WORK_PHASES):
        state = "done" if (i < wi or deploy_on) else ("cur" if i == wi else "todo")
        phases.append({"key": p, "label": PHASE_LABEL.get(p, p),
                       "group": "work", "state": state})
    if deploy_on:
        seen_cur = False
        for p in DEPLOY_PHASES:
            if p in dep_skipped:
                st_ = "skip"
            elif p == dep_cur:
                st_ = "cur"
                seen_cur = True
            elif p in dep_done or (dep_cur is None and not seen_cur and run
                                   and run.get("status") == "ok"):
                st_ = "done"
            else:
                st_ = "todo"
            phases.append({"key": p, "label": PHASE_LABEL.get(p, p),
                           "group": "deploy", "state": st_})
    return {"phases": phases, "note": note, "deploy": deploy_on,
            "work": cur_work,
            "failed": bool(run and run.get("status") == "failed")}


def token_series(buckets, minutes=60, now=None):
    """Per-minute [input, output] token counts for the last `minutes`."""
    now_b = int((now or time.time()) // 60)
    ins, outs = [], []
    for b in range(now_b - minutes + 1, now_b + 1):
        v = (buckets or {}).get(str(b))
        ins.append(v[0] if v else 0)
        outs.append(v[1] if v else 0)
    return ins, outs


def phase_rail(theme, rm, width):
    """One line: the Common Framework work phases as a small rail,
    `● arch ━━ ◉ code ── ○ qa ── ○ debug`."""
    phases = [p for p in (rm.get("phases") or []) if p["group"] == "work"]
    if not phases:
        return ""
    glyph = {"done": "●", "cur": "◉", "todo": "○", "skip": "◌"}
    colour = {"done": theme.good, "cur": theme.accent, "todo": theme.dim, "skip": theme.dim}
    def build(link_pad, glyph_pad, links=True):
        out = []
        for i, p in enumerate(phases):
            if i:
                if links:
                    link = "━━" if phases[i - 1]["state"] == "done" else "──"
                    out.append(theme.c(theme.good if link == "━━" else theme.dim,
                                       link_pad + link[:1 if link_pad == "" else 2] + link_pad))
                else:
                    out.append(" ")
            out.append(theme.c(colour[p["state"]], glyph[p["state"]] + glyph_pad + p["label"]))
        return "".join(out)

    # widest form that fits: "● arch ━━ ◉ code", then tighter, then dots only
    for line in (build(" ", " "), build("", " "), build("", "", links=False)):
        if vlen(line) <= width:
            return line
    return " ".join(theme.c(colour[p["state"]], glyph[p["state"]]) for p in phases)


def hours_minutes(secs):
    """'1h 23m 05s' for a duration in seconds; always hours + minutes +
    seconds, minutes and seconds zero-padded ('0h 07m 03s'), so the row never
    changes width as the session runs. None (unknown duration) renders as an
    em dash."""
    if secs is None:
        return "—"
    secs = max(0, int(secs))
    return "%dh %02dm %02ds" % (secs // 3600, (secs % 3600) // 60, secs % 60)


def session_seconds(payload, tr, session_id=""):
    """How long this chat has been running, in seconds, or None.

    Claude Code puts `cost.total_duration_ms` (wall clock since the session
    started) into the statusline stdin JSON — that is the authoritative
    number. With `statusLine.refreshInterval` set, Claude Code re-runs this
    script every N seconds, but the payload it hands over may be the same
    snapshot as last time, so a bare `total_duration_ms` would freeze between
    turns. To keep the seconds ticking, the last value seen is remembered
    together with the moment it was seen (a tiny per-session file next to
    the transcript state): while the payload repeats that value, the elapsed
    wall clock since then is added on top; as soon as a fresh value arrives
    it wins and the clock re-anchors. When the field is missing altogether
    (older builds, --demo without it, foreign callers) fall back to the
    transcript: the earliest per-minute token bucket marks the first
    assistant turn, and "now" closes the interval.
    """
    cost = (payload or {}).get("cost") or {}
    ms = cost.get("total_duration_ms")
    if isinstance(ms, (int, float)) and ms >= 0:
        now = time.time()
        anchor = None
        if session_id:
            try:
                anchor = json.loads(anchor_path(session_id).read_text(encoding="utf-8"))
            except Exception:
                anchor = None
        if anchor and anchor.get("ms") == ms and isinstance(anchor.get("at"), (int, float)):
            return ms / 1000.0 + max(0.0, now - float(anchor["at"]))
        if session_id:
            try:
                anchor_path(session_id).write_text(json.dumps({"ms": ms, "at": now}), encoding="utf-8")
            except Exception:
                pass
        return ms / 1000.0
    buckets = (tr or {}).get("buckets") or {}
    try:
        first = min(int(k) for k in buckets)
    except ValueError:
        return None
    return max(0.0, time.time() - first * 60)


def price_row(theme, session_usd, session_secs, width):
    """The bare price line under the right column: session cost, session time.

    "session" is this chat alone — the number Claude Code reports for the
    running session. "t" is how long this chat has been open, hours, minutes
    and seconds (see session_seconds). When the duration is unknown the right
    half degrades to an em dash instead of disappearing, so the row keeps
    its width and the panel never jumps.
    """
    tcol = theme.dim if session_secs is None else theme.value
    txt = hours_minutes(session_secs)
    # the time label is always a bare "t"; the cost label shrinks if the column is narrow
    for l_lab, r_lab in (("session ", "t "), ("ses ", "t ")):
        left = theme.c(theme.label, l_lab) + theme.c(theme.money, money(session_usd))
        right = theme.c(theme.label, r_lab) + theme.c(tcol, txt)
        if vlen(left) + vlen(right) + 1 <= width:
            break
    return fit(left, right, width)


def limit_line(theme, left_frac, width):
    """A thin track of what is LEFT: it shrinks as the limit is consumed and
    the consumed part turns grey. One colour for the whole line — green,
    yellow once 30% or less is left, red at 10% or less."""
    left_frac = max(0.0, min(1.0, left_frac or 0.0))
    n = int(round(left_frac * width))
    if n == 0 and left_frac > 0:
        n = 1
    rgb = theme.bad if left_frac <= 0.10 else (theme.warn if left_frac <= 0.30 else theme.good)
    return theme.c(rgb, "━" * n) + theme.c(theme.dim, "─" * (width - n))


def until(ts_iso):
    """'4h 9m' / '6d 17h' until an ISO timestamp, or ''."""
    t = parse_ts(ts_iso)
    if not t:
        return ""
    d = max(0, int(t - time.time()))
    if d >= 86400:
        return "%dd %dh" % (d // 86400, (d % 86400) // 3600)
    if d >= 3600:
        return "%dh %dm" % (d // 3600, (d % 3600) // 60)
    return "%dm" % (d // 60)


def nearest_limit(cfg, cache):
    """Subscription: the window closest to exhaustion.
    Returns (name, used_frac, resets_in, real) or None. `real` is True when the
    numbers come from Anthropic's usage endpoint, False for the local estimate."""
    pu = cache.get("provider") or {}
    if pu.get("windows") and time.time() - float(pu.get("ts", 0)) < 3600:
        w = max(pu["windows"], key=lambda x: x["used"])
        return (w["name"], w["used"], until(w.get("resets_at")), True)
    lim = cfg.get("limits") or {}
    wins = cache.get("windows") or {}
    cands = []
    s_cap = float(lim.get("session_usd") or 0)
    if s_cap:
        cands.append(("%dh" % int(lim.get("session_hours", 5)), float(wins.get("session_usd") or 0) / s_cap))
    w_cap = float(lim.get("week_usd") or 0)
    if w_cap:
        cands.append(("week", float(wins.get("week_usd") or 0) / w_cap))
    if not cands:
        return None
    name, used = max(cands, key=lambda c: c[1])
    return (name, used, "", False)


def key_money_left(cfg, cache, tr, model_id):
    """API key / router: (left_usd, cap_usd, approx) or None."""
    km = cache.get("router") or {}
    adm = cache.get("admin") or {}
    wins = cache.get("windows") or {}
    budget = float(cfg.get("key_budget_usd") or 0)
    bal = km.get("balance")
    spent = km.get("spent")
    if spent is None and isinstance(adm.get("cost_usd"), (int, float)):
        spent = adm["cost_usd"]
    if bal is not None:
        cap = budget or ((float(bal) + float(spent)) if spent is not None else 0.0)
        return (float(bal), cap, False)
    if budget:
        if spent is None:
            spent = float(wins.get("session_usd") or 0)
        return (max(0.0, budget - float(spent)), budget, False)
    kt = key_tokens_left(cfg, cache, tr, model_id)
    if kt and kt["cap"]:
        tok_total = (tr.get("tok_in", 0) or 0) + (tr.get("tok_out", 0) or 0)
        cost = (tr.get("main_cost", 0) or 0) + (tr.get("agent_cost", 0) or 0)
        upt = (cost / tok_total) if (cost > 0 and tok_total > 0) else price_table(cfg, model_id)["in"] / 1e6
        return (kt["left"] * upt, kt["cap"] * upt, True)
    return None


def token_total_series(buckets, minutes=60, now=None):
    """Per-minute total (input + cache + output) tokens for the last `minutes`."""
    ins, outs = token_series(buckets, minutes=minutes, now=now)
    return [a + b for a, b in zip(ins, outs)]


def token_rate(buckets, minutes=5, now=None):
    """Average total tokens per minute over the last `minutes`."""
    tot = token_total_series(buckets, minutes=minutes, now=now)
    return int(sum(tot) / max(1, minutes))


def summarize(st):
    agents = sorted(st["chains"].values(), key=lambda a: a["order"])
    return {
        "main_cost": st["main_cost"],
        "agents": [{"label": a["label"], "cost": a["cost"],
                    "in": a.get("tin", 0), "out": a.get("tout", 0)} for a in agents],
        "agent_cost": sum(a["cost"] for a in agents),
        "ctx_tokens": st["ctx_tokens"],
        "ctx_model": st["ctx_model"],
        "n_msgs": st["n_msgs"],
        "tok_in": st.get("tok_in", 0),
        "tok_out": st.get("tok_out", 0),
        "tok_cache": st.get("tok_cache", 0),
        "buckets": st.get("buckets", {}),
        "tools": st.get("tools", []),
        "fw_phase": st.get("fw_phase", ""),
        "fw_age": (st.get("n_tools", 0) - st.get("fw_at", 0)) if st.get("fw_phase") else None,
        "deploy_seen": st.get("deploy_seen", 0),
    }


# --------------------------------------------------------------------------- #
# deploy pipeline (written by pipeline.py into <repo>/.pipeline/run.json)
# --------------------------------------------------------------------------- #

def read_pipeline(cfg, cwd):
    """Find and load the nearest .pipeline/run.json, if it is worth showing."""
    if not cfg.get("pipeline", {}).get("enabled", True):
        return None
    try:
        p = Path(cwd or ".").resolve()
    except Exception:
        return None
    run = None
    for d in [p] + list(p.parents):
        f = d / ".pipeline" / "run.json"
        if f.exists():
            try:
                run = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return None
            break
        if (d / ".git").exists():
            break
    if not run or not run.get("phases"):
        return None
    # keep a finished run on screen for a little while, then drop it
    if run.get("status") in ("ok", "failed"):
        keep = float(cfg["pipeline"].get("show_finished_minutes", 10)) * 60
        if time.time() - float(run.get("finished") or 0) > keep:
            return None
    # A run that nobody writes to any more is a ghost: `make` was interrupted,
    # the terminal was closed, a sample was rendered. Its elapsed timer would
    # keep ticking under every prompt and the caret would never move again.
    # The file's mtime is the only honest liveness signal — `pipeline` rewrites
    # it on every stage — so age it out. A gate waiting on a human is the one
    # legitimately quiet state, hence a generous default.
    stale = float(cfg["pipeline"].get("stale_hours", 6) or 0) * 3600
    if stale:
        try:
            if time.time() - f.stat().st_mtime > stale:
                return None
        except Exception:
            pass
    return run


def render_pipeline_row(theme, run, width):
    """One line: rail + where we are + what it is waiting for."""
    phases = run["phases"]
    done = set(run.get("done") or [])
    skipped = set(run.get("skipped") or [])
    cur = run.get("current")
    status = run.get("status", "running")
    failed = status == "failed"

    marks = []
    for i, ph in enumerate(phases):
        if i:
            idx = phases.index(cur) if cur in phases else (len(phases) if status == "ok" else -1)
            marks.append(theme.c(theme.good if i <= idx else theme.dim,
                                 "━" if i <= idx else "─"))
        if ph in skipped:
            marks.append(theme.c(theme.dim, "◌"))
        elif ph == cur:
            marks.append(theme.c(theme.bad if failed else theme.accent, "◉"))
        elif ph in done or status == "ok":
            marks.append(theme.c(theme.good, "●"))
        else:
            marks.append(theme.c(theme.dim, "○"))
    rail = "".join(marks)

    started = float(run.get("started") or time.time())
    end = float(run.get("finished") or time.time())
    el = end - started
    m, sec = divmod(int(el), 60)
    if m >= 60:
        el_txt = "%dh%02dm" % (m // 60, m % 60)
    elif m:
        el_txt = "%dm%02ds" % (m, sec)
    else:
        el_txt = "%ds" % sec

    st = run.get("stage") or {}
    where = cur or "-"
    if st.get("title"):
        where += " · " + str(st["title"])
    left = (theme.c(theme.label, "DEPLOY ") + rail +
            theme.c(theme.dim, "  ") + theme.c(theme.value, where) +
            theme.c(theme.dim, " · " + el_txt))

    if status == "gate":
        q = ((run.get("gate") or {}).get("question")) or "?"
        right = theme.c(theme.warn, "⏸ " + q)
    elif status == "failed":
        right = theme.c(theme.bad, "✗ " + (run.get("message") or "failed"))
    elif status == "ok":
        right = theme.c(theme.good, "✔ done")
    else:
        right = theme.c(theme.dim, run.get("version") or "")
    return fit(left, right, width)


# --------------------------------------------------------------------------- #
# git
# --------------------------------------------------------------------------- #

def git_branch(cwd):
    try:
        r = subprocess.run(
            ["git", "-C", cwd or ".", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=1.0,
        )
        if r.returncode == 0:
            b = r.stdout.strip()
            return b if b and b != "HEAD" else "detached"
    except Exception:
        pass
    return ""


def git_root(cwd):
    """Absolute path of the repository (or worktree) that owns `cwd`.

    The tree cost is scoped to a repository, so every session that ever ran
    anywhere inside this checkout — repo root, a subfolder, a nested tool
    directory — has to collapse onto one identity. `git rev-parse
    --show-toplevel` gives exactly that, and for a linked worktree it returns
    the worktree path rather than the main checkout, which is what "working
    branch" means to the user. Returns "" outside a repository.
    """
    try:
        r = subprocess.run(
            ["git", "-C", cwd or ".", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=1.0,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def git_dirty(cwd):
    try:
        r = subprocess.run(
            ["git", "-C", cwd or ".", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, timeout=1.0,
        )
        return bool(r.stdout.strip())
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# billing mode
# --------------------------------------------------------------------------- #

def billing_mode(cfg):
    """Returns (kind, name). kind in {'key','router','sub'}."""
    base = os.environ.get("ANTHROPIC_BASE_URL") or ""
    if base and "api.anthropic.com" not in base:
        host = re.sub(r"^https?://", "", base).split("/")[0].split(":")[0]
        parts = [p for p in host.split(".") if p not in
                 ("api", "www", "gateway", "gw", "proxy", "router", "v1")]
        short = (parts[0] if parts else host)
        return "router", short[:12]
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "key", "api key"
    if os.environ.get("CLAUDE_CODE_USE_BEDROCK") == "1":
        return "key", "bedrock"
    if os.environ.get("CLAUDE_CODE_USE_VERTEX") == "1":
        return "key", "vertex"
    return "sub", (cfg.get("plan") or "sub")


# --------------------------------------------------------------------------- #
# reasoning effort + context from the Claude Code payload
# --------------------------------------------------------------------------- #

EFFORT = {"low": ("Low", 1), "medium": ("Medium", 2), "high": ("High", 3),
          "xhigh": ("Extra high", 4), "max": ("Max", 5)}
METER_ON, METER_OFF = "▰", "▱"


def effort_level(payload):
    """Reasoning effort: the payload if Claude Code sends it, else settings.

    Returns (key, label, steps) or ("", "", 0)."""
    cands = []
    for k in ("effort", "effort_level", "reasoning_effort", "effortLevel"):
        v = payload.get(k)
        if isinstance(v, dict):
            v = v.get("level") or v.get("value")
        cands.append(v)
    m = payload.get("model") or {}
    cands += [m.get("effort"), m.get("effort_level"), m.get("reasoning_effort")]
    cands.append(os.environ.get("CLAUDE_CODE_EFFORT_LEVEL"))
    for name in ("settings.local.json", "settings.json"):
        try:
            cands.append(json.loads((CLAUDE_DIR / name).read_text(encoding="utf-8")).get("effortLevel"))
        except Exception:
            pass
    for v in cands:
        if isinstance(v, str) and v.strip():
            key = v.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
            if key in EFFORT:
                return (key,) + EFFORT[key]
            return (key, v.strip().capitalize(), 0)
    return ("", "", 0)


def effort_meter(theme, ef, width=5):
    key, label, steps = ef
    if not key:
        return theme.c(theme.dim, "reasoning: default")
    meter = (theme.c(theme.accent, METER_ON * steps) + theme.c(theme.dim, METER_OFF * (width - steps))
             if steps else "")
    return (theme.c(theme.label, "reasoning ") + meter + (" " if meter else "") +
            theme.c(theme.value, label))


def payload_context(payload):
    """(fraction, tokens, limit) from context_window in the payload, or None."""
    cw = payload.get("context_window") or {}
    if not isinstance(cw, dict):
        return None
    used = cw.get("used_percentage")
    tok = cw.get("used_tokens") or cw.get("total_tokens") or cw.get("tokens")
    lim = cw.get("context_window_size") or cw.get("size") or cw.get("limit")
    if isinstance(used, (int, float)):
        return (max(0.0, float(used) / 100.0), int(tok or 0), int(lim or 0))
    if isinstance(tok, (int, float)) and isinstance(lim, (int, float)) and lim:
        return (float(tok) / float(lim), int(tok), int(lim))
    return None


# --------------------------------------------------------------------------- #
# slow cache (rolling windows, admin API, router balance)
# --------------------------------------------------------------------------- #

def read_cache():
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def refresh_running():
    """A refresh is in flight if the lock is younger than 10 minutes."""
    try:
        return time.time() - LOCK_PATH.stat().st_mtime < 600
    except Exception:
        return False


def refresh_needed(cfg):
    """The slow scan only feeds API-key / router / admin views."""
    return True


def maybe_spawn_refresh(cfg, root=""):
    if not refresh_needed(cfg):
        return
    c = read_cache()
    age = time.time() - float(c.get("ts", 0))
    if age < max(20, int(cfg.get("refresh_seconds", 90))):
        return
    if refresh_running():          # statusline + cctok may fire at the same moment
        return
    try:
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--refresh"] +
            (["--root", str(root)] if root else []),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except Exception:
        pass


def scan_rolling_windows(cfg):
    """Sum locally computed cost over the last N hours / 7 days across all projects."""
    now = time.time()
    win_h = float(cfg["limits"].get("session_hours", 5)) * 3600.0
    week = 7 * 24 * 3600.0
    sess_sum = 0.0
    week_sum = 0.0
    sess_tok = 0
    week_tok = 0
    root = CLAUDE_DIR / "projects"
    if not root.exists():
        return {"session_usd": 0.0, "week_usd": 0.0, "session_tokens": 0,
                "week_tokens": 0, "files": 0}
    files = 0
    for f in root.rglob("*.jsonl"):
        try:
            if now - f.stat().st_mtime > week + 3600:
                continue
        except Exception:
            continue
        files += 1
        try:
            with f.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"usage"' not in line and '"costUSD"' not in line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    if e.get("type") != "assistant":
                        continue
                    ts = e.get("timestamp")
                    t = parse_ts(ts)
                    if t is None or now - t > week:
                        continue
                    msg = e.get("message") or {}
                    c = e.get("costUSD")
                    if not isinstance(c, (int, float)):
                        c = usage_cost(cfg, msg.get("model") or "", msg.get("usage"))
                    tk = usage_context(msg.get("usage"))
                    week_sum += c
                    week_tok += tk
                    if now - t <= win_h:
                        sess_sum += c
                        sess_tok += tk
        except Exception:
            continue
    return {"session_usd": sess_sum, "week_usd": week_sum,
            "session_tokens": sess_tok, "week_tokens": week_tok, "files": files}


# --------------------------------------------------------------------------- #
# tree cost: per-branch spend of one repository
# --------------------------------------------------------------------------- #

def project_slug(path):
    """Claude Code's own project-folder encoding: every non-alphanumeric -> "-"."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path or ""))


def tree_ledger_path(root):
    TREE_DIR.mkdir(parents=True, exist_ok=True)
    return TREE_DIR / (project_slug(root)[-120:] + ".json")


def read_tree(root):
    """Load the ledger of `root`, or None when it has never been built."""
    if not root:
        return None
    try:
        led = json.loads(tree_ledger_path(root).read_text(encoding="utf-8"))
    except Exception:
        return None
    return led if isinstance(led, dict) and led.get("root") == str(root) else None


def tree_project_dirs(root):
    """Every ~/.claude/projects folder that belongs to this repository.

    Claude Code keys a project folder by the *cwd* of the session, so one repo
    can own several of them: the root itself plus any subdirectory a session
    was started from. The encoding is lossy (it cannot be decoded back), but it
    is a prefix code — a subdirectory always encodes as the root's slug plus
    "-<rest>" — so a prefix match finds them all without decoding anything.
    """
    base = CLAUDE_DIR / "projects"
    if not root or not base.exists():
        return []
    slug = project_slug(root)
    out = []
    try:
        for d in base.iterdir():
            if d.is_dir() and (d.name == slug or d.name.startswith(slug + "-")):
                out.append(d)
    except Exception:
        return []
    return out


def scan_tree(cfg, root):
    """Rebuild/extend the per-branch cost ledger of one repository.

    Runs in the background refresh, never in the render path, because a cold
    build has to read every transcript of the repo once. Afterwards it is
    cheap: each transcript is remembered by byte offset, so a refresh only
    parses the lines that were appended since the previous one. Every
    assistant message carries `gitBranch`, so a session that hopped branches
    is split correctly instead of being charged to whatever branch it ended
    on. Result shape: {"root", "ts", "files": {key: offset}, "sessions":
    {session_id: {branch: usd}}}.
    """
    if not root or not (cfg.get("tree") or {}).get("enabled", True):
        return None
    led = read_tree(root) or {"root": str(root), "files": {}, "sessions": {}}
    led["root"] = str(root)
    files = led.setdefault("files", {})
    sessions = led.setdefault("sessions", {})

    for d in tree_project_dirs(root):
        for f in sorted(d.glob("*.jsonl")):
            key = d.name + "/" + f.name
            sid = f.stem
            try:
                size = f.stat().st_size
            except Exception:
                continue
            off = int(files.get(key) or 0)
            if off > size:                     # rotated or truncated: start over
                off, sessions[sid] = 0, {}
            if off == size:
                files[key] = off
                continue
            acc = sessions.setdefault(sid, {})
            try:
                with f.open("r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(off)
                    for line in fh:
                        if not line.endswith("\n"):
                            break              # partial last line; re-read next time
                        off += len(line.encode("utf-8", "replace"))
                        line = line.strip()
                        if not line or line[0] != "{":
                            continue
                        if '"usage"' not in line and '"costUSD"' not in line:
                            continue
                        try:
                            e = json.loads(line)
                        except Exception:
                            continue
                        if e.get("type") != "assistant":
                            continue
                        msg = e.get("message") or {}
                        c = e.get("costUSD")
                        if not isinstance(c, (int, float)):
                            c = usage_cost(cfg, msg.get("model") or "", msg.get("usage"))
                        br = e.get("gitBranch") or ""
                        acc[br] = acc.get(br, 0.0) + c
            except Exception:
                pass
            files[key] = off

    led["ts"] = time.time()
    try:
        pth = tree_ledger_path(root)
        tmp = pth.with_suffix(".json.%d.tmp" % os.getpid())
        tmp.write_text(json.dumps(led), encoding="utf-8")
        os.replace(str(tmp), str(pth))         # atomic: readers never see a half file
    except Exception:
        pass
    return led


def tree_cost(cfg, root, branch, session_id, live_cost):
    """Total spend of `branch` in this repository, in USD, or None.

    The ledger lags by one background refresh, and the session being rendered
    right now is exactly the one that moves. So the ledger contributes every
    *other* session of the branch, and the live cost of this chat is added on
    top — the number never goes stale and never counts this chat twice.
    """
    if not root or not (cfg.get("tree") or {}).get("enabled", True):
        return None
    led = read_tree(root)
    if led is None:
        return live_cost                       # ledger not built yet: show what we know
    # git_branch() reports a detached head as "detached"; the transcripts spell
    # the same state "HEAD". Accept both so a detached checkout still sums up.
    names = {branch, "HEAD"} if branch == "detached" else {branch}
    total = 0.0
    for sid, per_branch in (led.get("sessions") or {}).items():
        if sid == session_id or not isinstance(per_branch, dict):
            continue
        for name in names:
            total += float(per_branch.get(name, 0.0) or 0.0)
    return total + (live_cost or 0.0)


def key_tokens_left(cfg, cache, tr, model_id):
    """API-key mode: how many tokens are left, and from which source.

    Returns None when nothing is configured, else
    {"left": int, "cap": int|None, "used": int|None, "source": str, "approx": bool}
    """
    wins = cache.get("windows") or {}
    km = cache.get("router") or {}
    adm = cache.get("admin") or {}

    tok_total = (tr.get("tok_in", 0) or 0) + (tr.get("tok_out", 0) or 0)
    cost = (tr.get("main_cost", 0) or 0) + (tr.get("agent_cost", 0) or 0)
    if cost > 0 and tok_total > 0:
        usd_per_tok, approx = cost / tok_total, False
    else:
        usd_per_tok, approx = price_table(cfg, model_id)["in"] / 1e6, True

    budget_tok = int(cfg.get("key_budget_tokens") or 0)
    if budget_tok:
        used = int(wins.get("session_tokens") or 0)
        return {"left": max(0, budget_tok - used), "cap": budget_tok, "used": used,
                "source": "%dh" % int(cfg["limits"].get("session_hours", 5)), "approx": False}

    bal = km.get("balance")
    spent = km.get("spent")
    if spent is None and isinstance(adm.get("cost_usd"), (int, float)):
        spent = adm["cost_usd"]
    budget_usd = float(cfg.get("key_budget_usd") or 0)
    if bal is not None:
        left = int(float(bal) / usd_per_tok)
        cap_usd = budget_usd or (float(bal) + float(spent or 0)) if (spent is not None or budget_usd) else 0
        cap = int(cap_usd / usd_per_tok) if cap_usd else None
        return {"left": left, "cap": cap, "used": (cap - left) if cap else None,
                "source": "balance", "approx": approx}
    if budget_usd:
        if spent is None:
            spent = float(wins.get("session_usd") or 0)
        left_usd = max(0.0, budget_usd - float(spent))
        cap = int(budget_usd / usd_per_tok)
        return {"left": int(left_usd / usd_per_tok), "cap": cap,
                "used": int(float(spent) / usd_per_tok), "source": "budget", "approx": approx}
    return None


def parse_ts(ts):
    if not ts:
        return None
    try:
        s = str(ts).replace("Z", "+00:00")
        import datetime as _dt
        return _dt.datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def http_json(url, headers, timeout=6.0):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def dig(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur if isinstance(cur, (int, float)) else None


def deep_sum_amounts(obj):
    """Best-effort: sum every numeric 'amount' / 'cost' / 'value' leaf."""
    total = 0.0
    found = False

    def walk(o):
        nonlocal total, found
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("amount", "cost", "value", "total_cost_usd") and isinstance(v, (int, float)):
                    total += float(v)
                    found = True
                elif k in ("amount", "cost") and isinstance(v, dict):
                    walk(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return total if found else None


def fetch_admin(cfg):
    a = cfg.get("admin") or {}
    if not a.get("enabled"):
        return None
    key = os.environ.get(a.get("key_env") or "ANTHROPIC_ADMIN_KEY")
    if not key:
        return {"error": "no admin key in $%s" % (a.get("key_env"),)}
    import datetime as _dt
    start = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=int(a.get("window_days", 7)))
    url = "%s?starting_at=%s" % (a["url"], start.strftime("%Y-%m-%dT%H:00:00Z"))
    try:
        data = http_json(url, {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        })
    except Exception as ex:
        return {"error": str(ex)[:80]}
    total = deep_sum_amounts(data)
    return {"cost_usd": total, "window_days": int(a.get("window_days", 7))}


def fetch_router(cfg):
    k = cfg.get("router") or {}
    if not k.get("enabled") or not k.get("url"):
        return None
    headers = {"accept": "application/json"}
    tok = os.environ.get(k.get("token_env") or "")
    if tok:
        headers[k.get("auth_header", "Authorization")] = (k.get("auth_prefix", "Bearer ") or "") + tok
    try:
        data = http_json(k["url"], headers)
    except Exception as ex:
        return {"error": str(ex)[:80]}
    out = {}
    for p in k.get("balance_paths", []):
        v = dig(data, p)
        if v is not None:
            out["balance"] = float(v)
            break
    for p in k.get("spent_paths", []):
        v = dig(data, p)
        if v is not None:
            out["spent"] = float(v)
            break
    return out or {"error": "no balance field found"}


def do_refresh(root=""):
    if refresh_running():
        return
    try:
        CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
        LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass
    try:
        _do_refresh(root)
    finally:
        try:
            LOCK_PATH.unlink()
        except Exception:
            pass


def _do_refresh(root=""):
    cfg = load_config()
    cache = read_cache()
    cache["ts"] = time.time()
    try:
        cache["windows"] = scan_rolling_windows(cfg)
    except Exception as ex:
        cache["windows_error"] = str(ex)[:120]
    try:
        scan_tree(cfg, root)       # per-repo ledger, its own file next to the cache
    except Exception:
        pass
    if PROV is not None:
        pid = PROV.detect_provider(cfg, billing_mode(cfg)[0])
        cache["provider"] = PROV.fetch(pid, cfg)
    adm = fetch_admin(cfg)
    if adm is not None:
        cache["admin"] = adm
    km = fetch_router(cfg)
    if km is not None:
        cache["router"] = km
    try:
        tmp = CACHE_PATH.with_suffix(".json.%d.tmp" % os.getpid())
        tmp.write_text(json.dumps(cache), encoding="utf-8")
        os.replace(str(tmp), str(CACHE_PATH))      # atomic: readers never see a half-written file
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

def term_width(cfg):
    w = int(cfg.get("width") or 0)
    if not w:
        try:
            w = int(os.environ.get("COLUMNS") or 0)
        except Exception:
            w = 0
    if not w:
        try:
            import shutil
            w = shutil.get_terminal_size((100, 24)).columns
        except Exception:
            w = 100
    return max(40, min(240, w - int(cfg.get("margin", 4) or 0)))


def context_limit(cfg, tokens, model_id):
    lim = int(cfg.get("context_limit") or 0)
    if lim:
        return lim
    if tokens > 200_000 or "1m" in (model_id or "").lower():
        return 1_000_000
    return 200_000


def render(cfg, data):
    theme = Theme(cfg.get("theme", "dark"))
    W = term_width(cfg)

    # ---- gather ------------------------------------------------------------
    model = data["model_name"]
    kind, bill = data["billing"]
    branch = data["branch"]
    dirty = data["dirty"]
    proj = data["project"]
    tr = data["transcript"]
    cache = data["cache"]

    total_cost = data["session_cost"]
    agents = tr["agents"][: int(cfg.get("max_agents", 8))]
    agent_cost = tr["agent_cost"]
    main_cost = max(0.0, (total_cost or 0.0) - agent_cost) if total_cost else tr["main_cost"]
    sess_cost = total_cost if total_cost else main_cost + agent_cost

    ctx_tokens = tr["ctx_tokens"]
    ctx_lim = context_limit(cfg, ctx_tokens, data["model_id"])
    ctx_frac = (ctx_tokens / ctx_lim) if ctx_lim else 0.0
    if data.get("ctx_payload"):                 # Claude Code's own number wins
        ctx_frac = data["ctx_payload"][0]

    # ---- titles live inside the rows (no top border) -----------------------
    head = theme.c(theme.accent, proj)
    if branch:
        head += theme.c(theme.warn, " (%s)" % branch)
    if dirty:
        head += theme.c(theme.warn, "*")
    t_mid = ("TOKENS" if cfg.get("center", "tokens") == "tokens"
             else ("AGENTS" if agents else "SPEND"))

    # geometry: │ <LEFT> │ <MID> │ <RIGHT> │  -> W = LEFT+MID+RIGHT+10
    RIGHT = 24
    ef = data.get("effort") or ("", "", 0)
    ef_word = ef[1] if ef[0] else ""
    model_ef = (theme.c(theme.value, model) +
                ((theme.c(theme.dim, " · ") + theme.c(theme.accent, ef_word)) if ef_word else ""))
    model_ef = (theme.c(theme.value, model) +
                ((theme.c(theme.dim, " · ") + theme.c(theme.accent, ef_word)) if ef_word else ""))
    # ---- left column -------------------------------------------------------
    bill_rgb = {"sub": theme.good, "key": theme.warn, "router": theme.accent2}[kind]
    l1 = head

    if kind == "sub":
        l2 = theme.c(theme.label, "plan ") + theme.c(bill_rgb, bill)
    else:
        kt = key_tokens_left(cfg, cache, tr, data["model_id"])
        km = cache.get("router") or {}
        adm = cache.get("admin") or {}
        if kt is not None and kt["cap"]:
            frac = 1.0 - (kt["left"] / float(kt["cap"]))
            left_txt = ("≈" if kt["approx"] else "") + toks(kt["left"]) + " left"
            key_txt = theme.c(bill_rgb, bill) + theme.c(theme.dim, " · ")
            l2 = (key_txt + bar(theme, frac, 6) +
                  theme.c(theme.value, " " + pct(frac)) +
                  theme.c(theme.dim, " ") + theme.c(theme.money, left_txt))
        elif kt is not None:
            l2 = (theme.c(bill_rgb, bill) + theme.c(theme.dim, " · ") +
                  theme.c(theme.money, ("≈" if kt["approx"] else "") + toks(kt["left"]) + " left") +
                  theme.c(theme.dim, " · " + kt["source"]))
        elif km.get("error") or adm.get("error"):
            l2 = theme.c(bill_rgb, bill) + theme.c(theme.dim, " · " + vclip(km.get("error") or adm.get("error"), 24))
        else:
            l2 = theme.c(bill_rgb, bill) + theme.c(theme.dim, " · key budget not set")

    # row 1 is the project alone; row 2 carries plan/key on the left and
    # "model · effort" on the right, so the column is sized for row 2
    LEFT = max(24, min(56, max(vlen(l1), vlen(l2) + 2 + vlen(model_ef))))
    l1 = pad(l1, LEFT)
    l2 = fit(l2, model_ef, LEFT)

    # no outer frame:  <LEFT> │ <MID> │ <RIGHT>   -> width = LEFT+MID+RIGHT+6
    rest = W - LEFT - RIGHT - 6
    if rest < 18:
        MID = 18
    else:                       # the chart takes ~60% of the free width; the
        MID = max(min(30, rest), int(round(rest * 0.6)))   # panel is left-aligned, not stretched

    # ---- middle column: per-agent bars ------------------------------------
    if cfg.get("center", "tokens") == "tokens":
        tok_in = tr.get("tok_in", 0) or 0
        total_tok = tok_in + (tr.get("tok_out", 0) or 0)
        cache_frac = (float(tr.get("tok_cache", 0) or 0) / tok_in) if tok_in else 0.0
        sum_lbl = theme.c(theme.dim, "Σ ") + theme.c(theme.value, toks(total_tok))
        cache_lbl = theme.c(theme.dim, "cache ") + theme.c(theme.value, pct(cache_frac).strip())
        lw = max(vlen(sum_lbl), vlen(cache_lbl))
        cw = max(8, MID - lw - 1)                          # chart width
        totals = token_total_series(tr.get("buckets"), minutes=cw)
        m1 = fit(spark(theme, totals, theme.accent), sum_lbl, MID)
        pu = cache.get("provider") or {}
        p_title = pu.get("title") or ""
        p_fresh = bool(pu) and time.time() - float(pu.get("ts", 0)) < 3600
        prefix = (theme.c(theme.label, p_title + " ") if p_title and pu.get("provider") != "anthropic" else "")
        if p_fresh and pu.get("windows"):
            w = max(pu["windows"], key=lambda x: x["used"])
            lim_frac = max(0.0, 1.0 - w["used"])
            lim_lbl = (prefix + theme.c(theme.label, w["name"]) + theme.c(theme.dim, " · ") +
                       theme.c(theme.value, pct(lim_frac).strip() + " left"))
            rs = until(w.get("resets_at"))
            if rs and MID >= 46:
                lim_lbl += theme.c(theme.dim, " · ↻ " + rs)
        elif p_fresh and pu.get("balance"):
            b = pu["balance"]
            cap = b.get("cap") or float(cfg.get("key_budget_usd") or 0) or None
            lim_frac = (b["left"] / cap) if cap else 1.0
            cur = b.get("currency") or ""
            amt = money(b["left"]) if cur in ("USD", "credits", "") else "%.2f %s" % (b["left"], cur)
            lim_lbl = prefix + theme.c(theme.money, amt) + theme.c(theme.dim, " left")
        elif kind == "sub":
            nl = nearest_limit(cfg, cache)
            if nl is None:
                lim_frac, lim_lbl = 0.0, theme.c(theme.dim, pu.get("error") or "limits: waiting for usage data")
            else:
                name, used, resets, real = nl
                lim_frac = max(0.0, 1.0 - used)
                lim_lbl = (theme.c(theme.label, name) + theme.c(theme.dim, " · ") +
                           theme.c(theme.value, ("" if real else "≈") + pct(lim_frac).strip() + " left"))
        else:
            ml = key_money_left(cfg, cache, tr, data["model_id"])
            if ml is None:
                lim_frac, lim_lbl = 0.0, theme.c(theme.dim, pu.get("error") or "key budget not set")
            else:
                left_usd, cap_usd, approx = ml
                lim_frac = (left_usd / cap_usd) if cap_usd else 0.0
                lim_lbl = prefix + theme.c(theme.money, ("≈" if approx else "") + money(left_usd)) + theme.c(theme.dim, " left")
        lw2 = max(6, cw - vlen(lim_lbl) - 1)
        m2 = fit(limit_line(theme, lim_frac, lw2) + " " + lim_lbl, cache_lbl, MID)

    elif agents:
        vals = [a["cost"] for a in agents]
        m1 = spark(theme, vals, theme.accent2)
        m1 += theme.c(theme.dim, "  %d agents · %s" % (len(tr["agents"]), money(agent_cost)))
        chunks = []
        for a in agents:
            chunks.append(theme.c(theme.label, a["label"]) +
                          theme.c(theme.money, " " + money_short(a["cost"])))
        m2 = vclip(theme.c(theme.label, t_mid + "  ") + theme.c(theme.dim, " ").join(chunks), MID)
    else:
        m1 = theme.c(theme.dim, "no subagents this session")
        m2 = theme.c(theme.label, t_mid + "  ") + theme.c(theme.label, "main ") + theme.c(theme.money, money(main_cost))

    # ---- right column ------------------------------------------------------
    # row 1: "session ctx" names the bar below; row 2: the bar, full column.
    r1 = fit("", theme.c(theme.dim, "session ctx"), RIGHT)
    cbw = max(5, RIGHT - 5)
    r2 = bar(theme, ctx_frac, cbw) + theme.c(theme.value, " " + pct(ctx_frac))
    r3 = price_row(theme, sess_cost, data.get("session_secs"), RIGHT)

    V = theme.c(theme.frame, "│")
    rows = ["%s %s %s %s %s" % (pad(l1, LEFT), V, pad(m1, MID), V, pad(r1, RIGHT)),
            "%s %s %s %s %s" % (pad(l2, LEFT), V, pad(m2, MID), V, pad(r2, RIGHT))]

    # The prices always sit directly under the context bar, in the right
    # column, without a frame or a separator. When a deploy is on screen they
    # ride its line — the rail is squeezed to make room — so the panel does not
    # grow a fourth row just to carry two numbers.
    inner = LEFT + MID + RIGHT + 6
    run = data.get("pipeline")
    if run:
        rows.append(fit(render_pipeline_row(theme, run, inner - RIGHT - 2), r3, inner))
    else:
        rows.append(GUARD + "%s %s %s %s %s" % (" " * LEFT, " ", " " * MID, " ",
                                                pad(r3, RIGHT)))
    return "\n".join(rows)


def render_compact(cfg, data):
    """Fallback for narrow terminals: two lines."""
    theme = Theme(cfg.get("theme", "dark"))
    tr = data["transcript"]
    kind, bill = data["billing"]
    ctx_lim = context_limit(cfg, tr["ctx_tokens"], data["model_id"])
    ctx_frac = tr["ctx_tokens"] / ctx_lim if ctx_lim else 0
    if data.get("ctx_payload"):
        ctx_frac = data["ctx_payload"][0]
    head = "%s%s %s %s  %s %s%%" % (
        theme.c(theme.accent, data["project"]),
        theme.c(theme.warn, " (%s)" % data["branch"]) if data["branch"] else "",
        theme.c(theme.value, data["model_name"]),
        theme.c(theme.dim, "· ") + theme.c(theme.accent, (data.get("effort") or ("", "", 0))[1] or bill),
        theme.c(theme.label, "ctx") + " " + bar(theme, ctx_frac, 8),
        min(999, int(round(ctx_frac * 100))),
    )
    sp = spark(theme, [a["cost"] for a in tr["agents"]], theme.accent2)
    if kind == "sub":
        limits_txt = theme.c(theme.label, "plan ") + theme.c(theme.good, bill)
    else:
        kt = key_tokens_left(cfg, data["cache"], tr, data["model_id"])
        if kt is None:
            limits_txt = theme.c(theme.warn, bill) + theme.c(theme.dim, " · key budget not set")
        else:
            left = ("≈" if kt["approx"] else "") + toks(kt["left"]) + " left"
            if kt["cap"]:
                fr = 1.0 - kt["left"] / float(kt["cap"])
                limits_txt = (theme.c(theme.label, "tokens") + " " + bar(theme, fr, 6) +
                              " %d%% " % int(round(fr * 100)) + theme.c(theme.money, left))
            else:
                limits_txt = theme.c(theme.label, "tokens ") + theme.c(theme.money, left)
    sess = data["session_cost"] or tr["main_cost"] + tr["agent_cost"]
    secs = data.get("session_secs")
    tail = "%s  %s%s%s" % (
        limits_txt,
        theme.c(theme.label, "ses ") + theme.c(theme.money, money(sess)),
        theme.c(theme.dim, " · ") + theme.c(theme.label, "t ") +
        theme.c(theme.value, hours_minutes(secs)) if secs is not None else "",
        ("  " + sp + theme.c(theme.dim, " %dag" % len(tr["agents"]))) if tr["agents"] else "",
    )
    out = head + "\n" + tail
    if data.get("pipeline"):
        out += "\n" + render_pipeline_row(theme, data["pipeline"], term_width(cfg))
    return out


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def build_data(cfg, payload):
    cwd = payload.get("cwd") or (payload.get("workspace") or {}).get("current_dir") or os.getcwd()
    model = payload.get("model") or {}
    cost = payload.get("cost") or {}
    session_id = payload.get("session_id") or ""
    transcript = payload.get("transcript_path") or ""

    tr = parse_transcript(cfg, transcript, session_id)
    root = git_root(cwd)
    maybe_spawn_refresh(cfg, root)

    branch = git_branch(cwd)
    session_cost = cost.get("total_cost_usd")
    if session_cost is None:
        session_cost = tr["main_cost"] + tr["agent_cost"]

    return {
        "project": Path((payload.get("workspace") or {}).get("project_dir") or cwd).name or "~",
        "branch": branch,
        "dirty": git_dirty(cwd),
        "model_name": model.get("display_name") or model.get("id") or "claude",
        "model_id": model.get("id") or "",
        "billing": billing_mode(cfg),
        "session_cost": session_cost,
        "tree_cost": tree_cost(cfg, root, branch, session_id, session_cost),
        "session_secs": session_seconds(payload, tr, session_id),
        "transcript": tr,
        "cache": read_cache(),
        "pipeline": read_pipeline(cfg, cwd),
        "effort": effort_level(payload),
        "ctx_payload": payload_context(payload),
    }


def demo_payload():
    return {
        "session_id": "demo",
        "transcript_path": "",
        "cwd": os.getcwd(),
        "model": {"id": "claude-opus-5-20260101", "display_name": "Opus 5 (1M)"},
        "workspace": {"current_dir": os.getcwd(), "project_dir": os.getcwd()},
        "cost": {"total_cost_usd": 1.84, "total_duration_ms": 4985000},
        "context_window": {"used_percentage": 46},
        "effort": "high",
    }


def main():
    args = sys.argv[1:]
    cfg = load_config()

    if "--refresh" in args:
        root = ""
        if "--root" in args:
            i = args.index("--root")
            root = args[i + 1] if i + 1 < len(args) else ""
        do_refresh(root)
        return

    if "--doctor" in args:
        print("config file : %s (%s)" % (CONFIG_PATH, "found" if CONFIG_PATH.exists() else "missing, using defaults"))
        print("cache file  : %s (%s)" % (CACHE_PATH, "found" if CACHE_PATH.exists() else "missing"))
        print("projects    : %s" % (CLAUDE_DIR / "projects"))
        _root = git_root(os.getcwd())
        if _root:
            _led = read_tree(_root)
            print("tree ledger : %s (%s)" % (
                tree_ledger_path(_root),
                "%d sessions, branch %s" % (len(_led.get("sessions") or {}), git_branch(_root))
                if _led else "not built yet, wait for a refresh"))
        else:
            print("tree ledger : not a git repository, tree cost is off here")
        print("billing     : %s" % (billing_mode(cfg),))
        if PROV is not None:
            print("provider    : %s (auto-detected: %s; with credentials: %s)" % (
                PROV.detect_provider(cfg, billing_mode(cfg)[0]),
                PROV.detect_provider({"provider": "auto"}, billing_mode(cfg)[0]),
                ", ".join(PROV.available()) or "none"))
        print("width       : %d" % term_width(cfg))
        print("cache       : %s" % json.dumps(read_cache(), indent=2)[:1500])
        print("\neffective config:\n%s" % json.dumps(cfg, indent=2))
        return

    if "--demo" in args:
        payload = demo_payload()
        data = build_data(cfg, payload)
        import random
        random.seed(11)
        nb, buckets, v = 60, {}, 0.3
        now_b = int(time.time() // 60)
        for i in range(nb):
            v = max(0.03, min(1.0, v + random.uniform(-0.2, 0.22)))
            burst = 1.0 if 12 < i < 26 or 38 < i < 52 else 0.3
            buckets[str(now_b - nb + 1 + i)] = [int(v * burst * 240000),
                                                int(v * burst * 9000)]
        data["transcript"] = {
            "tok_in": 12_481_930, "tok_out": 392_114, "tok_cache": 11_900_000,
            "buckets": buckets, "main_cost": 0.72, "tools": [], "fw_phase": "code",
            "fw_age": 3,
            "agents": [
                {"label": "ui", "cost": 0.41}, {"label": "db", "cost": 0.28},
                {"label": "api", "cost": 0.19}, {"label": "tests", "cost": 0.14},
                {"label": "docs", "cost": 0.06},
            ],
            "agent_cost": 1.08, "ctx_tokens": 184000, "ctx_model": "opus", "n_msgs": 42,
        }
        data["cache"] = {"windows": {"session_usd": 10.2, "week_usd": 56.0,
                                     "session_tokens": 3_200_000, "week_tokens": 17_500_000}}
        if data["billing"][0] == "router":
            data["cache"]["router"] = {"balance": 12.4, "spent": 17.6}
        data["branch"] = data["branch"] or "main"
        data["tree_cost"] = 12.43          # fixed, so --demo renders identically
        if data.get("pipeline") is None:
            data["pipeline"] = {
                "phases": ["pre", "build", "tests", "push", "test", "ready",
                           "QA", "prod", "sec", "seo", "clean"],
                "done": ["pre", "build", "tests", "push", "test", "ready"],
                "skipped": [], "current": "QA", "status": "gate",
                "started": time.time() - 593, "finished": None,
                "version": "50e0485d",
                "stage": {"n": 3, "total": 5, "title": "Manual QA"},
                "gate": {"question": "Деплоить на PRODUCTION?"},
            }
        print(render(cfg, data))
        return

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    try:
        data = build_data(cfg, payload)
        w = term_width(cfg)
        print(render(cfg, data) if w >= 78 else render_compact(cfg, data))
    except Exception as ex:
        # never break the prompt
        m = (payload.get("model") or {}).get("display_name", "claude")
        print("%s · statusline error: %s" % (m, str(ex)[:60]))


if __name__ == "__main__":
    main()
