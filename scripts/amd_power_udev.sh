#!/usr/bin/env bash
# Lets SmoovPlay hold an AMD card's clocks high while it plays (framegen/amdpower.py), without running it as root.
# Adds a udev rule that gives the 'render' group write access to each amdgpu card's
# power_dpm_force_performance_level, and applies it now. Undo: sudo rm /etc/udev/rules.d/70-smoovplay-amdgpu.rules
#
#   sudo bash scripts/amd_power_udev.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run it with sudo: sudo bash $0" >&2
    exit 1
fi

RULE=/etc/udev/rules.d/70-smoovplay-amdgpu.rules
cat > "$RULE" <<'EOF'
# SmoovPlay: the 'render' group may set amdgpu's performance level (held "high" while SmoovPlay plays)
ACTION=="add|change", SUBSYSTEM=="drm", KERNEL=="card[0-9]*", DRIVERS=="amdgpu", RUN+="/bin/sh -c 'f=/sys%p/device/power_dpm_force_performance_level; [ -e $$f ] && chgrp render $$f && chmod g+w $$f'"
EOF
echo "Wrote $RULE"

udevadm control --reload
udevadm trigger --subsystem-match=drm --action=change
sleep 1
ls -l /sys/class/drm/card[0-9]*/device/power_dpm_force_performance_level 2>/dev/null || true
echo "Done. Your user needs to be in the 'render' group (check with: groups)."
