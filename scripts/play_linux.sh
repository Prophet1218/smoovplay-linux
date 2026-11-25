#!/usr/bin/env bash
# Starts PS5 Remote Play with SmoovPlay on Linux: chiaki-ng with the frame tap (in the 'smoovplay' distrobox that
# scripts/setup_chiaki_cachyos.sh made), then run.py --chiaki --display. Extra arguments go to run.py:
#
#   bash scripts/play_linux.sh
#   bash scripts/play_linux.sh --hz 90
#
# In chiaki-ng: 1080p, 60 fps, H.265, then connect to the PS5. Esc in SmoovPlay's window quits both.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOX=smoovplay
CHIAKI="$HOME/src/chiaki-ng-frametap/gui/chiaki"
cd "$REPO"

if [ ! -x "$CHIAKI" ]; then
    echo "chiaki-ng with the frame tap isn't built yet: bash scripts/setup_chiaki_cachyos.sh" >&2
    exit 1
fi

if command -v distrobox >/dev/null && distrobox list 2>/dev/null | grep -qw "$BOX"; then
    distrobox enter "$BOX" -- env CHIAKI_FRAMETAP=1 "$CHIAKI" >/tmp/chiaki-frametap.log 2>&1 &
else
    CHIAKI_FRAMETAP=1 "$CHIAKI" >/tmp/chiaki-frametap.log 2>&1 &
fi
CHIAKI_PID=$!
echo "[play] chiaki-ng started (log: /tmp/chiaki-frametap.log)"

stop_chiaki() {
    pkill -9 -f "chiaki-ng-frametap/gui/chiaki" 2>/dev/null
    kill -9 "$CHIAKI_PID" 2>/dev/null
}
trap stop_chiaki EXIT

PYGLFW_LIBRARY_VARIANT=wayland "$REPO/.venv/bin/python" run.py --chiaki --display "$@"
