#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup.py — interactive installer for the Common bundle.

    python3 setup.py                 # interactive: pick products, CLIs, blocks
    python3 setup.py --all --yes     # everything, no questions (old restore.sh)
    python3 setup.py --products framework --cli claude,codex --blocks core,develop
    python3 setup.py --dry-run       # show what would be copied, touch nothing
    python3 setup.py --list          # print the block catalogue

Products
  framework  Common Framework — the Commoncode skills / agents / rules,
             installed into Claude Code, Codex, Kilo Code, OpenCode, Cursor,
             Antigravity or any other CLI that reads SKILL.md folders.
  usage      Common Usage — the terminal panels: statusline, cctok, pipeline.
             They read Claude Code transcripts, so they always go to the
             Claude config dir ($CLAUDE_CONFIG_DIR or ~/.claude).

Every file that would be overwritten is backed up first into
<target>/.common-setup-backup-<stamp>/. No third-party dependencies.
"""

import argparse
import re
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()
STAMP = time.strftime("%Y%m%d-%H%M%S")

CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (HOME / ".claude"))
CODEX_DIR = Path(os.environ.get("CODEX_HOME") or (HOME / ".codex"))
BIN_DIR = Path(os.environ.get("COMMON_BIN_DIR") or (HOME / ".local" / "bin"))


def _first_existing(*cands):
    for d in cands:
        if d.exists():
            return d
    return cands[0]


# Global config dirs of the other CLIs (each overridable by an env var).
KILO_DIR = Path(os.environ.get("COMMON_KILO_DIR")
                or _first_existing(HOME / ".kilo", HOME / ".kilocode"))
OPENCODE_DIR = Path(os.environ.get("COMMON_OPENCODE_DIR")
                    or (Path(os.environ.get("XDG_CONFIG_HOME") or (HOME / ".config")) / "opencode"))
CURSOR_DIR = Path(os.environ.get("COMMON_CURSOR_DIR") or (HOME / ".cursor"))
ANTIGRAVITY_DIR = Path(os.environ.get("COMMON_ANTIGRAVITY_DIR") or (HOME / ".gemini"))

# Where each CLI keeps its global instructions, skills and slash commands.
# "claude" / "codex" have hand-written file lists in FRAMEWORK_BLOCKS; the
# rest are derived from the codex (flat SKILL.md) side through these layouts:
#   rules    — where the global AGENTS.md goes (None = not supported globally)
#   command  — where a prompt like /develop goes; "skill" = wrap it as a skill
#   skills   — folder that holds <name>/SKILL.md
TARGETS = [
    {"id": "claude", "title": "Claude Code", "dir": CLAUDE_DIR, "bin": "claude",
     "layout": "claude", "hint": "скиллы commoncode:*, /develop, агенты mode-code / mode-qa"},
    {"id": "codex", "title": "Codex CLI", "dir": CODEX_DIR, "bin": "codex",
     "layout": "codex", "hint": "AGENTS.md, prompts/develop.md, скиллы $commoncode-*"},
    {"id": "kilo", "title": "Kilo Code", "dir": KILO_DIR, "bin": "kilo",
     "layout": {"rules": "rules/commoncode.md", "command": "workflows/{name}.md", "skills": "skills"},
     "hint": "rules/, workflows/develop.md, skills/"},
    {"id": "opencode", "title": "OpenCode", "dir": OPENCODE_DIR, "bin": "opencode",
     "layout": {"rules": "AGENTS.md", "command": "commands/{name}.md", "skills": "skills"},
     "hint": "AGENTS.md, commands/develop.md, skills/"},
    {"id": "cursor", "title": "Cursor", "dir": CURSOR_DIR, "bin": "cursor",
     "layout": {"rules": None, "command": "skill", "skills": "skills"},
     "hint": "skills/ (правила — AGENTS.md в корне проекта, см. README)"},
    {"id": "antigravity", "title": "Antigravity", "dir": ANTIGRAVITY_DIR, "bin": "antigravity",
     "layout": {"rules": "GEMINI.md", "command": "skill", "skills": "config/skills"},
     "hint": "GEMINI.md, config/skills/"},
    {"id": "other", "title": "Другая CLI (папка со skills/)", "dir": None, "bin": None,
     "layout": {"rules": "AGENTS.md", "command": "commands/{name}.md", "skills": "skills"},
     "hint": "AGENTS.md, commands/, skills/ в указанную папку"},
]
TARGET_BY_ID = {t["id"]: t for t in TARGETS}

# --------------------------------------------------------------------------- #
# catalogue
# --------------------------------------------------------------------------- #

CODEX_CORE = [
    "commoncode-core-rules", "commoncode-mode-architect", "commoncode-mode-debug",
    "commoncode-devplan-protocol", "commoncode-document-protocol",
    "commoncode-graph-protocol", "commoncode-data-transform",
]


def _skills(side, names):
    return [("%s/skills/%s" % (side, n), "skills/%s" % n) for n in names]


# (source relative to repo, destination relative to the CLI dir)
FRAMEWORK_BLOCKS = [
    {
        "id": "core", "required": True,
        "title": "Ядро Commoncode",
        "desc": "правила (Semantic Template + English-First) и плагин commoncode: "
                "core-rules, mode-architect, mode-debug, протоколы разметки",
        "claude": [("claude/rules", "rules"), ("claude/skills/commoncode", "skills/commoncode")],
        "codex": [("codex/AGENTS.md", "AGENTS.md")] + _skills("codex", CODEX_CORE),
    },
    {
        "id": "develop",
        "title": "/develop — оркестратор фаз",
        "desc": "Architect → Code → QA → Debug; субагенты mode-code и mode-qa",
        "claude": [("claude/commands/develop.md", "commands/develop.md"),
                   ("claude/agents/mode-code.md", "agents/mode-code.md"),
                   ("claude/agents/mode-qa.md", "agents/mode-qa.md")],
        "codex": [("codex/prompts/develop.md", "prompts/develop.md")]
                 + _skills("codex", ["commoncode-mode-code", "commoncode-mode-qa"]),
    },
    {
        "id": "dev-base",
        "title": "commoncode-dev-base — практическая база",
        "desc": "экзоскелет, LDD-логи, тесты, слои; шаблоны conftest / logger / DevPlan / AppGraph",
        "claude": _skills("claude", ["commoncode-dev-base"]),
        "codex": _skills("codex", ["commoncode-dev-base"]),
    },
    {
        "id": "master-prompt",
        "title": "/common-master-prompt — генератор мастер-промптов",
        "desc": "Prompt-as-Contract v5, шаблоны спринта и AppGraph",
        "claude": _skills("claude", ["common-master-prompt"]),
        "codex": _skills("codex", ["common-master-prompt", "master-prompt"]),
    },
    {
        "id": "ultraprompt",
        "title": "/ultraprompt — декомпозиция проекта",
        "desc": "разбивает проект на версионные задачи и GitHub Issues",
        "claude": _skills("claude", ["ultraprompt"]),
        "codex": _skills("codex", ["ultraprompt"]),
    },
    {
        "id": "version-test",
        "title": "/version-test — менеджер версий",
        "desc": "пре-релизные проверки и бамп версии vX.Y.Za",
        "claude": _skills("claude", ["version-test"]),
        "codex": _skills("codex", ["version-test"]),
    },
]

USAGE_FILES = {
    "cc_statusline.py": "cc_statusline.py",
    "providers.py": "providers.py",
    "cctok.py": "cctok.py",
    "tokenpanel.py": "tokenpanel.py",
    "ansi2html.py": "ansi2html.py",
    "pipeline.py": "pipeline.py",
    "Makefile.example": "pipeline.Makefile.example",
}

USAGE_BLOCKS = [
    {
        "id": "statusline",
        "title": "Статуслайн Claude Code",
        "desc": "три панели: модель и лимиты · расход токенов · стоимость и контекст; "
                "прописывается в settings.json",
        "files": ["cc_statusline.py", "providers.py"],
        "wire_statusline": True,
    },
    {
        "id": "cctok",
        "title": "cctok — панель сессии в терминале",
        "desc": "токены, скорость, кэш, стоимость, график и фазы Common Framework; "
                "команда `cctok` в ~/.local/bin",
        "files": ["cc_statusline.py", "providers.py", "cctok.py", "tokenpanel.py", "ansi2html.py"],
        "links": [("cctok.py", "cctok")],
    },
    {
        "id": "codex-statusline",
        "title": "Статус-строка Codex",
        "desc": "Codex не запускает внешние команды: включаются встроенные элементы — ветка, модель "
                "с уровнем рассуждения, лимиты 5h / неделя, контекст, стоимость (config.toml)",
        "files": [],
        "codex_status_line": True,
    },
    {
        "id": "pipeline",
        "title": "pipeline — рельс деплоя",
        "desc": "этапы, тайминги и гейты из Makefile; виден в статуслайне; команда `pipeline`",
        "files": ["pipeline.py", "Makefile.example"],
        "links": [("pipeline.py", "pipeline")],
    },
]

PRODUCTS = [
    {"id": "framework", "title": "Common Framework",
     "desc": "скиллы, агенты, команды и правила Commoncode для выбранных CLI"},
    {"id": "usage", "title": "Common Usage",
     "desc": "терминальные панели: статуслайн, cctok, pipeline (Claude Code) и статус-строка Codex"},
]

# --------------------------------------------------------------------------- #
# terminal UI
# --------------------------------------------------------------------------- #

IS_TTY = False
TTY_IN = None


def _open_tty():
    """stdin if it is a terminal, else /dev/tty (curl | bash), else None."""
    global IS_TTY, TTY_IN
    if sys.stdin.isatty():
        IS_TTY, TTY_IN = True, sys.stdin
        return
    try:
        TTY_IN = open("/dev/tty", "r")
        IS_TTY = TTY_IN.isatty()
    except Exception:
        TTY_IN, IS_TTY = None, False


def c(code, s):
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return s
    return "\x1b[%sm%s\x1b[0m" % (code, s)


BOLD, DIM, GREEN, YELLOW, CYAN, RED = "1", "2", "32", "33", "36", "31"


class RawKeys:
    """cbreak mode for the whole menu: one key at a time, no echo, Ctrl-C works."""

    def __enter__(self):
        import termios
        import tty
        self.fd = TTY_IN.fileno()
        self.old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd, termios.TCSANOW)      # keep typed-ahead keys
        return self

    def __exit__(self, *exc):
        import termios
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

    def key(self):
        """One key; arrow keys collapse to 'up' / 'down'. Reads the fd directly
        so nothing is left behind in a Python-level buffer."""
        import select
        ch = os.read(self.fd, 1)
        if ch == b"\x1b":
            seq = b""
            while len(seq) < 8:
                r, _, _ = select.select([self.fd], [], [], 0.05)
                if not r:
                    break
                seq += os.read(self.fd, 1)
                if seq[-1:].isalpha() or seq[-1:] == b"~":
                    break
            return {b"[A": "up", b"[B": "down", b"OA": "up", b"OB": "down"}.get(seq, "esc")
        try:
            return ch.decode("utf-8")
        except UnicodeDecodeError:
            return ""


def select_many(title, items, preselected, hint=""):
    """Checkbox list. items: [{"id","title","desc","required"?}]. Returns ids."""
    ids = [it["id"] for it in items]
    chosen = set(preselected)
    if not IS_TTY:
        print()
        print(c(BOLD, title))
        for i, it in enumerate(items, 1):
            mark = "x" if it["id"] in chosen else " "
            print("  [%s] %d. %s — %s" % (mark, i, it["title"], it["desc"]))
        print(c(DIM, "  (нет терминала: беру отмеченное по умолчанию)"))
        return [i for i in ids if i in chosen]

    cur = 0
    n = len(items)
    drawn = 0

    def draw():
        nonlocal drawn
        if drawn:
            sys.stdout.write("\x1b[%dA" % drawn)          # cursor up
        lines = [c(BOLD, title)]
        if hint:
            lines.append(c(DIM, hint))
        for i, it in enumerate(items):
            on = it["id"] in chosen
            box = c(GREEN, "[x]") if on else c(DIM, "[ ]")
            ptr = c(CYAN, "›") if i == cur else " "
            t = it["title"] + (c(YELLOW, "  (обязательно)") if it.get("required") else "")
            lines.append("%s %s %s" % (ptr, box, c(BOLD, t) if i == cur else t))
            lines.append("       " + c(DIM, it["desc"]))
        lines.append(c(DIM, "  ↑/↓ двигаться · пробел отметить · a все · n ничего · Enter продолжить · q выход"))
        out = "\n".join("\x1b[2K" + ln for ln in lines) + "\n"
        sys.stdout.write(out)
        sys.stdout.flush()
        drawn = len(lines)

    print()
    draw()
    with RawKeys() as keys:
        while True:
            k = keys.key()
            if k in ("up", "k"):
                cur = (cur - 1) % n
            elif k in ("down", "j", "\t"):
                cur = (cur + 1) % n
            elif k == " ":
                it = items[cur]
                if it["id"] in chosen:
                    if it.get("required"):
                        pass
                    else:
                        chosen.discard(it["id"])
                else:
                    chosen.add(it["id"])
            elif k == "a":
                chosen = set(ids)
            elif k == "n":
                chosen = {it["id"] for it in items if it.get("required")}
            elif k in ("\r", "\n"):
                break
            elif k in ("q", "\x03", "esc"):
                print(c(RED, "\nОтменено."))
                sys.exit(130)
            draw()
    return [i for i in ids if i in chosen]


def ask(prompt, default=""):
    if not IS_TTY:
        return default
    sys.stdout.write("%s%s " % (prompt, (" [%s]" % default) if default else ""))
    sys.stdout.flush()
    line = TTY_IN.readline()
    if not line:
        return default
    return line.strip() or default


def confirm(prompt, default=True):
    if not IS_TTY:
        return default
    ans = ask(prompt + (" [Y/n]" if default else " [y/N]"))
    if not ans:
        return default
    return ans.lower() in ("y", "yes", "д", "да")


# --------------------------------------------------------------------------- #
# file operations
# --------------------------------------------------------------------------- #

class Installer:
    def __init__(self, dry_run=False):
        self.dry = dry_run
        self.backups = {}      # target dir -> backup dir
        self.actions = []      # human-readable log

    def log(self, msg):
        self.actions.append(msg)
        print("  " + msg)

    def backup(self, root, target):
        """Copy an existing target aside before overwriting it."""
        if not target.exists() and not target.is_symlink():
            return
        bdir = self.backups.get(str(root))
        if bdir is None:
            bdir = root / (".common-setup-backup-" + STAMP)
            self.backups[str(root)] = bdir
        rel = target.relative_to(root)
        dest = bdir / rel
        if self.dry:
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        if target.is_dir() and not target.is_symlink():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(target, dest, symlinks=True)
        else:
            shutil.copy2(target, dest, follow_symlinks=False)

    def put(self, src, root, rel):
        """Copy file or directory `src` to root/rel (directories are replaced)."""
        target = root / rel
        if not src.exists():
            self.log(c(YELLOW, "пропуск (нет источника): %s" % src.relative_to(HERE)))
            return
        self.backup(root, target)
        self.log("%s → %s" % (src.relative_to(HERE), target))
        if self.dry:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if target.is_symlink() or target.is_file():
                target.unlink()
            elif target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", ".DS_Store"))
        else:
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            shutil.copy2(src, target)

    def put_text(self, text, root, rel, what):
        """Write generated content to root/rel (backed up like any other file)."""
        target = root / rel
        self.backup(root, target)
        self.log("%s → %s" % (what, target))
        if self.dry:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def link(self, target, name):
        """Symlink BIN_DIR/name -> target (only if BIN_DIR exists or can be made)."""
        try:
            BIN_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.log(c(YELLOW, "не могу создать %s — пропускаю %s" % (BIN_DIR, name)))
            return
        ln = BIN_DIR / name
        self.log("%s ⇢ %s" % (ln, target))
        if self.dry:
            return
        if ln.is_symlink() or ln.exists():
            ln.unlink()
        ln.symlink_to(target)
        try:
            os.chmod(target, 0o755)
        except Exception:
            pass

    def wire_statusline(self, root):
        """Set statusLine in <root>/settings.json (backup kept as .bak)."""
        p = root / "settings.json"
        cfg = {}
        if p.exists():
            try:
                cfg = json.loads(p.read_text(encoding="utf-8"))
            except Exception as ex:
                self.log(c(YELLOW, "settings.json не разобран (%s) — не трогаю. "
                                   "Добавь руками: \"statusLine\": {\"type\":\"command\","
                                   "\"command\":\"python3 ~/.claude/cc_statusline.py\",\"padding\":0}" % ex))
                return
        cmd = "python3 %s" % str(root / "cc_statusline.py").replace(str(HOME), "~", 1)
        cfg["statusLine"] = {"type": "command", "command": cmd, "padding": 0}
        self.log("settings.json: statusLine → %s" % cmd)
        if self.dry:
            return
        if p.exists():
            shutil.copy2(p, p.with_suffix(".json.bak"))
        root.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    CODEX_STATUS_ITEMS = ["git-branch", "model-with-reasoning", "five-hour-limit",
                          "weekly-limit", "context-used", "estimated-thread-cost"]

    def wire_codex_status_line(self, root):
        """Set [tui] status_line in <root>/config.toml (backup kept as .bak)."""
        p = root / "config.toml"
        line = "status_line = [%s]" % ", ".join('"%s"' % i for i in self.CODEX_STATUS_ITEMS)
        text = p.read_text(encoding="utf-8") if p.exists() else ""
        lines = text.split("\n") if text else []
        out, done, in_tui = [], False, False
        for ln in lines:
            st = ln.strip()
            if st.startswith("[") and not st.startswith("[["):
                in_tui = (st == "[tui]")
                out.append(ln)
                if in_tui and not done:
                    out.append(line); done = True
                continue
            if in_tui and st.startswith("status_line"):
                continue                             # replaced by the line we added
            if not in_tui and st.startswith("tui.status_line"):
                if not done:
                    out.append(line.replace("status_line", "tui.status_line", 1)); done = True
                continue
            out.append(ln)
        if not done:
            # no [tui] table: put the dotted key at the top, before any table header
            head, tail, seen_table = [], [], False
            for ln in out:
                if ln.strip().startswith("[") and not seen_table:
                    seen_table = True
                (tail if seen_table else head).append(ln)
            out = head + ["tui." + line, ""] + tail
        new = "\n".join(out).rstrip("\n") + "\n"
        self.log("config.toml: tui.status_line → %s" % ", ".join(self.CODEX_STATUS_ITEMS))
        if self.dry:
            return
        if p.exists():
            shutil.copy2(p, p.with_suffix(".toml.bak"))
        root.mkdir(parents=True, exist_ok=True)
        p.write_text(new, encoding="utf-8")

    def ensure_config(self, root):
        """statusline.json is created once from the example; never overwritten."""
        p = root / "statusline.json"
        if p.exists():
            self.log("оставляю существующий %s" % p)
            return
        self.log("создаю %s (поправь plan / limits под себя)" % p)
        if not self.dry:
            root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HERE / "usage" / "statusline.example.json", p)


# --------------------------------------------------------------------------- #
# plan + run
# --------------------------------------------------------------------------- #

def detect_clis():
    found = []
    for t in TARGETS:
        if t["dir"] is None:
            continue
        if t["dir"].exists() or (t["bin"] and shutil.which(t["bin"])):
            found.append(t["id"])
    return found


def prompt_as_skill(src):
    """Wrap a prompt file (codex/prompts/<name>.md) as <name>/SKILL.md."""
    name = src.stem
    body = src.read_text(encoding="utf-8")
    m = re.search(r"^---\s*\n(.*?)\n---\s*\n", body, re.S)
    desc = ""
    if m:
        dm = re.search(r"^description:\s*(.+)$", m.group(1), re.M)
        desc = dm.group(1).strip() if dm else ""
        body = body[m.end():]
    if not desc:
        hm = re.search(r"^#\s*/%s[^\n]*?[—-]\s*(.+)$" % re.escape(name), body, re.M)
        desc = hm.group(1).strip() if hm else "Common Framework /%s flow" % name
    return "---\nname: %s\ndescription: %s\ndisable-model-invocation: true\n---\n\n%s" % (
        name, desc.replace("\n", " "), body)


def install_framework(inst, blocks, clis, other_dir):
    for cid in clis:
        t = TARGET_BY_ID[cid]
        root = Path(other_dir).expanduser() if cid == "other" else t["dir"]
        layout = t["layout"]
        print()
        print(c(BOLD, "Common Framework → %s (%s)" % (root, t["title"])))
        for b in FRAMEWORK_BLOCKS:
            if b["id"] not in blocks:
                continue
            if layout in ("claude", "codex"):
                for src_rel, dst_rel in b[layout]:
                    inst.put(HERE / src_rel, root, dst_rel)
                continue
            # derived layout: map the codex-side files onto this CLI's folders
            for src_rel, dst_rel in b["codex"]:
                src = HERE / src_rel
                if dst_rel == "AGENTS.md":
                    if layout["rules"]:
                        inst.put(src, root, layout["rules"])
                    else:
                        inst.log(c(DIM, "правила: %s не читает глобальный AGENTS.md — "
                                       "скопируй codex/AGENTS.md в корень проекта" % t["title"]))
                elif dst_rel.startswith("prompts/"):
                    name = src.stem
                    if layout["command"] == "skill":
                        inst.put_text(prompt_as_skill(src), root,
                                      "%s/%s/SKILL.md" % (layout["skills"], name),
                                      "%s (как скилл)" % src_rel)
                    else:
                        inst.put(src, root, layout["command"].format(name=name))
                elif dst_rel.startswith("skills/"):
                    inst.put(src, root, "%s/%s" % (layout["skills"], src.name))
                else:
                    inst.put(src, root, dst_rel)


def install_usage(inst, blocks):
    root = CLAUDE_DIR
    print()
    print(c(BOLD, "Common Usage → %s" % root))
    files = []
    links = []
    wire = False
    for b in USAGE_BLOCKS:
        if b["id"] not in blocks:
            continue
        for f in b["files"]:
            if f not in files:
                files.append(f)
        links += b.get("links", [])
        wire = wire or b.get("wire_statusline", False)
    if any(b.get("codex_status_line") for b in USAGE_BLOCKS if b["id"] in blocks):
        inst.wire_codex_status_line(CODEX_DIR)
    for f in files:
        inst.put(HERE / "usage" / f, root, USAGE_FILES[f])
    if not inst.dry:
        for f in files:
            try:
                os.chmod(root / USAGE_FILES[f], 0o755)
            except Exception:
                pass
    if files:
        inst.ensure_config(root)
    for src, name in links:
        inst.link(root / USAGE_FILES[src], name)
    if wire:
        inst.wire_statusline(root)


def print_catalogue():
    print(c(BOLD, "Продукты"))
    for p in PRODUCTS:
        print("  %-10s %s — %s" % (p["id"], p["title"], p["desc"]))
    print()
    print(c(BOLD, "Блоки Common Framework  (--blocks)"))
    for b in FRAMEWORK_BLOCKS:
        print("  %-14s %s — %s" % (b["id"], b["title"], b["desc"]))
    print()
    print(c(BOLD, "Блоки Common Usage  (--usage-blocks)"))
    for b in USAGE_BLOCKS:
        print("  %-14s %s — %s" % (b["id"], b["title"], b["desc"]))


def summary(products, clis, other_dir, fw_blocks, us_blocks):
    print()
    print(c(BOLD, "План установки"))
    if "framework" in products:
        where = []
        for cid in clis:
            t = TARGET_BY_ID[cid]
            where.append("%s → %s" % (t["title"], other_dir if cid == "other" else t["dir"]))
        print("  Common Framework: %s" % ", ".join(fw_blocks))
        for w in where:
            print("      " + w)
    if "usage" in products:
        print("  Common Usage: %s" % ", ".join(us_blocks))
        print("      → %s  (команды в %s)" % (CLAUDE_DIR, BIN_DIR))
    print(c(DIM, "  Существующие файлы будут скопированы в .common-setup-backup-%s/ перед заменой." % STAMP))


def main():
    ap = argparse.ArgumentParser(description="Common bundle installer")
    ap.add_argument("--products", default="", help="framework,usage")
    ap.add_argument("--cli", default="", help="claude,codex,kilo,opencode,cursor,antigravity,other")
    ap.add_argument("--other-dir", default="", help="directory for --cli other")
    ap.add_argument("--blocks", default="", help="framework blocks, comma-separated or 'all'")
    ap.add_argument("--usage-blocks", default="", help="usage blocks, comma-separated or 'all'")
    ap.add_argument("--all", action="store_true", help="both products, all blocks, detected CLIs")
    ap.add_argument("--yes", "-y", action="store_true", help="no questions")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true", help="print the catalogue and exit")
    a = ap.parse_args()

    if a.list:
        print_catalogue()
        return 0

    _open_tty()
    interactive = IS_TTY and not a.yes

    print(c(BOLD, "Common — установка"))
    print(c(DIM, "источник: %s" % HERE))

    # ---- step 1: which CLIs ---------------------------------------------------
    detected = detect_clis()
    clis, other_dir = [], a.other_dir
    if a.cli:
        clis = [x.strip() for x in a.cli.split(",") if x.strip()]
        bad = [x for x in clis if x not in TARGET_BY_ID]
        if bad:
            print(c(RED, "неизвестные CLI: %s (доступны: %s)" % (
                ", ".join(bad), ", ".join(TARGET_BY_ID))))
            return 1
    elif interactive:
        items = []
        for t in TARGETS:
            if t["dir"] is None:
                desc = t["hint"]
            else:
                desc = "→ %s · %s%s" % (t["dir"], t["hint"],
                                        "  (найден)" if t["id"] in detected else "")
            items.append({"id": t["id"], "title": t["title"], "desc": desc})
        clis = select_many("Для каких CLI ставим Common Framework?", items,
                           detected or ["claude"],
                           "найденные отмечены; остальные ставятся в стандартные папки")
        if "other" in clis:
            other_dir = ask("  Папка для другой CLI:", other_dir or "")
            if not other_dir:
                clis.remove("other")
    else:
        clis = detected or ["claude"]
    if "other" in clis and not other_dir:
        print(c(RED, "--cli other требует --other-dir"))
        return 1

    # ---- step 2: products -----------------------------------------------------
    if a.all:
        products = ["framework", "usage"]
    elif a.products:
        products = [p.strip() for p in a.products.split(",") if p.strip()]
    elif interactive:
        pre = ["framework"] + (["usage"] if "claude" in clis else [])
        products = select_many("Что ставим?", PRODUCTS, pre,
                               "Common Usage читает транскрипты Claude Code")
    else:
        products = ["framework"] + (["usage"] if "claude" in clis else [])
    if not products:
        print(c(RED, "Ничего не выбрано."))
        return 1
    if "framework" in products and not clis:
        print(c(RED, "Не выбрана ни одна CLI."))
        return 1

    # ---- blocks -------------------------------------------------------------
    fw_ids = [b["id"] for b in FRAMEWORK_BLOCKS]
    us_ids = [b["id"] for b in USAGE_BLOCKS]
    fw_blocks, us_blocks = [], []
    if "framework" in products:
        if a.all or a.blocks == "all":
            fw_blocks = fw_ids
        elif a.blocks:
            fw_blocks = [x.strip() for x in a.blocks.split(",") if x.strip()]
            bad = [x for x in fw_blocks if x not in fw_ids]
            if bad:
                print(c(RED, "неизвестные блоки: %s" % ", ".join(bad)))
                return 1
        elif interactive:
            fw_blocks = select_many("Блоки Common Framework", FRAMEWORK_BLOCKS, fw_ids,
                                    "ядро ставится всегда; остальное — по желанию")
        else:
            fw_blocks = fw_ids
        if "core" not in fw_blocks:
            fw_blocks = ["core"] + fw_blocks
    if "usage" in products:
        if a.all or a.usage_blocks == "all":
            us_blocks = us_ids
        elif a.usage_blocks:
            us_blocks = [x.strip() for x in a.usage_blocks.split(",") if x.strip()]
            bad = [x for x in us_blocks if x not in us_ids]
            if bad:
                print(c(RED, "неизвестные блоки: %s" % ", ".join(bad)))
                return 1
        elif interactive:
            us_blocks = select_many("Блоки Common Usage", USAGE_BLOCKS, us_ids,
                                    "все три читают транскрипты Claude Code из %s" % CLAUDE_DIR)
        else:
            us_blocks = us_ids
        if not us_blocks:
            products.remove("usage")

    if shutil.which("python3") is None and "usage" in products:
        print(c(YELLOW, "python3 не найден в PATH — Common Usage не сможет запускаться."))

    summary(products, clis, other_dir, fw_blocks, us_blocks)
    if interactive and not a.dry_run and not confirm("Продолжить?"):
        print("Отменено.")
        return 130

    # ---- run ----------------------------------------------------------------
    inst = Installer(dry_run=a.dry_run)
    if a.dry_run:
        print(c(YELLOW, "\n--dry-run: ничего не записываю"))
    if "framework" in products:
        install_framework(inst, fw_blocks, clis, other_dir)
    if "usage" in products:
        install_usage(inst, us_blocks)

    # ---- epilogue -----------------------------------------------------------
    print()
    print(c(GREEN, "Готово." if not a.dry_run else "Просмотр завершён."))
    for root, b in inst.backups.items():
        print("  бэкап заменённых файлов: %s" % b)
    if "framework" in products:
        print("  Перезапусти CLI. В Claude Code проверь: /develop, /common-master-prompt, "
              "/ultraprompt, /version-test и скиллы commoncode:*.")
        if "codex" in clis:
            print("  В Codex скиллы видны как $commoncode-*, промпт /develop — в prompts/.")
        if "kilo" in clis:
            print("  В Kilo Code: /develop из workflows/, правила в rules/, скиллы в skills/.")
        if "opencode" in clis:
            print("  В OpenCode: /develop из commands/, правила AGENTS.md, скиллы в skills/.")
        if "cursor" in clis:
            print("  В Cursor: скиллы в ~/.cursor/skills, /develop — скилл; правила положи в AGENTS.md проекта.")
        if "antigravity" in clis:
            print("  В Antigravity: правила в ~/.gemini/GEMINI.md, скиллы в ~/.gemini/config/skills.")
    if "usage" in products:
        if "statusline" in us_blocks:
            print("  Статуслайн появится после перезапуска Claude Code (или /statusline).")
        if "cctok" in us_blocks or "pipeline" in us_blocks:
            if str(BIN_DIR) not in os.environ.get("PATH", "").split(os.pathsep):
                print(c(YELLOW, "  %s нет в PATH — добавь: export PATH=\"%s:$PATH\"" % (BIN_DIR, BIN_DIR)))
        print("  Лимиты подписки для полосок 5h / неделя — в %s/statusline.json." % CLAUDE_DIR)
        print("  Проверка: python3 %s/cc_statusline.py --demo · cctok · pipeline demo" % CLAUDE_DIR)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(130)
