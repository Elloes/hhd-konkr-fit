#!/usr/bin/env bash
#
# Handheld Daemon (hhd-konkr-fit) — universal one-command installer
#
# Installs the hhd-konkr-fit fork (Ayaneo Konkr Fit HX370/HX470 optimized
# Handheld Daemon) to ~/.local/share/hhd with zero manual steps:
#   * detects the distro and package manager,
#   * checks and installs missing dependencies,
#   * installs udev rules + hwdb + the hhd_local@ systemd service
#     (bundled in this repository, no upstream downloads needed),
#   * downloads the gamescope overlay UI (hhd-ui) AppImage,
#   * enables and starts the service,
#   * verifies the installation.
#
# Supported distros (best effort everywhere else):
#   SteamOS, Bazzite, CachyOS, Anatase OS, Fedora / Red Hat / CentOS family,
#   Arch / Manjaro family, Debian / Ubuntu / Mint family, Void Linux.
#
# Usage:
#   curl -L https://github.com/Elloes/hhd-konkr-fit/raw/master/install.sh | bash
#
# Optional environment overrides:
#   HHD_FORK_REPO   Fork repository to install from
#                   (default: https://github.com/Elloes/hhd-konkr-fit)
#   HHD_FORK_SRC    Use an existing local checkout of the fork instead of
#                   cloning (must contain pyproject.toml and src/hhd).
#   HHD_KEEP_DISTRO_HHD  set to "1" to NOT stop/disable a distro-provided
#                   `hhd@` service (Anatase).

set -Eeuo pipefail

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
FORK_REPO="${HHD_FORK_REPO:-https://github.com/Elloes/hhd-konkr-fit}"
UI_RELEASES_API="https://api.github.com/repos/hhd-dev/hhd-ui/releases/latest"
INSTALL_DIR="$HOME/.local/share/hhd"
SRC_DIR="$INSTALL_DIR/src"
VENV_DIR="$INSTALL_DIR/venv"
BIN_LINK_DIR="$HOME/.local/bin"
SERVICE_NAME="hhd_local@$(id -un)"

log()  { printf '\033[1;34m[hhd-install]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[hhd-install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[hhd-install]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[hhd-install] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# rm_rf <path> — remove a path even if it contains root-owned files
# (e.g. a previous install that was run as root/sudo).
rm_rf() {
    rm -rf "$1" 2>/dev/null || $SUDO rm -rf "$1"
}

# --------------------------------------------------------------------------
# Root / privilege handling
# --------------------------------------------------------------------------
if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
    warn "Running as root: installing for root's \$HOME."
else
    SUDO="sudo"
    command -v sudo >/dev/null 2>&1 || die "Not running as root and 'sudo' is unavailable."
fi
# Prompt once for the whole run.
$SUDO -v

# --------------------------------------------------------------------------
# Distro / package manager detection
# --------------------------------------------------------------------------
OS_ID="unknown"
OS_ID_LIKE=""
if [ -r /etc/os-release ]; then
    OS_ID=$(. /etc/os-release && printf '%s' "${ID:-unknown}")
    OS_ID_LIKE=$(. /etc/os-release && printf '%s' "${ID_LIKE:-}")
fi

PKG_MANAGER=""
case "$OS_ID" in
    steamos|bazzite|rhel|centos|fedora|anolis|nobara|bluefin)
        PKG_MANAGER="dnf" ;;
    arch|manjaro|cachyos|garuda|endeavouros|artix|arcolinux)
        PKG_MANAGER="pacman" ;;
    debian|ubuntu|mint|pop|zorin|raspbian|kali|elementary|system76)
        PKG_MANAGER="apt" ;;
    void)
        PKG_MANAGER="xbps" ;;
    opensuse-tumbleweed|opensuse-leap|suse)
        PKG_MANAGER="zypper" ;;
    *)
        for c in dnf pacman xbps-install apt zypper; do
            if command -v "$c" >/dev/null 2>&1; then PKG_MANAGER="$c"; break; fi
        done
        ;;
esac
# Fall back to matching against ID_LIKE (e.g. anatase, rhel-derivative, etc.)
if [ -z "$PKG_MANAGER" ]; then
    for like in ${OS_ID_LIKE// / }; do
        case "$like" in
            *fedora*|*rhel*|*centos*) PKG_MANAGER="dnf" ;;
            *arch*|*manjaro*)         PKG_MANAGER="pacman" ;;
            *debian*|*ubuntu*)        PKG_MANAGER="apt" ;;
            *suse*)                   PKG_MANAGER="zypper" ;;
        esac
        [ -n "$PKG_MANAGER" ] && break
    done
fi
[ -n "$PKG_MANAGER" ] || die "Could not detect a package manager (dnf/pacman/xbps/apt/zypper)."

# ostree (SteamOS, Bazzite, Bluefin, ...) — /etc is a read-only overlay.
IS_OSTREE=0
[ -f /run/ostree-booted ] && IS_OSTREE=1

log "Detected distro: '$OS_ID' (ID_LIKE: '${OS_ID_LIKE:-n/a}'), package manager: $PKG_MANAGER, ostree: $IS_OSTREE"

PKG_FLAG=""
case "$PKG_MANAGER" in
    apt) PKG_FLAG="-y" ;;
    pacman) PKG_FLAG="--noconfirm" ;;
esac

# install_packages <pkg|tool>... — installs only the missing tools/binaries.
install_packages() {
    local pkg pm_pkg tool missing=()
    for pkg in "$@"; do
        pm_pkg="${pkg%|*}"; tool="${pkg#*|}"
        [ "$tool" = "$pkg" ] && tool="$pm_pkg"
        command -v "$tool" >/dev/null 2>&1 || missing+=("$pm_pkg")
    done
    [ ${#missing[@]} -eq 0 ] && return 0
    missing=($(printf '%s\n' "${missing[@]}" | sort -u))
    log "Installing missing dependencies: ${missing[*]}"
    case "$PKG_MANAGER" in
        dnf)      $SUDO dnf install -y "${missing[@]}" ;;
        pacman)   $SUDO pacman -S --needed $PKG_FLAG "${missing[@]}" ;;
        apt)      $SUDO apt-get update -qq && $SUDO apt-get install -qq $PKG_FLAG "${missing[@]}" ;;
        zypper)   $SUDO zypper --non-interactive install "${missing[@]}" ;;
        xbps-install) $SUDO xbps-install -Sy "${missing[@]}" || $SUDO xbps-install -y "${missing[@]}" ;;
        *)        die "Unsupported package manager: $PKG_MANAGER" ;;
    esac
}

# The venv-module package name varies by family.
case "$PKG_MANAGER" in
    pacman) VENV_PKG="python|python3" ;;
    *)      VENV_PKG="python3-venv|python3" ;;
esac

install_packages "$VENV_PKG" "git|git" "curl|curl" "ca-certificates|curl"

# Sanity: python3 + venv module must exist now.
command -v python3 >/dev/null 2>&1 || die "python3 is required but was not found."
python3 -c 'import ensurepip' >/dev/null 2>&1 \
    || warn "python3-venv/ensurepip may be missing; venv creation could fail."
# --------------------------------------------------------------------------
# Source code (self-hosted fork)
# --------------------------------------------------------------------------
if [ -n "${HHD_FORK_SRC:-}" ]; then
    [ -f "$HHD_FORK_SRC/pyproject.toml" ] && [ -d "$HHD_FORK_SRC/src/hhd" ] \
        || die "HHD_FORK_SRC=$HHD_FORK_SRC is not a valid hhd-konkr-fit checkout."
    SRC_DIR="$HHD_FORK_SRC"
    log "Using local fork checkout at $SRC_DIR"
elif [ -f "$HOME/pyproject.toml" ] && [ -d "$HOME/src/hhd" ] && [ -d "$HOME/.git" ]; then
    SRC_DIR="$HOME"
    log "Running from a local fork checkout — using $SRC_DIR"
else
    mkdir -p "$INSTALL_DIR"
    if [ -d "$SRC_DIR/.git" ]; then
        log "Updating existing fork checkout at $SRC_DIR"
        git -C "$SRC_DIR" fetch --depth 1 origin \
            && git -C "$SRC_DIR" reset --hard FETCH_HEAD
    else
        rm_rf "$SRC_DIR"
        log "Cloning $FORK_REPO (shallow) to $SRC_DIR"
        git clone --depth 1 "$FORK_REPO" "$SRC_DIR"
    fi
fi

# Ensure the current user owns the source tree (an older test install may
# have been done as root), so git/pip/rm below can operate on it.
$SUDO chown -R "$(id -un):" "$SRC_DIR"

# --------------------------------------------------------------------------
# Python environment
# --------------------------------------------------------------------------
log "Creating virtualenv at $VENV_DIR"
rm_rf "$VENV_DIR"
python3 -m venv --system-site-packages "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
log "Installing hhd-konkr-fit (hhd + bundled adjustor) into the virtualenv"
"$VENV_DIR/bin/pip" install --quiet --upgrade "$SRC_DIR"

# --------------------------------------------------------------------------
# udev rules, hwdb and systemd service (bundled in the fork — self-hosted)
# --------------------------------------------------------------------------
log "Installing udev rules, hwdb and systemd service unit"
$SUDO install -d /etc/udev/rules.d /etc/udev/hwdb.d
$SUDO install -m 0644 "$SRC_DIR/usr/lib/udev/rules.d/83-hhd.rules" /etc/udev/rules.d/83-hhd.rules
$SUDO install -m 0644 "$SRC_DIR/usr/lib/udev/hwdb.d/83-hhd.hwdb"   /etc/udev/hwdb.d/83-hhd.hwdb
if command -v udevadm >/dev/null 2>&1; then
    $SUDO udevadm hwdb --update || warn "udevadm hwdb --update failed (non-fatal)."
fi
$SUDO install -m 0644 "$SRC_DIR/usr/lib/systemd/system/hhd_local@.service" \
    /etc/systemd/system/hhd_local@.service

# --------------------------------------------------------------------------
# User PATH links
# --------------------------------------------------------------------------
mkdir -p "$BIN_LINK_DIR"
for name in hhd hhd.contrib hhdctl; do
    [ -x "$VENV_DIR/bin/$name" ] && ln -sf "$VENV_DIR/bin/$name" "$BIN_LINK_DIR/$name"
done

# --------------------------------------------------------------------------
# Gamescope overlay UI (hhd-ui AppImage, published upstream)
# --------------------------------------------------------------------------
log "Downloading the hhd-ui gamescope overlay"
ui_url=$(curl -fsSL "$UI_RELEASES_API" | grep "browser_download_url" | cut -d '"' -f 4 \
    | grep "hhd-ui.AppImage" | head -n1)
[ -n "$ui_url" ] \
    && curl -fsSL -o "$BIN_LINK_DIR/hhd-ui" "$ui_url" \
    && chmod +x "$BIN_LINK_DIR/hhd-ui" \
    || warn "Could not download the hhd-ui overlay (non-fatal — you can grab it later from the hhd-dev/hhd-ui releases)."

# --------------------------------------------------------------------------
# Distro-provided hhd (Anatase preinstalls Handheld Daemon)
# --------------------------------------------------------------------------
if [ "${HHD_KEEP_DISTRO_HHD:-0}" != "1" ]; then
    if command -v systemctl >/dev/null 2>&1 \
        && $SUDO systemctl list-unit-files 2>/dev/null | grep -q "^hhd@"; then
        case "$OS_ID" in
            *anatase*) warn "Anatase OS detected: distro Handheld Daemon is preinstalled." ;;
        esac
        log "Stopping/disabling the distro-provided hhd@ service to avoid conflicts"
        $SUDO systemctl disable --now "hhd@$(id -un)" 2>/dev/null || true
        $SUDO systemctl disable --now "hhd" 2>/dev/null || true
    fi
fi

# --------------------------------------------------------------------------
# SELinux (enforcing): label the venv binaries
# --------------------------------------------------------------------------
if [ -f /sys/fs/selinux/enforce ] && [ "$(cat /sys/fs/selinux/enforce)" != "0" ] \
    && command -v semanage >/dev/null 2>&1; then
    log "SELinux is enforcing: relabeling hhd venv binaries"
    user_home_dir=$(readlink -f "$HOME")
    $SUDO semanage fcontext -a -t bin_t "$user_home_dir/.local/share/hhd/venv/bin/.*" 2>/dev/null || true
    $SUDO restorecon -Rv "$user_home_dir/.local/share/hhd/venv/bin/" || warn "restorecon failed (non-fatal)."
fi

# --------------------------------------------------------------------------
# systemd service
# --------------------------------------------------------------------------
if command -v systemctl >/dev/null 2>&1; then
    log "Enabling and starting the $SERVICE_NAME service"
    $SUDO systemctl daemon-reload
    $SUDO systemctl enable --now "$SERVICE_NAME"
else
    warn "systemd not found — run '$VENV_DIR/bin/hhd --user $(id -un)' manually."
fi

# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------
log "Verifying the installation"
installed_version=$("$VENV_DIR/bin/python" -c \
    "import hhd, adjustor, importlib.metadata; print(importlib.metadata.version('hhd'))") \
    || die "Verification failed: the hhd package could not be imported."
if command -v systemctl >/dev/null 2>&1; then
    $SUDO systemctl is-active --quiet "$SERVICE_NAME" \
        && service_state="running" \
        || service_state="not running (start it with: $SUDO systemctl start $SERVICE_NAME)"
else
    service_state="n/a"
fi

echo
echo "============================================================"
ok "Handheld Daemon (hhd-konkr-fit) $installed_version installed successfully."
echo "    Source:      $SRC_DIR"
echo "    Service:     $SERVICE_NAME ($service_state)"
echo "    UI overlay:  $BIN_LINK_DIR/hhd-ui"
echo
echo "    Konkr Fit (HX370/HX470) support, power profiles and the"
echo "    self-hosted update channel are now active."
echo "============================================================"
echo
log "Done! Launch any game and double-tap the side button for the overlay,"
log "or run 'hhdctl' from a terminal. No reboot required."

