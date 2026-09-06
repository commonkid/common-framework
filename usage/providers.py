#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
providers.py — plan limits / balances of the model providers a CLI can run on.

One normalised shape for every provider:

    {"provider": "codex", "title": "Codex", "ts": 1700000000.0,
     "windows": [{"name": "week", "used": 0.88, "resets_at": "2026-09-07T..."}],
     "balance": {"left": 12.4, "cap": 30.0, "currency": "USD"},   # money providers
     "error": "..."}                                               # when it failed

`windows` are rolling quota windows (used = 0..1); `balance` is money left.
Credentials are read from the CLI's own store (Claude Code keychain, ~/.codex,
~/.gemini, GitHub Copilot) or from the provider's usual environment variable —
nothing is sent anywhere except the provider's own API.

    python3 providers.py            # probe every provider that has credentials
    python3 providers.py codex      # one provider
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

HOME = Path.home()
CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (HOME / ".claude"))
CODEX_DIR = Path(os.environ.get("CODEX_HOME") or (HOME / ".codex"))
GEMINI_DIR = HOME / ".gemini"
COPILOT_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or (HOME / ".config")) / "github-copilot"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _http(url, headers, data=None, timeout=8.0):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    h = dict(headers)
    if body is not None:
        h.setdefault("content-type", "application/json")
    req = urllib.request.Request(url, headers=h, data=body, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _err(ex):
    if isinstance(ex, urllib.error.HTTPError):
        return "HTTP %d" % ex.code
    return str(ex)[:80]


def _env(*names):
    for n in names:
        v = os.environ.get(n)
        if v:
            return v.strip()
    return ""


def _json_file(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _iso_from_epoch(ts):
    if not ts:
        return None
    try:
        import datetime as _dt
        return _dt.datetime.fromtimestamp(float(ts), _dt.timezone.utc).isoformat()
    except Exception:
        return None


def _window_name(seconds):
    try:
        s = int(seconds)
    except Exception:
        return "window"
    if s <= 0:
        return "window"
    if s % 86400 == 0 and s >= 86400 * 6:
        return "week" if s == 604800 else "%dd" % (s // 86400)
    if s % 3600 == 0:
        return "%dh" % (s // 3600)
    return "%dm" % (s // 60)


def _walk(obj):
    """Yield every dict inside a JSON tree."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            for d in _walk(v):
                yield d
    elif isinstance(obj, list):
        for v in obj:
            for d in _walk(v):
                yield d


PCT_KEYS = ("used_percent", "usage_percent", "usedPercent", "usagePercent", "percent",
            "utilization", "percentage", "usage")
REMAIN_PCT_KEYS = ("remaining_percent", "remainingPercent", "percent_remaining", "remainingFraction")
RESET_KEYS = ("reset_at", "resets_at", "resetAt", "resetsAt", "reset_time", "resetTime",
              "reset_date", "quota_reset_date", "next_reset", "nextReset", "reset_after_seconds")
NAME_KEYS = ("name", "window", "kind", "type", "period", "modelId", "model", "limit_name", "title")


def guess_windows(data):
    """Best effort for providers with undocumented payloads: every dict that
    carries a percentage (used or remaining) becomes a window."""
    out = []
    for d in _walk(data):
        used = None
        for k in PCT_KEYS:
            v = d.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                used = float(v)
                used = used / 100.0 if used > 1.0 else used
                break
        if used is None:
            for k in REMAIN_PCT_KEYS:
                v = d.get(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    rem = float(v)
                    rem = rem / 100.0 if rem > 1.0 else rem
                    used = 1.0 - rem
                    break
        if used is None:
            lim = d.get("limit") or d.get("total") or d.get("quota")
            u = d.get("used") or d.get("usage") or d.get("consumed")
            if isinstance(lim, (int, float)) and isinstance(u, (int, float)) and lim:
                used = float(u) / float(lim)
        if used is None:
            continue
        reset = None
        for k in RESET_KEYS:
            if k in d and d[k] not in (None, ""):
                v = d[k]
                if k == "reset_after_seconds":
                    reset = _iso_from_epoch(time.time() + float(v))
                elif isinstance(v, (int, float)):
                    reset = _iso_from_epoch(v if v < 1e12 else v / 1000.0)
                else:
                    reset = str(v)
                break
        name = None
        for k in NAME_KEYS:
            if isinstance(d.get(k), str) and d[k]:
                name = d[k][:14]
                break
        if name is None:
            secs = d.get("limit_window_seconds") or d.get("window_seconds") or d.get("windowSeconds")
            name = _window_name(secs) if secs else "quota"
        out.append({"name": name, "used": max(0.0, min(1.0, used)), "resets_at": reset})
    return out


def _result(pid, title, windows=None, balance=None, error=None):
    r = {"provider": pid, "title": title, "ts": time.time()}
    if windows:
        r["windows"] = windows
    if balance:
        r["balance"] = balance
    if error:
        r["error"] = error
    return r


# --------------------------------------------------------------------------- #
# 1. Claude (Anthropic subscription) — Claude Code's own OAuth token
# --------------------------------------------------------------------------- #

def anthropic_token():
    raw = ""
    if sys.platform == "darwin":
        try:
            r = subprocess.run(["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                               capture_output=True, text=True, timeout=5)
            raw = r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            raw = ""
    if not raw:
        try:
            raw = (CLAUDE_DIR / ".credentials.json").read_text(encoding="utf-8")
        except Exception:
            return ""
    try:
        return (json.loads(raw).get("claudeAiOauth") or {}).get("accessToken") or ""
    except Exception:
        return ""


def fetch_anthropic(cfg):
    tok = anthropic_token()
    if not tok:
        return _result("anthropic", "Claude", error="no Claude Code login")
    try:
        data = _http("https://api.anthropic.com/api/oauth/usage", {
            "Authorization": "Bearer " + tok, "anthropic-beta": "oauth-2025-04-20",
            "accept": "application/json", "user-agent": "claude-code/2.1.0"})
    except Exception as ex:
        return _result("anthropic", "Claude", error=_err(ex))
    wins = []
    for lim in data.get("limits") or []:
        if not isinstance(lim, dict) or lim.get("percent") is None:
            continue
        kind = lim.get("kind") or ""
        scope = ((lim.get("scope") or {}).get("model") or {}).get("display_name")
        name = "5h" if kind == "session" else ("week" + (" · " + scope if scope else "") if kind.startswith("weekly") else kind)
        wins.append({"name": name, "used": float(lim["percent"]) / 100.0, "resets_at": lim.get("resets_at")})
    if not wins:
        for key, name in (("five_hour", "5h"), ("seven_day", "week")):
            w = data.get(key) or {}
            if isinstance(w, dict) and w.get("utilization") is not None:
                wins.append({"name": name, "used": float(w["utilization"]) / 100.0, "resets_at": w.get("resets_at")})
    return _result("anthropic", "Claude", windows=wins, error=None if wins else "no windows in response")


# --------------------------------------------------------------------------- #
# 2. Codex (ChatGPT plan) — ~/.codex/auth.json
# --------------------------------------------------------------------------- #

def codex_auth():
    d = _json_file(CODEX_DIR / "auth.json")
    t = d.get("tokens") or {}
    return t.get("access_token") or "", t.get("account_id") or ""


def fetch_codex(cfg):
    tok, acct = codex_auth()
    if not tok:
        return _result("codex", "Codex", error="no Codex login (codex login)")
    h = {"Authorization": "Bearer " + tok, "accept": "application/json", "user-agent": "codex-cli"}
    if acct:
        h["chatgpt-account-id"] = acct
    try:
        data = _http("https://chatgpt.com/backend-api/wham/usage", h)
    except Exception as ex:
        return _result("codex", "Codex", error=_err(ex))
    wins = []
    rl = data.get("rate_limit") or {}
    for key in ("primary_window", "secondary_window"):
        w = rl.get(key)
        if isinstance(w, dict) and w.get("used_percent") is not None:
            wins.append({"name": _window_name(w.get("limit_window_seconds")),
                         "used": float(w["used_percent"]) / 100.0,
                         "resets_at": _iso_from_epoch(w.get("reset_at"))})
    bal = None
    cr = data.get("credits") or {}
    if cr.get("has_credits"):
        try:
            bal = {"left": float(cr.get("balance") or 0), "cap": None, "currency": "credits"}
        except Exception:
            bal = None
    return _result("codex", "Codex", windows=wins, balance=bal, error=None if wins else "no rate_limit in response")


# --------------------------------------------------------------------------- #
# 3. Gemini CLI / Antigravity — ~/.gemini/oauth_creds.json
# --------------------------------------------------------------------------- #

def fetch_gemini(cfg):
    creds = _json_file(GEMINI_DIR / "oauth_creds.json")
    tok = creds.get("access_token") or ""
    if not tok:
        return _result("gemini", "Gemini", error="no Gemini CLI login")
    project = _env("GOOGLE_CLOUD_PROJECT", "GEMINI_PROJECT") or ""
    body = {"project": project} if project else {}
    try:
        data = _http("https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota",
                     {"Authorization": "Bearer " + tok, "accept": "application/json"}, data=body)
    except Exception as ex:
        return _result("gemini", "Gemini", error=_err(ex))
    wins = []
    for d in _walk(data):
        if "remainingFraction" in d:
            wins.append({"name": (d.get("modelId") or d.get("model") or "quota")[:14],
                         "used": 1.0 - float(d.get("remainingFraction") or 0),
                         "resets_at": d.get("resetTime")})
    if not wins:
        wins = guess_windows(data)
    return _result("gemini", "Gemini", windows=wins, error=None if wins else "no quota buckets")


# --------------------------------------------------------------------------- #
# 4. GitHub Copilot — ~/.config/github-copilot/{apps,hosts}.json or GITHUB_TOKEN
# --------------------------------------------------------------------------- #

def copilot_token():
    for name in ("apps.json", "hosts.json"):
        d = _json_file(COPILOT_DIR / name)
        for v in d.values():
            if isinstance(v, dict) and v.get("oauth_token"):
                return v["oauth_token"]
    return _env("GITHUB_COPILOT_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")


def fetch_copilot(cfg):
    tok = copilot_token()
    if not tok:
        return _result("copilot", "Copilot", error="no GitHub Copilot login")
    try:
        data = _http("https://api.github.com/copilot_internal/user", {
            "Authorization": "token " + tok, "accept": "application/json",
            "Editor-Version": "vscode/1.100.0", "user-agent": "GitHubCopilotChat/0.30"})
    except Exception as ex:
        return _result("copilot", "Copilot", error=_err(ex))
    wins = []
    snaps = data.get("quota_snapshots") or {}
    reset = data.get("quota_reset_date") or data.get("quota_reset_date_utc")
    for key, name in (("premium_interactions", "premium"), ("chat", "chat"), ("completions", "compl")):
        q = snaps.get(key)
        if not isinstance(q, dict) or q.get("unlimited"):
            continue
        ent = q.get("entitlement")
        rem = q.get("remaining")
        pr = q.get("percent_remaining")
        if isinstance(pr, (int, float)):
            used = 1.0 - float(pr) / 100.0
        elif isinstance(ent, (int, float)) and ent and isinstance(rem, (int, float)):
            used = 1.0 - float(rem) / float(ent)
        else:
            continue
        wins.append({"name": name, "used": max(0.0, min(1.0, used)), "resets_at": reset})
    return _result("copilot", "Copilot", windows=wins, error=None if wins else "no quota_snapshots")


# --------------------------------------------------------------------------- #
# 5. OpenRouter — OPENROUTER_API_KEY
# --------------------------------------------------------------------------- #

def fetch_openrouter(cfg):
    key = _env("OPENROUTER_API_KEY")
    if not key:
        return _result("openrouter", "OpenRouter", error="OPENROUTER_API_KEY not set")
    try:
        data = _http("https://openrouter.ai/api/v1/credits", {"Authorization": "Bearer " + key})
    except Exception as ex:
        return _result("openrouter", "OpenRouter", error=_err(ex))
    d = data.get("data") or {}
    try:
        total, used = float(d.get("total_credits") or 0), float(d.get("total_usage") or 0)
    except Exception:
        return _result("openrouter", "OpenRouter", error="unexpected response")
    return _result("openrouter", "OpenRouter",
                   balance={"left": max(0.0, total - used), "cap": total or None, "currency": "USD"})


# --------------------------------------------------------------------------- #
# 6. DeepSeek — DEEPSEEK_API_KEY
# --------------------------------------------------------------------------- #

def fetch_deepseek(cfg):
    key = _env("DEEPSEEK_API_KEY")
    if not key:
        return _result("deepseek", "DeepSeek", error="DEEPSEEK_API_KEY not set")
    try:
        data = _http("https://api.deepseek.com/user/balance", {"Authorization": "Bearer " + key})
    except Exception as ex:
        return _result("deepseek", "DeepSeek", error=_err(ex))
    infos = data.get("balance_infos") or []
    if not infos:
        return _result("deepseek", "DeepSeek", error="no balance_infos")
    b = infos[0]
    try:
        left = float(b.get("total_balance") or 0)
    except Exception:
        left = 0.0
    return _result("deepseek", "DeepSeek",
                   balance={"left": left, "cap": None, "currency": b.get("currency") or "USD"})


# --------------------------------------------------------------------------- #
# 7. Moonshot (Kimi API, pay as you go) — MOONSHOT_API_KEY
# --------------------------------------------------------------------------- #

def fetch_moonshot(cfg):
    key = _env("MOONSHOT_API_KEY", "KIMI_API_KEY")
    if not key:
        return _result("moonshot", "Moonshot", error="MOONSHOT_API_KEY not set")
    base = "https://api.moonshot.cn" if _env("MOONSHOT_CN") else "https://api.moonshot.ai"
    try:
        data = _http(base + "/v1/users/me/balance", {"Authorization": "Bearer " + key})
    except Exception as ex:
        return _result("moonshot", "Moonshot", error=_err(ex))
    d = data.get("data") or data
    try:
        left = float(d.get("available_balance") or 0)
    except Exception:
        return _result("moonshot", "Moonshot", error="unexpected response")
    return _result("moonshot", "Moonshot", balance={"left": left, "cap": None, "currency": "CNY"})


# --------------------------------------------------------------------------- #
# 8. Kimi Code (coding plan) — KIMI_CODE_API_KEY
# --------------------------------------------------------------------------- #

def fetch_kimi_code(cfg):
    key = _env("KIMI_CODE_API_KEY")
    if not key:
        return _result("kimi-code", "Kimi Code", error="KIMI_CODE_API_KEY not set")
    try:
        data = _http("https://api.kimi.com/coding/v1/usages", {"Authorization": "Bearer " + key})
    except Exception as ex:
        return _result("kimi-code", "Kimi Code", error=_err(ex))
    wins = guess_windows(data)
    return _result("kimi-code", "Kimi Code", windows=wins, error=None if wins else "no usage windows")


# --------------------------------------------------------------------------- #
# 9. Z.ai GLM coding plan — ZAI_API_KEY / ZHIPU_API_KEY
# --------------------------------------------------------------------------- #

def fetch_zai(cfg):
    key = _env("ZAI_API_KEY", "Z_AI_API_KEY", "ZHIPU_API_KEY")
    if not key:
        return _result("zai", "GLM", error="ZAI_API_KEY not set")
    base = "https://open.bigmodel.cn" if _env("ZAI_CN") else "https://api.z.ai"
    try:
        data = _http(base + "/api/monitor/usage/quota/limit",
                     {"Authorization": key, "Accept-Language": "en-US,en", "accept": "application/json"})
    except Exception as ex:
        return _result("zai", "GLM", error=_err(ex))
    wins = guess_windows(data)
    return _result("zai", "GLM", windows=wins, error=None if wins else "no quota fields")


# --------------------------------------------------------------------------- #
# 10. MiniMax token plan — MINIMAX_API_KEY
# --------------------------------------------------------------------------- #

def fetch_minimax(cfg):
    key = _env("MINIMAX_API_KEY")
    if not key:
        return _result("minimax", "MiniMax", error="MINIMAX_API_KEY not set")
    base = "https://api.minimaxi.com" if _env("MINIMAX_CN") else "https://www.minimax.io"
    try:
        data = _http(base + "/v1/token_plan/remains", {"Authorization": "Bearer " + key})
    except Exception as ex:
        return _result("minimax", "MiniMax", error=_err(ex))
    wins = guess_windows(data)
    return _result("minimax", "MiniMax", windows=wins,
                   error=None if wins else "endpoint needs a web session, not an API key")


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #

PROVIDERS = [
    {"id": "anthropic",  "title": "Claude",     "fetch": fetch_anthropic,  "has": lambda: bool(anthropic_token()),
     "hosts": ("anthropic.com",)},
    {"id": "codex",      "title": "Codex",      "fetch": fetch_codex,      "has": lambda: bool(codex_auth()[0]),
     "hosts": ("openai.com", "chatgpt.com")},
    {"id": "gemini",     "title": "Gemini",     "fetch": fetch_gemini,     "has": lambda: (GEMINI_DIR / "oauth_creds.json").exists(),
     "hosts": ("googleapis.com",)},
    {"id": "copilot",    "title": "Copilot",    "fetch": fetch_copilot,    "has": lambda: bool(copilot_token()),
     "hosts": ("githubcopilot.com", "github.com")},
    {"id": "openrouter", "title": "OpenRouter", "fetch": fetch_openrouter, "has": lambda: bool(_env("OPENROUTER_API_KEY")),
     "hosts": ("openrouter.ai",)},
    {"id": "deepseek",   "title": "DeepSeek",   "fetch": fetch_deepseek,   "has": lambda: bool(_env("DEEPSEEK_API_KEY")),
     "hosts": ("deepseek.com",)},
    {"id": "moonshot",   "title": "Moonshot",   "fetch": fetch_moonshot,   "has": lambda: bool(_env("MOONSHOT_API_KEY", "KIMI_API_KEY")),
     "hosts": ("moonshot.ai", "moonshot.cn")},
    {"id": "kimi-code",  "title": "Kimi Code",  "fetch": fetch_kimi_code,  "has": lambda: bool(_env("KIMI_CODE_API_KEY")),
     "hosts": ("kimi.com",)},
    {"id": "zai",        "title": "GLM",        "fetch": fetch_zai,        "has": lambda: bool(_env("ZAI_API_KEY", "Z_AI_API_KEY", "ZHIPU_API_KEY")),
     "hosts": ("z.ai", "bigmodel.cn")},
    {"id": "minimax",    "title": "MiniMax",    "fetch": fetch_minimax,    "has": lambda: bool(_env("MINIMAX_API_KEY")),
     "hosts": ("minimax.io", "minimaxi.com", "minimax.chat")},
]
BY_ID = {p["id"]: p for p in PROVIDERS}


def detect_provider(cfg, billing_kind="sub"):
    """Which provider's limits to show.

    statusline.json "provider": an id from PROVIDERS, or "auto":
      * subscription (no API key / base URL)  -> anthropic
      * ANTHROPIC_BASE_URL points at a known host -> that provider
      * otherwise the first provider that has credentials, anthropic last
    """
    want = (cfg.get("provider") or "auto").strip().lower()
    if want in BY_ID:
        return want
    if billing_kind == "sub":
        return "anthropic"
    base = (os.environ.get("ANTHROPIC_BASE_URL") or "").lower()
    for p in PROVIDERS:
        if any(h in base for h in p["hosts"]):
            return p["id"]
    for p in PROVIDERS[1:]:
        try:
            if p["has"]():
                return p["id"]
        except Exception:
            pass
    return "anthropic"


def fetch(provider_id, cfg=None):
    p = BY_ID.get(provider_id)
    if not p:
        return {"provider": provider_id, "title": provider_id, "ts": time.time(), "error": "unknown provider"}
    try:
        return p["fetch"](cfg or {})
    except Exception as ex:
        return _result(p["id"], p["title"], error=_err(ex))


def available():
    """Ids of providers whose credentials are present on this machine."""
    out = []
    for p in PROVIDERS:
        try:
            if p["has"]():
                out.append(p["id"])
        except Exception:
            pass
    return out


if __name__ == "__main__":
    ids = sys.argv[1:] or available()
    if not ids:
        print("no provider credentials found; set an API key or log in to a CLI")
    for pid in ids:
        r = fetch(pid)
        line = "%-11s" % r["title"]
        if r.get("windows"):
            line += "  " + " · ".join("%s %d%% used" % (w["name"], round(w["used"] * 100)) for w in r["windows"])
        if r.get("balance"):
            b = r["balance"]
            line += "  balance %.2f %s" % (b["left"], b.get("currency") or "")
        if r.get("error"):
            line += "  [%s]" % r["error"]
        print(line)
