#!/usr/bin/env bash
# Lossless Scaling's frame generation (lsfg-vk) on the Flatpak chiaki-ng, on CachyOS / Arch.
#
#   bash scripts/setup_lsfg_chiaki.sh
#
# Before: own Lossless Scaling on Steam and switch it to the "lsfg-vk" branch (Steam: Lossless Scaling ->
# Properties -> Betas -> lsfg-vk), and let it download. After: lsfg-vk-ui, make a profile named "chiaki"
# (multiplier 2), then: flatpak run io.github.streetpea.Chiaki4deck
#
# What it does: installs lsfg-vk (UI and CLI) from the AUR, the Flatpak chiaki-ng and lsfg-vk's Vulkan layer for
# Flatpak runtimes, lets chiaki-ng read lsfg-vk's config and the Steam folder, turns the "chiaki" profile on for it,
# and copies the settings (registered PS5) from the chiaki-ng built for SmoovPlay, if the Flatpak has none.
# Following lsfg-vk's docs: https://lsfg-vk.dev/docs/installation/ and .../installation/flatpak/
set -euo pipefail

APP=io.github.streetpea.Chiaki4deck
STEAM_COMMON="$HOME/.local/share/Steam/steamapps/common"
step() { echo; echo "=== $*"; }

if [ ! -d "$STEAM_COMMON/Lossless Scaling" ]; then
    echo "Lossless Scaling isn't in $STEAM_COMMON." >&2
    echo "Install it in Steam and switch it to the lsfg-vk branch (Properties -> Betas), then run this again." >&2
    exit 1
fi

step "lsfg-vk (AUR) and its UI's Qt packages"
sudo pacman -S --needed --noconfirm qt6-declarative qt6-base flatpak
if command -v lsfg-vk-ui >/dev/null; then
    echo "already installed"
elif command -v paru >/dev/null; then
    paru -S --needed lsfg-vk-bin
elif command -v yay >/dev/null; then
    yay -S --needed lsfg-vk-bin
else
    echo "No AUR helper (paru or yay). Install one, or lsfg-vk from https://builds.lsfg-vk.dev into ~/.local" >&2
    exit 1
fi

step "Flathub (user) and the Flatpak chiaki-ng"
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user -y --noninteractive flathub "$APP" || flatpak info "$APP" >/dev/null

step "lsfg-vk's Vulkan layer for Flatpak runtimes"
for v in 24.08 25.08; do
    flatpak install --user -y --noninteractive flathub "org.freedesktop.Platform.VulkanLayer.lsfgvk//$v" ||
        echo "(runtime $v: not installed, fine if chiaki-ng doesn't use it)"
done

step "permissions and the profile for chiaki-ng"
mkdir -p "$HOME/.config/lsfg-vk"
flatpak override --user --filesystem="$HOME/.config/lsfg-vk:rw" "$APP"
flatpak override --user --filesystem="$STEAM_COMMON:ro" "$APP"
flatpak override --user --env=LSFGVK_CONFIG="$HOME/.config/lsfg-vk/conf.toml" "$APP"
flatpak override --user --env=LSFGVK_PROFILE=chiaki "$APP"

FLATPAK_CFG="$HOME/.var/app/$APP/config/Chiaki"
if [ -d "$HOME/.config/Chiaki" ] && [ ! -d "$FLATPAK_CFG" ]; then
    step "copying chiaki-ng's settings (registered PS5) into the Flatpak"
    mkdir -p "$(dirname "$FLATPAK_CFG")"
    cp -r "$HOME/.config/Chiaki" "$FLATPAK_CFG"
fi

echo
echo "Done. Next:"
echo "  1. lsfg-vk-ui   -> make a profile named exactly: chiaki   (multiplier 2, flow scale 1.0), save"
echo "  2. flatpak run $APP"
