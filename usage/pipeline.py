#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py — deploy pipeline renderer for a terminal, driven from a Makefile.

One rail of phases, redrawn at every stage, with per-phase timing compared
against the previous run, and blocking gates for human decisions.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     STAGE 2  Test Ready                                        ⏱ 9m 53s
     стенд готов к ручной проверке

     ●━━●━━━━●━━━●━━━◉───○────○─────○────○────○
     pre build tests push test ready QA prod sec seo clean
     ✔ Тестовый стенд обновлён: https://test.example.com
     ⏱ этап ready: 12s  (прошлый прогон: 9s ▲ +33%)

Usage from a Makefile
---------------------
    PL := python3 tools/pipeline.py

    all: pre build tests push test ready qa prod sec seo clean

    pre:
        @$(PL) init --name MYAPP \
            --phases pre,build,tests,push,test,ready,QA,prod,sec,seo,clean
        @$(PL) at pre
        ... your commands ...

    ready:
        @$(PL) stage 2 "Test Ready" --at ready --desc "стенд готов к ручной проверке"
        @$(PL) note ok "Тестовый стенд обновлён: https://test.example.com"
        @$(PL) link test https://test.example.com

    qa:
        @$(PL) stage 3 "Manual QA" --at QA --desc "опциональная ручная проверка перед продом"
        @$(PL) note dot "Стоит глянуть: новые фичи · edge cases · UI/UX изменения"
        @$(PL) gate "Деплоить на PRODUCTION?" --ok "Автотесты прошли"

    prod:
        @$(PL) at prod
        ... deploy ...
        @$(PL) done

State lives in <repo>/.pipeline/run.json — the statusline reads the same file,
so a running deploy shows up in the prompt of every terminal in that repo.

No third-party dependencies.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

STATE_DIRNAME = ".pipeline"
RUN_FILE = "run.json"
HISTORY_FILE = "history.json"
HISTORY_KEEP = 20

# --------------------------------------------------------------------------- #
# i18n
# --------------------------------------------------------------------------- #

STR = {
    "ru": {
        "stage": "STAGE",
        "phase_time": "этап",
        "prev_run": "прошлый прогон",
        "elapsed": "прошло",
        "total": "всего",
        "gate_yes": "да",
        "gate_no": "нет",
        "gate_hint": "[y/N]",
        "aborted": "Отменено",
        "failed": "УПАЛО",
        "ok": "ГОТОВО",
        "waiting": "ждёт решения",
        "skipped": "пропущено",
        "no_run": "нет активного прогона",
    },
    "en": {
        "stage": "STAGE",
        "phase_time": "phase",
        "prev_run": "previous run",
        "elapsed": "elapsed",
        "total": "total",
        "gate_yes": "yes",
        "gate_no": "no",
        "gate_hint": "[y/N]",
        "aborted": "Aborted",
        "failed": "FAILED",
        "ok": "DONE",
        "waiting": "awaiting decision",
        "skipped": "skipped",
        "no_run": "no active run",
    },
}


def T(key):
    lang = os.environ.get("PIPELINE_LANG", "ru")
    return STR.get(lang, STR["ru"]).get(key, key)


# --------------------------------------------------------------------------- #
# colors
# --------------------------------------------------------------------------- #

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

C = {
    "frame": (92, 99, 112),
    "dim": (78, 85, 97),
    "label": (122, 130, 144),
    "value": (232, 236, 242),
    "done": (74, 222, 128),
    "cur": (56, 208, 232),
    "warn": (250, 204, 21),
    "bad": (248, 113, 113),
    "accent": (96, 165, 250),
    "gate": (250, 204, 21),
}


def _no_color():
    return bool(os.environ.get("NO_COLOR")) or os.environ.get("PIPELINE_COLOR") == "0"


def c(key, s):
    if _no_color() or not s:
        return s
    r, g, b = C[key]
    return "\x1b[38;2;%d;%d;%dm%s\x1b[0m" % (r, g, b, s)


def bold(s):
    return s if _no_color() else "\x1b[1m%s\x1b[0m" % s


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


def term_width():
    try:
        w = int(os.environ.get("COLUMNS") or 0)
    except Exception:
        w = 0
    if not w:
        w = shutil.get_terminal_size((100, 24)).columns
    return max(48, min(140, w))


# --------------------------------------------------------------------------- #
# state
# --------------------------------------------------------------------------- #

def repo_root(start=None):
    p = Path(start or os.getcwd()).resolve()
    for d in [p] + list(p.parents):
        if (d / ".git").exists() or (d / STATE_DIRNAME).exists():
            return d
    return p


def state_dir(start=None):
    d = repo_root(start) / STATE_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_run(start=None):
    p = state_dir(start) / RUN_FILE
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_run(run, start=None):
    p = state_dir(start) / RUN_FILE
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def load_history(start=None):
    p = state_dir(start) / HISTORY_FILE
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"runs": []}


def push_history(run, start=None):
    h = load_history(start)
    h["runs"].append({
        "run_id": run.get("run_id"),
        "ts": run.get("started"),
        "finished": run.get("finished"),
        "status": run.get("status"),
        "version": run.get("version"),
        "durations": run.get("durations", {}),
        "total": (run.get("finished") or time.time()) - run.get("started", time.time()),
    })
    h["runs"] = h["runs"][-HISTORY_KEEP:]
    (state_dir(start) / HISTORY_FILE).write_text(
        json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")


def prev_duration(phase, start=None):
    """Duration of `phase` in the most recent successful run."""
    for r in reversed(load_history(start).get("runs", [])):
        if r.get("status") == "ok" and phase in (r.get("durations") or {}):
            return r["durations"][phase]
    return None


def git_version():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=2)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


# --------------------------------------------------------------------------- #
# formatting
# --------------------------------------------------------------------------- #

def fmt_dur(s):
    if s is None:
        return "—"
    s = float(s)
    if s < 1:
        return "0s"
    if s < 60:
        return "%ds" % int(round(s))
    m, sec = divmod(int(round(s)), 60)
    if m < 60:
        return "%dm %02ds" % (m, sec)
    h, m = divmod(m, 60)
    return "%dh %02dm" % (h, m)


def delta_note(cur, prev):
    if prev is None or cur is None or prev < 0.5 or cur < 0.5:
        return ""
    pct = (cur - prev) / prev * 100.0
    if abs(pct) < 8:
        return c("dim", " (%s: %s ≈)" % (T("prev_run"), fmt_dur(prev)))
    arrow, key = ("▲", "warn") if pct > 0 else ("▼", "done")
    return c("dim", " (%s: %s " % (T("prev_run"), fmt_dur(prev))) + \
        c(key, "%s %+d%%" % (arrow, int(round(pct)))) + c("dim", ")")


# --------------------------------------------------------------------------- #
# the rail
# --------------------------------------------------------------------------- #

DOT_DONE, DOT_CUR, DOT_TODO, DOT_FAIL, DOT_SKIP = "●", "◉", "○", "✗", "◌"
LINE_DONE, LINE_TODO = "━", "─"


def rail(run, width=None):
    """Two lines: the track with dots, and the phase names underneath."""
    phases = run["phases"]
    done = set(run.get("done", []))
    skipped = set(run.get("skipped", []))
    cur = run.get("current")
    failed = run.get("status") == "failed"

    width = width or term_width()
    # names line, phases separated by one space; remember each name's center
    names, centers, pos = [], [], 0
    for i, ph in enumerate(phases):
        if i:
            names.append(" ")
            pos += 1
        centers.append(pos + len(ph) // 2)
        names.append(ph)
        pos += len(ph)
    plain_names = "".join(names)

    # track line
    track = [" "] * pos
    for i, ph in enumerate(phases):
        ci = centers[i]
        if ph in skipped:
            track[ci] = DOT_SKIP
        elif ph == cur:
            track[ci] = DOT_FAIL if failed else DOT_CUR
        elif ph in done:
            track[ci] = DOT_DONE
        else:
            track[ci] = DOT_TODO
    # connectors
    cur_idx = phases.index(cur) if cur in phases else -1
    for i in range(len(phases) - 1):
        a, b = centers[i], centers[i + 1]
        ch = LINE_DONE if i < cur_idx else LINE_TODO
        for j in range(a + 1, b):
            track[j] = ch

    # colorize per-phase segments
    out = []
    for i, ph in enumerate(phases):
        lo = 0 if i == 0 else centers[i - 1] + 1
        hi = centers[i] + 1
        seg = "".join(track[lo:hi])
        if ph in skipped:
            out.append(c("dim", seg))
        elif ph == cur:
            out.append(c("bad" if failed else "cur", seg))
        elif ph in done:
            out.append(c("done", seg))
        else:
            out.append(c("dim", seg))
    track_line = "".join(out)

    # colorize names the same way
    nout = []
    for i, ph in enumerate(phases):
        if i:
            nout.append(" ")
        if ph in skipped:
            nout.append(c("dim", ph))
        elif ph == cur:
            nout.append(bold(c("bad" if failed else "cur", ph)))
        elif ph in done:
            nout.append(c("done", ph))
        else:
            nout.append(c("dim", ph))
    names_line = "".join(nout)

    if pos > width - 2:                       # too wide: drop to a compact rail
        marks = []
        for i, ph in enumerate(phases):
            if ph in skipped:
                marks.append(c("dim", DOT_SKIP))
            elif ph == cur:
                marks.append(c("bad" if failed else "cur", DOT_CUR))
            elif ph in done:
                marks.append(c("done", DOT_DONE))
            else:
                marks.append(c("dim", DOT_TODO))
        pos_txt = " %d/%d %s" % (cur_idx + 1, len(phases), cur or "")
        return "".join(marks) + c("label", pos_txt), None

    return track_line, names_line


# --------------------------------------------------------------------------- #
# blocks
# --------------------------------------------------------------------------- #

def hr(width=None, key="cur"):
    return c(key, "━" * (width or term_width()))


def print_stage(run, n, total, title, desc):
    w = term_width()
    elapsed = time.time() - run.get("started", time.time())
    head_l = " %s %s  %s" % (c("label", T("stage")), bold(c("value", str(n))) +
                             (c("dim", "/%s" % total) if total else ""),
                             bold(c("cur", title)))
    head_r = c("label", "⏱ ") + c("value", fmt_dur(elapsed)) + " "
    gap = max(1, w - vlen(head_l) - vlen(head_r))
    print()
    print(hr(w))
    print(head_l + " " * gap + head_r)
    if desc:
        print(" " + c("dim", desc))
    print()
    track, names = rail(run, w)
    print(" " + track)
    if names:
        print(" " + names)


ICONS = {
    "ok": ("✔", "done"),
    "fail": ("✗", "bad"),
    "warn": ("!", "warn"),
    "dot": ("·", "label"),
    "time": ("⏱", "label"),
    "run": ("→", "cur"),
    "rocket": ("🚀", "warn"),
}


def print_note(kind, text):
    ic, key = ICONS.get(kind, ICONS["dot"])
    print(" %s %s" % (c(key, ic), c("value" if kind in ("ok", "fail") else "label", text)))


def print_phase_timing(run, phase):
    cur = (run.get("durations") or {}).get(phase)
    prev = prev_duration(phase)
    line = " %s %s %s: %s" % (c("label", "⏱"), c("label", T("phase_time")),
                              c("value", phase), c("value", fmt_dur(cur)))
    print(line + delta_note(cur, prev))


def print_gate_box(question, subline=None, ok_line=None):
    w = term_width()
    inner = w - 2
    lines = []
    if ok_line:
        lines.append(c("done", "✅ ") + c("value", ok_line) +
                     (c("dim", "   ·   ") + c("warn", subline) if subline else ""))
    elif subline:
        lines.append(c("dim", subline))
    lines.append(c("warn", "🚀 ") + bold(c("gate", question)))
    print()
    print(c("gate", "╭" + "─" * inner + "╮"))
    for ln in lines:
        pad = max(0, inner - 1 - vlen(ln))
        print(c("gate", "│") + " " + ln + " " * pad + c("gate", "│"))
    print(c("gate", "╰" + "─" * inner + "╯"))


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #

def close_current_phase(run):
    cur = run.get("current")
    if not cur:
        return
    st = run.get("current_started")
    if st:
        run.setdefault("durations", {})[cur] = time.time() - st
    if cur not in run.setdefault("done", []):
        run["done"].append(cur)


def cmd_init(a):
    phases = [p.strip() for p in a.phases.split(",") if p.strip()]
    run = {
        "name": a.name or repo_root().name,
        "run_id": "%d" % int(time.time()),
        "started": time.time(),
        "phases": phases,
        "done": [],
        "skipped": [],
        "durations": {},
        "current": None,
        "current_started": None,
        "stage": None,
        "version": a.version or git_version(),
        "status": "running",
        "gate": None,
        "links": {},
        "finished": None,
        "message": "",
    }
    save_run(run)
    if not a.quiet:
        w = term_width()
        print()
        print(hr(w, "accent"))
        title = "%s  %s" % (bold(c("value", run["name"])),
                            c("dim", "· " + (run["version"] or "no version")))
        print(" " + title)
        track, names = rail(run, w)
        print(" " + track)
        if names:
            print(" " + names)
    return 0


def _require_run():
    run = load_run()
    if not run:
        sys.stderr.write("pipeline: %s (run `pipeline init` first)\n" % T("no_run"))
        sys.exit(2)
    return run


def cmd_at(a):
    run = _require_run()
    if a.phase not in run["phases"]:
        sys.stderr.write("pipeline: unknown phase %r\n" % a.phase)
        return 2
    close_current_phase(run)
    run["current"] = a.phase
    run["current_started"] = time.time()
    run["status"] = "running"
    save_run(run)
    if not a.quiet:
        track, names = rail(run)
        print(" " + track)
        if names:
            print(" " + names)
        prev = run.get("done", [])
        if prev:
            print_phase_timing(run, prev[-1])
    return 0


def cmd_stage(a):
    run = _require_run()
    if a.at:
        if a.at not in run["phases"]:
            sys.stderr.write("pipeline: unknown phase %r\n" % a.at)
            return 2
        if run.get("current") != a.at:
            close_current_phase(run)
            run["current"] = a.at
            run["current_started"] = time.time()
    run["stage"] = {"n": a.n, "total": a.total, "title": a.title, "desc": a.desc or ""}
    run["status"] = "running"
    save_run(run)
    print_stage(run, a.n, a.total, a.title, a.desc)
    prev = run.get("done", [])
    if prev:
        print_phase_timing(run, prev[-1])
    return 0


def cmd_note(a):
    run = load_run()
    print_note(a.kind, a.text)
    if run is not None and a.kind in ("ok", "fail", "warn"):
        run["message"] = a.text
        save_run(run)
    return 0


def cmd_link(a):
    run = _require_run()
    run.setdefault("links", {})[a.name] = a.url
    save_run(run)
    print_note("ok", "%s: %s" % (a.name, a.url))
    return 0


def cmd_skip(a):
    run = _require_run()
    for ph in a.phases.split(","):
        ph = ph.strip()
        if ph and ph not in run.setdefault("skipped", []):
            run["skipped"].append(ph)
    save_run(run)
    if not a.quiet:
        print_note("dot", "%s: %s" % (T("skipped"), a.phases))
    return 0


def cmd_gate(a):
    run = _require_run()
    sub = a.sub
    if sub is None:
        bits = []
        if run.get("version"):
            bits.append("версия %s" % run["version"])
        for k, v in (run.get("links") or {}).items():
            bits.append("%s: %s" % (k, v))
        sub = "  ·  ".join(bits)
    run["status"] = "gate"
    run["gate"] = {"question": a.question, "since": time.time()}
    save_run(run)

    print_gate_box(a.question, sub, a.ok)

    auto = a.auto or os.environ.get("PIPELINE_AUTO", "")
    if auto in ("yes", "y", "1"):
        answer = True
    elif auto in ("no", "n", "0"):
        answer = False
    elif not sys.stdin.isatty():
        answer = bool(a.default_yes)
    else:
        try:
            raw = input(" %s %s " % (c("gate", "?"), c("label", T("gate_hint")))).strip().lower()
        except (EOFError, KeyboardInterrupt):
            raw = ""
        answer = raw in ("y", "yes", "д", "да")

    run["status"] = "running"
    run["gate"] = None
    save_run(run)

    if answer:
        print_note("ok", T("gate_yes"))
        return 0
    print_note("warn", T("gate_no") + " — " + T("aborted"))
    return 1


def cmd_done(a):
    run = _require_run()
    close_current_phase(run)
    run["current"] = None
    run["current_started"] = None
    run["status"] = "ok"
    run["finished"] = time.time()
    save_run(run)
    push_history(run)
    w = term_width()
    total = run["finished"] - run["started"]
    print()
    print(hr(w, "done"))
    line = " %s %s  %s" % (c("done", "✔"), bold(c("done", T("ok"))),
                           c("dim", run.get("name", "")))
    right = c("label", "⏱ ") + c("value", fmt_dur(total))
    print(line + " " * max(1, w - vlen(line) - vlen(right)) + right)
    slow = sorted((run.get("durations") or {}).items(), key=lambda kv: -kv[1])[:4]
    if slow:
        print(" " + c("dim", "  ".join("%s %s" % (k, fmt_dur(v)) for k, v in slow)))
    return 0


def cmd_fail(a):
    run = _require_run()
    close_current_phase(run)
    run["status"] = "failed"
    run["message"] = a.reason or ""
    run["finished"] = time.time()
    save_run(run)
    push_history(run)
    w = term_width()
    print()
    print(hr(w, "bad"))
    print(" %s %s  %s" % (c("bad", "✗"), bold(c("bad", T("failed"))),
                          c("value", a.reason or "")))
    track, names = rail(run, w)
    print(" " + track)
    if names:
        print(" " + names)
    return 1


def cmd_status(a):
    run = load_run()
    if not run:
        if a.json:
            print("{}")
        else:
            print(T("no_run"))
        return 1
    if a.json:
        print(json.dumps(run, ensure_ascii=False))
        return 0
    cur = run.get("current") or "-"
    idx = run["phases"].index(cur) + 1 if cur in run["phases"] else 0
    el = (run.get("finished") or time.time()) - run.get("started", time.time())
    print("%s %s %d/%d %s %s" % (run.get("name", ""), run.get("status", ""),
                                 idx, len(run["phases"]), cur, fmt_dur(el)))
    return 0


def cmd_show(a):
    run = _require_run()
    st = run.get("stage") or {}
    print_stage(run, st.get("n", "-"), st.get("total"), st.get("title", ""), st.get("desc", ""))
    return 0


def cmd_reset(a):
    p = state_dir() / RUN_FILE
    try:
        p.unlink()
    except FileNotFoundError:
        pass
    print("pipeline: run state cleared")
    return 0


def cmd_demo(a):
    """Print a sample run without leaving one behind.

    The demo drives the very same state file the real pipeline uses, so a
    naive run would park a fake deploy — status "running", no finish time —
    in this repository forever, and the statusline would keep drawing its rail
    under every prompt. Snapshot whatever run.json was there, and put it back
    (or delete it) once the sample has been printed.
    """
    saved = state_dir() / RUN_FILE
    before = saved.read_bytes() if saved.exists() else None
    try:
        return _demo_body()
    finally:
        if before is None:
            saved.unlink(missing_ok=True)
            try:                       # do not leave an empty .pipeline behind:
                saved.parent.rmdir()   # repo_root() would anchor a later run on it
            except OSError:
                pass
        else:
            saved.write_bytes(before)


def _demo_body():
    phases = "pre,build,tests,push,test,ready,QA,prod,sec,seo,clean"
    ns = argparse.Namespace(name="MYAPP", phases=phases, version="50e0485d", quiet=False)
    cmd_init(ns)
    run = load_run()
    run["done"] = ["pre", "build", "tests", "push", "test"]
    run["durations"] = {"pre": 3, "build": 92, "tests": 41, "push": 18, "test": 26}
    run["started"] = time.time() - 593
    run["current"] = "ready"
    run["current_started"] = time.time() - 12
    run["links"] = {"test": "https://test.example.com"}
    save_run(run)
    cmd_stage(argparse.Namespace(n=2, total=5, title="Test Ready", at="ready",
                                 desc="стенд готов к ручной проверке"))
    print_note("ok", "Тестовый стенд обновлён: https://test.example.com")
    print_note("dot", "Автотесты уже прошли локально — стенд для ручной проверки")
    cmd_stage(argparse.Namespace(n=3, total=5, title="Manual QA", at="QA",
                                 desc="опциональная ручная проверка перед продом"))
    print_note("dot", "Стоит глянуть: новые фичи · edge cases · UI/UX изменения")
    print_gate_box("Деплоить на PRODUCTION?",
                   "версия 50e0485d на test",
                   "Автотесты прошли")
    return 0


# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser(prog="pipeline", description="terminal deploy pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="start a new run")
    p.add_argument("--name", default="")
    p.add_argument("--phases", required=True, help="comma-separated phase names")
    p.add_argument("--version", default="")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("at", help="move the caret to a phase")
    p.add_argument("phase")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_at)

    p = sub.add_parser("stage", help="print a stage header + rail")
    p.add_argument("n", type=int)
    p.add_argument("title")
    p.add_argument("--total", type=int, default=0)
    p.add_argument("--at", default="")
    p.add_argument("--desc", default="")
    p.set_defaults(fn=cmd_stage)

    p = sub.add_parser("note", help="print a note line")
    p.add_argument("kind", choices=sorted(ICONS.keys()))
    p.add_argument("text")
    p.set_defaults(fn=cmd_note)

    p = sub.add_parser("link", help="record a link shown in gates and the statusline")
    p.add_argument("name")
    p.add_argument("url")
    p.set_defaults(fn=cmd_link)

    p = sub.add_parser("skip", help="mark phases as skipped")
    p.add_argument("phases")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_skip)

    p = sub.add_parser("gate", help="blocking yes/no gate; exit 0 = yes, 1 = no")
    p.add_argument("question")
    p.add_argument("--sub", default=None, help="context line (default: version + links)")
    p.add_argument("--ok", default=None, help="green line above the question")
    p.add_argument("--auto", default="", choices=["", "yes", "no", "y", "n", "1", "0"])
    p.add_argument("--default-yes", action="store_true",
                   help="non-interactive stdin answers yes instead of no")
    p.set_defaults(fn=cmd_gate)

    p = sub.add_parser("done", help="finish the run successfully")
    p.set_defaults(fn=cmd_done)

    p = sub.add_parser("fail", help="finish the run as failed")
    p.add_argument("reason", nargs="?", default="")
    p.set_defaults(fn=cmd_fail)

    p = sub.add_parser("status", help="one line for scripts")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("show", help="redraw the current stage")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("reset", help="drop the run state")
    p.set_defaults(fn=cmd_reset)

    p = sub.add_parser("demo", help="render a sample pipeline")
    p.set_defaults(fn=cmd_demo)

    a = ap.parse_args()
    try:
        sys.exit(a.fn(a) or 0)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
