#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tokenpanel.py — iStat-Menus-style panel for a Claude Code session.

  left   — Tokens (total) / Rate per minute / Cache share / Session + Tree cost
  center — top: total token spend per minute (one series, budget line)
           bottom: the roadmap rail — the Common Framework phase this branch
           is in (arch / code / qa / debug), plus the deploy stages, which
           only appear once a deploy actually started
  right  — Context (bar) / Key / Model / Project + branch

The chart packs 8 sub-levels into each text row and stacks three rows, so a
column has 24 levels. The dashed yellow line is the budget rate; the part of a
bar above it is painted red.
"""

import argparse
import math
import re
import shutil

# --------------------------------------------------------------------------- #
# palette
# --------------------------------------------------------------------------- #

FRAME = (72, 78, 88)
LABEL = (176, 182, 192)
VALUE = (238, 241, 246)
DIM = (104, 111, 122)
TITLE = (150, 158, 170)
MONEY = (94, 234, 212)

TOK_FILL = (96, 178, 214)
TOK_EDGE = (150, 220, 246)
BUDGET = (250, 204, 21)
OVER = (248, 113, 113)
GOOD = (74, 222, 128)
CUR = (86, 204, 236)
VIOLET = (167, 139, 250)

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
BLOCKS = " ▁▂▃▄▅▆▇█"
DOT_DONE, DOT_CUR, DOT_TODO, DOT_SKIP, DOT_FAIL = "●", "◉", "○", "◌", "✗"


def fg(rgb, s):
    return "\x1b[38;2;%d;%d;%dm%s\x1b[0m" % (rgb[0], rgb[1], rgb[2], s)


def bold(s):
    return "\x1b[1m%s\x1b[0m" % s


def vlen(s):
    import unicodedata
    s = ANSI_RE.sub("", s)
    n = 0
    for ch in s:
        if unicodedata.combining(ch) or ch == "️":
            continue
        n += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return n


def vclip(s, width):
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


def pad(s, w, align="<"):
    d = w - vlen(s)
    if d <= 0:
        return vclip(s, w)
    return (" " * d + s) if align == ">" else s + " " * d


def center(s, w):
    d = w - vlen(s)
    if d <= 0:
        return vclip(s, w)
    return " " * (d // 2) + s + " " * (d - d // 2)


def fit(l, r, w):
    return l + " " * max(1, w - vlen(l) - vlen(r)) + r


def human(n):
    n = float(n)
    if n >= 1e9:
        return "%.1fB" % (n / 1e9)
    if n >= 1e6:
        return ("%.1fM" if n < 1e7 else "%.0fM") % (n / 1e6)
    if n >= 1e3:
        return ("%.1fk" if n < 1e4 else "%.0fk") % (n / 1e3)
    return "%d" % n


def commas(n):
    return "{:,}".format(int(n))


def load_color(frac):
    return OVER if frac >= .85 else (BUDGET if frac >= .6 else GOOD)


def bar(frac, width):
    frac = max(0.0, min(1.0, frac))
    n = max(0, min(width, int(round(frac * width))))
    return fg(load_color(frac), "█" * n) + fg(DIM, "░" * (width - n))


# --------------------------------------------------------------------------- #
# the token chart
# --------------------------------------------------------------------------- #

def _resample(seq, width):
    if not seq:
        return [0.0] * width
    if len(seq) == width:
        return [float(v) for v in seq]
    out = []
    for i in range(width):
        a, b = i * len(seq) / width, (i + 1) * len(seq) / width
        lo, hi = int(a), max(int(a) + 1, int(math.ceil(b)))
        chunk = seq[lo:min(hi, len(seq))] or [seq[min(lo, len(seq) - 1)]]
        out.append(float(sum(chunk)) / len(chunk))
    return out


def total_chart(values, width, rows=3, budget_frac=None):
    """`rows` stacked text rows, 8 sub-levels each, one series: total tokens
    per column. `budget_frac` (0..1 of the peak) draws the dashed budget line;
    the part of a bar above it is painted red."""
    v = _resample(values, width)
    top = max(v) or 1.0
    lv = rows * 8
    cells = [int(round(x / top * lv)) for x in v]
    budget_lv = int(round(budget_frac * lv)) if budget_frac is not None else None

    grid = []
    for r in range(rows):
        from_bottom = rows - 1 - r
        line = []
        for x in range(width):
            raw = cells[x] - from_bottom * 8
            filled = max(0, min(8, raw))
            if filled == 0:
                on_budget = (budget_lv is not None and
                             from_bottom * 8 < budget_lv <= (from_bottom + 1) * 8)
                line.append(fg(BUDGET, "╌") if on_budget and x % 3 == 0 else " ")
                continue
            if budget_lv is not None and from_bottom * 8 >= budget_lv:
                colr = OVER            # only the part above the budget goes red
            else:
                colr = TOK_EDGE if 0 < raw < 8 else TOK_FILL
            line.append(fg(colr, BLOCKS[filled]))
        grid.append("".join(line))
    return grid


# --------------------------------------------------------------------------- #
# the roadmap rail
# --------------------------------------------------------------------------- #

STATE_GLYPH = {"done": DOT_DONE, "cur": DOT_CUR, "todo": DOT_TODO, "skip": DOT_SKIP}
STATE_COLOR = {"done": GOOD, "cur": CUR, "todo": DIM, "skip": DIM}


def _lay_out(phases, labels):
    """Positions for a labelled rail: (label starts, divider columns, width)."""
    starts, dividers, pos, prev_group = [], [], 0, None
    for i, (p, lab) in enumerate(zip(phases, labels)):
        if i:
            if p["group"] != prev_group:
                dividers.append(pos + 1)
                pos += 3                      # " ┃ "
            else:
                pos += 1
        starts.append(pos)
        pos += len(lab)
        prev_group = p["group"]
    return starts, dividers, pos


def short_label(lab, n=4):
    """'debug' -> 'dbg', 'ready' -> 'rdy': drop inner vowels before clipping."""
    if len(lab) <= n:
        return lab
    core = lab[0] + "".join(ch for ch in lab[1:] if ch.lower() not in "aeiou")
    return core[:n]


def rail_rows(rm, width):
    """Track of dots plus labels underneath; falls back to a dots-only rail
    with a text legend when the labels cannot fit."""
    phases = rm.get("phases") or []
    if not phases:
        return " " * width, " " * width
    failed = bool(rm.get("failed"))

    chosen = None
    # 1) everything with full labels; 2) deploy group only (the work phases
    # are already done once a deploy runs) — like pipeline's own rail;
    # 3) the same with shortened labels; 4) dots only.
    attempts = [(phases, [p["label"] for p in phases])]
    deploy = [p for p in phases if p["group"] == "deploy"]
    if deploy:
        attempts.append((deploy, [p["label"] for p in deploy]))
        attempts.append((deploy, [short_label(p["label"]) for p in deploy]))
    else:
        attempts.append((phases, [short_label(p["label"]) for p in phases]))
    for cand, labels in attempts:
        starts, dividers, pos = _lay_out(cand, labels)
        if pos <= width:
            chosen = (cand, labels, starts, dividers, pos)
            break
    if chosen is None:
        return _rail_compact(rm, width)
    phases, labels, starts, dividers, pos = chosen

    centers = [starts[i] + len(labels[i]) // 2 for i in range(len(phases))]
    cur_idx = next((i for i, p in enumerate(phases) if p["state"] == "cur"), -1)

    track = [" "] * pos
    for i in range(len(phases) - 1):
        ch = "━" if i < cur_idx else "─"
        for j in range(centers[i] + 1, centers[i + 1]):
            track[j] = ch
    for i, p in enumerate(phases):
        g = DOT_FAIL if (p["state"] == "cur" and failed) else STATE_GLYPH[p["state"]]
        track[centers[i]] = g
    for j in dividers:
        if 0 <= j < pos:
            track[j] = "┃"

    def colour_of(p):
        if p["state"] == "cur" and failed:
            return OVER
        return STATE_COLOR[p["state"]]

    # paint the track one phase-segment at a time
    out, lo = [], 0
    for i, p in enumerate(phases):
        hi = centers[i] + 1
        seg = "".join(track[lo:hi])
        if "┃" in seg:
            a, b = seg.split("┃", 1)
            out.append(fg(DIM, a) + fg(FRAME, "┃") + fg(colour_of(p), b))
        else:
            out.append(fg(colour_of(p), seg))
        lo = hi
    track_line = "".join(out) + fg(DIM, "".join(track[lo:]))

    # labels, aligned to the same columns
    lbl, cursor = [], 0
    for i, (p, lab) in enumerate(zip(phases, labels)):
        gap = starts[i] - cursor
        if gap > 0:
            g = " " * gap
            if any(cursor <= j < starts[i] for j in dividers):
                g = " " * (dividers[0] - cursor if False else gap)
            lbl.append(g)
        c = colour_of(p)
        lbl.append(bold(fg(c, lab)) if p["state"] == "cur" else fg(c, lab))
        cursor = starts[i] + len(lab)
    return track_line, "".join(lbl)


def _rail_compact(rm, width):
    phases = rm.get("phases") or []
    failed = bool(rm.get("failed"))
    marks, prev_group = [], None
    for p in phases:
        if prev_group and p["group"] != prev_group:
            marks.append(fg(FRAME, "┃"))
        cur_fail = p["state"] == "cur" and failed
        marks.append(fg(OVER if cur_fail else STATE_COLOR[p["state"]],
                        DOT_FAIL if cur_fail else STATE_GLYPH[p["state"]]))
        prev_group = p["group"]
    cur = next((p for p in phases if p["state"] == "cur"), None)
    idx = [i for i, p in enumerate(phases) if p["state"] == "cur"]
    pos = "%d/%d" % ((idx[0] + 1) if idx else 0, len(phases))
    line1 = fit("".join(marks),
                fg(CUR, cur["label"] if cur else "-") + fg(DIM, " " + pos), width)
    legend = "  ".join(p["label"] for p in phases if p["group"] == "work")
    return line1, pad(fg(DIM, vclip(legend + "  ┃  " + (rm.get("note") or ""), width)), width)


# --------------------------------------------------------------------------- #
# panels
# --------------------------------------------------------------------------- #

def box(rows, width):
    out = [fg(FRAME, "╭" + "─" * (width + 2) + "╮")]
    for r in rows:
        out.append(fg(FRAME, "│") + " " + pad(r, width) + " " + fg(FRAME, "│"))
    out.append(fg(FRAME, "╰" + "─" * (width + 2) + "╯"))
    return out


def kv_rows(pairs, width):
    rows = []
    for i, (label, value, colr) in enumerate(pairs):
        if i:
            rows.append(fg(FRAME, "─" * width))
        rows.append(fit(fg(LABEL, label + ":"), fg(colr, value), width))
    return rows


def render(data, width=None, mode="tokens"):
    W = width or min(160, max(92, shutil.get_terminal_size((124, 24)).columns - 2))
    LW, RW = 22, 26
    CW = max(30, W - LW - RW - 12)

    left = kv_rows([
        ("Tokens", commas(data["tok_total"]),                      VALUE),
        ("Rate",   human(data["rate_min"]) + "/min",               TOK_EDGE),
        ("Cache",  "%d%%" % int(round(data["cache_frac"] * 100)),  TITLE),
        # Session is this chat; Tree is every chat of this repo on the branch
        # that is checked out right now. "—" means "not a git repo / no ledger".
        ("Session", "$%.2f" % data["cost"],                        MONEY),
        ("Tree",   "—" if data.get("tree_cost") is None
                   else "$%.2f" % data["tree_cost"],               MONEY),
    ], LW)

    ctx_f = data["ctx"] / max(1, data["ctx_limit"])
    bw = max(6, RW - 14)
    ctx_row = fit(fg(LABEL, "Context:"),
                  bar(ctx_f, bw) + " " +
                  fg(load_color(ctx_f), "%3d%%" % min(999, int(round(ctx_f * 100)))), RW)
    kind, keyname = data["billing"]
    key_color = {"sub": GOOD, "key": BUDGET, "router": VIOLET}.get(kind, VALUE)
    kt = data.get("tokens_left")
    if kt:                                   # API key / router: show the remainder
        keyname = "%s%s left" % ("≈" if kt.get("approx") else "", human(kt["left"]))
    pu = data.get("provider") or {}
    if pu.get("windows"):                    # plan limits of the detected provider
        w = max(pu["windows"], key=lambda x: x["used"])
        lft = max(0.0, 1.0 - w["used"])
        keyname = "%s %s %d%% left" % (pu.get("title", ""), w["name"], round(lft * 100))
        key_color = OVER if lft <= .10 else (BUDGET if lft <= .30 else GOOD)
    elif pu.get("balance"):
        b = pu["balance"]
        keyname = "%s %.2f %s left" % (pu.get("title", ""), b["left"], b.get("currency") or "")
    proj = data["project"] + (" (%s)" % data["branch"] if data["branch"] else "")
    right = [ctx_row, fg(FRAME, "─" * RW)] + kv_rows([
        ("Key",     keyname,       key_color),
        ("Model",   data["model"], VALUE),
        ("Repo",    proj,          TITLE),
    ], RW)

    if mode == "agents":
        ags = data["agents"][:8] or [{"label": "—", "total": 0}]
        gap = 2
        cell = max(3, (CW - gap * (len(ags) - 1)) // len(ags))
        vals = []
        for i, a in enumerate(ags):
            if i:
                vals += [0.0] * gap
            vals += [float(a["total"])] * cell
        chart = total_chart(vals[:CW], CW)
        head = "AGENTS"
        sub = "tokens per subagent"
    else:
        chart = total_chart(data["series_total"], CW,
                            budget_frac=data.get("budget_frac"))
        head = "TOKENS"
        sub = "total per minute"

    rm = data.get("roadmap") or {}
    note = vclip(rm.get("note") or "", max(0, CW // 2))
    if CW < 60:                       # narrow: drop the subtitle before clipping
        sub = ""
    head_txt = fg(TITLE, bold(head)) + (fg(DIM, "  · " + sub) if sub else "")
    title = fit(center(head_txt, max(0, CW - vlen(note) - 2)), fg(DIM, note), CW)
    dots, labels_row = rail_rows(rm, CW)
    rows_c = [title, fg(FRAME, "─" * CW)] + chart + [dots, labels_row]

    h = max(len(left), len(right), len(rows_c))
    for seq in (left, right, rows_c):
        while len(seq) < h:
            seq.append("")

    return "\n".join(a + b + c for a, b, c in
                     zip(box(left, LW), box(rows_c, CW), box(right, RW)))


# --------------------------------------------------------------------------- #

def demo_data(shape="normal"):
    import random
    random.seed(7)
    n, st, v = 60, [], 0.3
    for i in range(n):
        v = max(0.02, min(1.0, v + random.uniform(-0.18, 0.2)))
        burst = 1.0 if 12 < i < 26 or 38 < i < 52 else 0.3
        st.append(v * burst * 250_000)

    def ph(k, g, s):
        return {"key": k, "label": k, "group": g, "state": s}

    if shape == "deploy":
        phases = [ph(k, "work", "done") for k in ("arch", "code", "qa", "debug")] + [
            ph("pre", "deploy", "done"), ph("tests", "deploy", "done"),
            ph("push", "deploy", "done"), ph("test", "deploy", "done"),
            ph("ready", "deploy", "done"), ph("QA", "deploy", "cur"),
            ph("prod", "deploy", "todo"), ph("sec", "deploy", "todo"),
            ph("seo", "deploy", "todo"), ph("clean", "deploy", "todo")]
        note = "gate · Деплоить на PRODUCTION?"
    else:
        phases = [ph("arch", "work", "done"), ph("code", "work", "cur"),
                  ph("qa", "work", "todo"), ph("debug", "work", "todo")]
        note = "no deploy in this chat"

    return {
        "tok_total": 12_874_044, "rate_min": 41_800, "cache_frac": 0.953, "cost": 14.82, "tree_cost": 214.77,
        "ctx": 184_000, "ctx_limit": 200_000,
        "billing": ("sub", "Max20"), "model": "Opus 5 (1M)",
        "project": "my-project", "branch": "main",
        "series_total": st, "budget_frac": 0.62,
        "roadmap": {"phases": phases, "note": note,
                    "deploy": shape == "deploy", "work": "code", "failed": False},
        "agents": [
            {"label": "ui", "total": 861_000}, {"label": "db", "total": 538_000},
            {"label": "api", "total": 412_000}, {"label": "tests", "total": 271_000},
            {"label": "docs", "total": 103_000},
        ],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="tokens", choices=["tokens", "agents"])
    ap.add_argument("--shape", default="normal", choices=["normal", "deploy"])
    ap.add_argument("--width", type=int, default=0)
    a = ap.parse_args()
    print(render(demo_data(a.shape), a.width or None, a.mode))
