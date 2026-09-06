#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cctok — iStat-Menus-style token panel for the current Claude Code session.

    cctok              one frame
    cctok --watch      live panel, redraws every few seconds
    cctok --mode agents

Three boxes side by side:

  left   — Tokens (total) / Rate per minute / Cache share / Session + Tree cost
  center — top: total token spend per minute (one series, budget line)
           bottom: the roadmap rail. The work group is the Common Framework
           phase (arch / code / qa / debug) and is always on; the deploy group
           only appears once a deploy actually started in this chat.
  right  — Context (bar) / Key / Model / Repo + branch

Data comes from the transcript of the newest session for the current directory,
parsed incrementally by cc_statusline.py, plus <repo>/.pipeline/run.json for the
deploy stages. Everything shown is this session only, except the tree cost:
that one is the whole working branch of the repository, read from the ledger
cc_statusline.py keeps under ~/.claude/statusline-tree/.
"""

import argparse
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cc_statusline as CS          # noqa: E402
import tokenpanel as TP             # noqa: E402


# --------------------------------------------------------------------------- #
# finding the session
# --------------------------------------------------------------------------- #

def find_transcript(cwd=None):
    """Newest transcript for this directory, else the newest one anywhere.

    Claude Code keys a project folder by the cwd the session started in, so
    running cctok from a subfolder of the repo (tools/, usage/, ...) finds
    nothing by an exact slug match. Before falling back to "newest transcript
    on this machine" — which would report another repository entirely — widen
    the search to every project folder of the enclosing git repository.
    """
    root = CS.CLAUDE_DIR / "projects"
    if not root.exists():
        return None
    cwd = Path(cwd or os.getcwd()).resolve()
    # Claude Code slugifies the absolute path: every non-alphanumeric run -> "-"
    candidates = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        if d.name.strip("-").replace("-", "") == str(cwd).replace("/", "").replace(
                "_", "").replace(".", "").replace("-", ""):
            candidates += list(d.glob("*.jsonl"))
    if not candidates:
        slug = str(cwd).replace("/", "-")
        d = root / slug
        if d.is_dir():
            candidates += list(d.glob("*.jsonl"))
    if not candidates:                       # same repo, session started elsewhere
        for d in CS.tree_project_dirs(CS.git_root(str(cwd))):
            candidates += list(d.glob("*.jsonl"))
    if not candidates:
        candidates = list(root.rglob("*.jsonl"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def pretty_model(model_id):
    """claude-opus-5-20260101 -> Opus 5 ; unknown ids pass through trimmed."""
    m = (model_id or "").lower()
    fam = next((f for f in ("opus", "sonnet", "haiku", "fable", "mythos") if f in m), None)
    if not fam:
        return (model_id or "claude")[:18]
    import re as _re
    # "opus-5-20260101" -> 5 ; "sonnet-4-5-20250929" -> 4.5  (a trailing date
    # is 6+ digits and must never be read as a minor version)
    mt = _re.search(r"%s[-_]?(\d+)(?:-(\d{1,2})(?=-|$))?" % fam, m)
    v = ""
    if mt:
        v = mt.group(1) + ("." + mt.group(2) if mt.group(2) else "")
    return ("%s %s" % (fam.capitalize(), v)).strip()


def build_data(cfg, minutes=60, transcript=None):
    tpath = transcript or find_transcript()
    if tpath is None:
        tr = {"agents": [], "agent_cost": 0.0, "main_cost": 0.0, "ctx_tokens": 0,
              "ctx_model": "", "tok_in": 0, "tok_out": 0, "tok_cache": 0,
              "buckets": {}, "tools": [], "deploy_seen": 0, "fw_phase": "",
              "fw_age": None}
        name = "no session found"
    else:
        tr = CS.parse_transcript(cfg, str(tpath), tpath.stem)
        name = tpath.stem[:8]

    buckets = tr.get("buckets") or {}
    series_total = CS.token_total_series(buckets, minutes=minutes)
    rate_min = CS.token_rate(buckets, minutes=5)

    cost = (tr.get("main_cost") or 0.0) + (tr.get("agent_cost") or 0.0)
    cache = CS.read_cache()
    wins = cache.get("windows") or {}
    lim = cfg["limits"]
    hours = float(lim.get("session_hours", 5) or 5)

    # The budget line: the token rate that, sustained for the whole window,
    # exactly spends the window budget. Needs a $/token ratio, which only
    # exists once this session has actually cost something.
    budget_frac = None
    tok_in = tr.get("tok_in", 0) or 0
    tok_total = tok_in + (tr.get("tok_out", 0) or 0)
    cache_frac = (float(tr.get("tok_cache", 0) or 0) / tok_in) if tok_in else 0.0
    if cost > 0 and tok_total > 0 and lim.get("session_usd"):
        usd_per_tok = cost / tok_total
        budget_tok_min = (float(lim["session_usd"]) / (hours * 60.0)) / usd_per_tok
        peak = max(series_total) if series_total else 0
        if peak and budget_tok_min < peak:      # off-scale means comfortably under
            budget_frac = budget_tok_min / peak

    cwd = os.getcwd()
    root = CS.git_root(cwd)
    branch = CS.git_branch(cwd)
    run = CS.read_pipeline(cfg, cwd)
    rm = CS.roadmap(tr, run)

    return {
        "session": name,
        "tok_total": tok_total,
        "rate_min": rate_min,
        "cache_frac": cache_frac,
        "cost": cost,
        # Only claim a tree cost when the session on screen actually belongs to
        # this repository; the global fallback above may have landed on another
        # project, and pairing its session cost with our branch would lie.
        "tree_cost": (CS.tree_cost(cfg, root, branch, tpath.stem, cost)
                      if tpath is not None and tpath.parent in CS.tree_project_dirs(root)
                      else None),
        "ctx": tr.get("ctx_tokens", 0),
        "ctx_limit": CS.context_limit(cfg, tr.get("ctx_tokens", 0), tr.get("ctx_model", "")),
        "billing": CS.billing_mode(cfg),
        "tokens_left": CS.key_tokens_left(cfg, cache, tr, tr.get("ctx_model", ""))
                       if CS.billing_mode(cfg)[0] != "sub" else None,
        "provider": cache.get("provider") or {},
        "model": pretty_model(tr.get("ctx_model")),
        "project": Path(cwd).name or "~",
        "branch": branch,
        "win_usd": float(wins.get("session_usd") or 0.0),
        "win_cap": float(lim.get("session_usd") or 0) or 1,
        "week_usd": float(wins.get("week_usd") or 0.0),
        "week_cap": float(lim.get("week_usd") or 0) or 1,
        "series_total": series_total,
        "budget_frac": budget_frac,
        "roadmap": rm,
        "agents": [{"label": a["label"], "total": (a.get("in", 0) or 0) + (a.get("out", 0) or 0)}
                   for a in tr.get("agents", [])],
    }


# --------------------------------------------------------------------------- #
# watch mode
# --------------------------------------------------------------------------- #

def read_key(timeout):
    """One keypress within `timeout` seconds, or None. No-op when not a tty."""
    if not sys.stdin.isatty():
        time.sleep(timeout)
        return None
    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        return sys.stdin.read(1) if r else None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def watch(cfg, args):
    mode = args.mode
    sys.stdout.write("\x1b[?25l")              # hide cursor
    try:
        while True:
            data = build_data(cfg, minutes=args.minutes)
            frame = TP.render(data, args.width or None, mode)
            hint = TP.fg(TP.DIM, "  t tokens · a agents · q quit   %s" %
                         time.strftime("%H:%M:%S"))
            sys.stdout.write("\x1b[H" + frame + "\n" + hint + "\x1b[0J")
            sys.stdout.flush()
            k = read_key(args.interval)
            if k in ("q", "\x03", "\x04"):
                break
            if k == "t":
                mode = "tokens"
            elif k == "a":
                mode = "agents"
            elif k in ("\t", " "):
                mode = "agents" if mode == "tokens" else "tokens"
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\n")
        sys.stdout.flush()


# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser(prog="cctok", description=__doc__.split("\n")[1])
    ap.add_argument("--mode", default="tokens", choices=["tokens", "agents"])
    ap.add_argument("--watch", action="store_true", help="live panel")
    ap.add_argument("--interval", type=float, default=3.0, help="watch refresh, seconds")
    ap.add_argument("--minutes", type=int, default=60, help="chart window, minutes")
    ap.add_argument("--width", type=int, default=0)
    ap.add_argument("--transcript", default="", help="parse this .jsonl instead")
    ap.add_argument("--which", action="store_true", help="print the transcript in use")
    a = ap.parse_args()

    cfg = CS.load_config()
    if a.which:
        t = find_transcript()
        print(t or "no transcript found under %s" % (CS.CLAUDE_DIR / "projects"))
        return

    CS.maybe_spawn_refresh(cfg)
    tp = Path(a.transcript) if a.transcript else None
    if a.watch:
        watch(cfg, a)
    else:
        print(TP.render(build_data(cfg, a.minutes, tp), a.width or None, a.mode))


if __name__ == "__main__":
    main()
