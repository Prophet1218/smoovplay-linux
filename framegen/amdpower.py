"""Linux, AMD cards: keep the graphics card's clocks up while SmoovPlay plays.

SmoovPlay's load comes in bursts: each 33 ms a game frame arrives, the card works for ~20 ms, then waits. amdgpu's
power management reads the idle part as a light load and lowers the clocks, so the next frame starts slow. On an
RX 9070 XT that cost ~5 ms a generated frame (25.4 -> 20.2 ms, p50) and as much again in delay. Setting the card's
power_dpm_force_performance_level to "high" for the session keeps its clocks up; leaving puts back what was there.

The file belongs to root. If SmoovPlay can't write it, it says once how to allow it (scripts/amd_power_udev.sh adds
a udev rule that lets the 'render' group write it), and plays on with the card managing its own clocks.
"""
from __future__ import annotations

import atexit
import glob
import os

LEVEL = "power_dpm_force_performance_level"
AMD = "0x1002"


def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def find_card() -> str | None:
    """The sysfs device folder of the AMD card with the most video memory (the discrete card, not a CPU's built-in
    graphics, which reports little or none)."""
    best, best_vram = None, -1
    for dev in glob.glob("/sys/class/drm/card[0-9]*/device"):
        if _read(os.path.join(dev, "vendor")) != AMD or not os.path.exists(os.path.join(dev, LEVEL)):
            continue
        try:
            vram = int(_read(os.path.join(dev, "mem_info_vram_total")) or 0)
        except ValueError:
            vram = 0
        if vram > best_vram:
            best, best_vram = dev, vram
    return best


class ClocksHigh:
    """Sets the card's performance level to "high"; restore() (also run at exit) puts back the level it found."""

    def __init__(self) -> None:
        self.dev = find_card()
        self.path = os.path.join(self.dev, LEVEL) if self.dev else None
        self.before: str | None = None
        self.why = ""
        if self.path is None:
            self.why = "no AMD card with power management found"
            return
        self.before = _read(self.path) or "auto"
        if self.before == "high":
            return  # already set (by the user, or a session that didn't get to restore it)
        try:
            with open(self.path, "w") as f:
                f.write("high")
        except OSError as e:
            self.why = f"{self.path} isn't writable ({e.strerror})"
            self.before = None
            return
        atexit.register(self.restore)

    @property
    def on(self) -> bool:
        return self.path is not None and _read(self.path) == "high"

    def restore(self) -> None:
        if self.path and self.before and self.before != "high":
            try:
                with open(self.path, "w") as f:
                    f.write(self.before)
            except OSError:
                pass
            self.before = None


def keep_clocks_high() -> ClocksHigh:
    clocks = ClocksHigh()
    if clocks.on:
        print(f"[run] AMD clocks: held high while playing ({os.path.basename(os.path.dirname(clocks.dev))}), "
              f"back to '{clocks.before or 'high'}' on exit")
    else:
        print(f"[run] AMD clocks: managed by the card ({clocks.why}). Holding them high saves ~5 ms a generated "
              "frame; to allow it once: sudo bash scripts/amd_power_udev.sh")
    return clocks
