#!/usr/bin/env bash
# Common bundle — bootstrap for the interactive installer.
#
#   From a clone:          ./setup.sh
#   Straight from GitHub:  curl -fsSL https://raw.githubusercontent.com/commonkid/common-framework/main/setup.sh | bash
#
# The one-liner clones the repository into $COMMON_FRAMEWORK_HOME
# (default ~/.common-framework), keeps it updated with `git pull` on later
# runs, and hands over to setup.py. All setup.py flags pass through:
#   ./setup.sh --all --yes         everything, no questions
#   ./setup.sh --dry-run           show the plan only
#   ./setup.sh --list              block catalogue
set -euo pipefail

REPO_URL="${COMMON_FRAMEWORK_REPO:-https://github.com/commonkid/common-framework.git}"
SRC=""

# 1. Running from inside a checkout?
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  d="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  [ -f "$d/setup.py" ] && SRC="$d"
fi

# 2. Otherwise fetch / refresh the repository.
if [ -z "$SRC" ]; then
  SRC="${COMMON_FRAMEWORK_HOME:-$HOME/.common-framework}"
  if ! command -v git >/dev/null 2>&1; then
    echo "git не найден — установи git или скачай архив репозитория и запусти python3 setup.py" >&2
    exit 1
  fi
  if [ -d "$SRC/.git" ]; then
    echo "==> обновляю $SRC"
    git -C "$SRC" pull --ff-only --quiet || echo "    (git pull не удался — использую то, что есть)"
  else
    echo "==> клонирую $REPO_URL → $SRC"
    git clone --depth 1 --quiet "$REPO_URL" "$SRC"
  fi
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 не найден — нужен Python 3.8+" >&2
  exit 1
fi

# 3. Hand over. When piped through bash, stdin is the script itself, so give
#    the installer the real terminal for its menus.
if [ -t 0 ]; then
  exec python3 "$SRC/setup.py" "$@"
elif ( exec </dev/tty ) 2>/dev/null; then
  exec python3 "$SRC/setup.py" "$@" </dev/tty
else
  echo "==> терминал недоступен — ставлю без вопросов (--yes)"
  exec python3 "$SRC/setup.py" --yes "$@"
fi
