#!/usr/bin/env bash
# Builds chiaki-ng with SmoovPlay's frame tap on CachyOS / Arch, in one go:
#
#   bash scripts/setup_chiaki_cachyos.sh
#
# chiaki_tap/build_linux.sh is written for Fedora 44, so it runs in a Fedora 44 distrobox (podman). The container
# shares your home folder, /dev/dri (the graphics card) and /dev/shm (the frame tap's shared memory), so chiaki-ng
# runs in it while SmoovPlay runs on CachyOS itself. Takes 20-40 minutes the first time (FFmpeg, libplacebo, Qt
# packages); running it again only rebuilds what's missing. Then: bash scripts/play_linux.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOX=smoovplay
IMAGE=registry.fedoraproject.org/fedora-toolbox:44
SRC="$HOME/src/chiaki-ng"
OUT="$HOME/src/chiaki-ng-frametap"
TAG=v1.10.1

step() { echo; echo "=== $*"; }

step "distrobox and podman"
sudo pacman -S --needed --noconfirm distrobox podman

if ! distrobox list 2>/dev/null | grep -qw "$BOX"; then
    step "Fedora 44 container '$BOX'"
    distrobox create --yes --name "$BOX" --image "$IMAGE"
fi

if [ ! -d "$SRC/.git" ]; then
    step "chiaki-ng $TAG source"
    mkdir -p "$(dirname "$SRC")"
    git clone --recursive -b "$TAG" https://github.com/streetpea/chiaki-ng.git "$SRC"
fi

step "build (in the container; asks for your password once for its dnf)"
distrobox enter "$BOX" -- bash "$REPO/chiaki_tap/build_linux.sh" "$SRC" "$OUT"

# A Flatpak chiaki-ng's settings (a registered PS5 among them) save registering again.
FLATPAK_CFG="$HOME/.var/app/io.github.streetpea.Chiaki4deck/config/Chiaki"
if [ -d "$FLATPAK_CFG" ] && [ ! -d "$HOME/.config/Chiaki" ]; then
    step "copying the Flatpak chiaki-ng's settings"
    mkdir -p "$HOME/.config"
    cp -r "$FLATPAK_CFG" "$HOME/.config/Chiaki"
fi

echo
echo "Done: $OUT/gui/chiaki"
echo "Play: bash scripts/play_linux.sh"
