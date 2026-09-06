#!/usr/bin/env bash
# Compatibility wrapper: the old "restore everything" behaviour.
# Equivalent to:  python3 setup.py --all --yes
# For the interactive installer run ./setup.sh instead.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/setup.py" --all --yes "$@"
