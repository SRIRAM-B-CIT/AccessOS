#!/usr/bin/env bash
# ==============================================================================
# AccessOS Standalone Bootable ISO Build & Mastering Pipeline
# ==============================================================================
# Builds a standalone hybrid bootable AccessOS ISO from Linux Mint 22.3 Xfce.
# 100% UNPRIVILEGED: Runs without sudo or root on the development host.
# DOES NOT modify host bootloader, partitions, or installed operating system.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="/mnt/1208154E081531E9/AccessOS"
BUILD_DIR="$WORK_DIR/iso_build"
ISO_ROOT="$BUILD_DIR/iso_root"
SQUASH_ROOT="$BUILD_DIR/squashfs_root"
TOOLS_DIR="$BUILD_DIR/tools"
SOURCE_ISO="$WORK_DIR/linuxmint-22.3-xfce-64bit.iso"
OUTPUT_ISO="$WORK_DIR/AccessOS.iso"
OUTPUT_SHA="$WORK_DIR/AccessOS.iso.sha256"

# Color logging
log()   { printf "\033[1;34m[AccessOS Build]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[AccessOS Warning]\033[0m %s\n" "$*"; }
err()   { printf "\033[1;31m[AccessOS Error]\033[0m %s\n" "$*" >&2; exit 1; }

log "Starting AccessOS ISO remastering pipeline..."

# ── 1. Tooling & Prerequisites ────────────────────────────────────────────────
command -v 7z >/dev/null 2>&1 || err "7z (p7zip-full) is required."
command -v mksquashfs >/dev/null 2>&1 || err "mksquashfs (squashfs-tools) is required."
command -v unsquashfs >/dev/null 2>&1 || err "unsquashfs (squashfs-tools) is required."

# Verify unprivileged xorriso
XORRISO_BIN="$TOOLS_DIR/bin/xorriso"
if [ ! -x "$XORRISO_BIN" ]; then
    err "Unprivileged xorriso binary not found at $XORRISO_BIN"
fi
export LD_LIBRARY_PATH="$TOOLS_DIR/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"

[ -f "$SOURCE_ISO" ] || err "Source ISO not found: $SOURCE_ISO"

mkdir -p "$BUILD_DIR" "$ISO_ROOT" "$TOOLS_DIR"

# ── 2. Unpack ISO Root ────────────────────────────────────────────────────────
if [ ! -f "$ISO_ROOT/casper/filesystem.squashfs" ]; then
    log "Unpacking source ISO root directory..."
    rm -rf "$ISO_ROOT"
    mkdir -p "$ISO_ROOT"
    7z x -y "$SOURCE_ISO" -o"$ISO_ROOT" >/dev/null
    log "ISO root unpacked successfully."
else
    log "ISO root directory already present, skipping unpack."
fi

# ── 3. Unpack SquashFS Root ────────────────────────────────────────────────────
if [ ! -d "$SQUASH_ROOT/usr" ]; then
    log "Unsquashing casper/filesystem.squashfs..."
    rm -rf "$SQUASH_ROOT"
    unsquashfs -d "$SQUASH_ROOT" "$ISO_ROOT/casper/filesystem.squashfs" >/dev/null || true
    log "SquashFS root unpacked."
else
    log "SquashFS root already unpacked, proceeding with customizations."
fi

# ── 4. Customize SquashFS Root ─────────────────────────────────────────────────
log "Applying AccessOS dedicated operating environment customizations..."

# 4.1 Install AccessOS to /opt/accessos
log "Installing AccessOS application to /opt/accessos..."
mkdir -p "$SQUASH_ROOT/opt/accessos"
rsync -a --exclude='.git' --exclude='iso_build' --exclude='tests' \
    --exclude='__pycache__' --exclude='*.pyc' \
    "$REPO_DIR/" "$SQUASH_ROOT/opt/accessos/"

# 4.2 Sync pre-installed Python dependencies to system dist-packages
log "Syncing pre-installed Python ML/CV dependencies to system dist-packages..."
mkdir -p "$SQUASH_ROOT/usr/local/lib/python3.12/dist-packages"
if [ -d "$REPO_DIR/.venv/lib/python3.12/site-packages" ]; then
    rsync -a "$REPO_DIR/.venv/lib/python3.12/site-packages/" "$SQUASH_ROOT/usr/local/lib/python3.12/dist-packages/"
fi

# 4.3 Install Launcher & Dedicated Session Scripts
log "Installing /usr/local/bin/accessos and /usr/local/bin/accessos-session..."
cat << 'RUNNER_EOF' > "$SQUASH_ROOT/usr/local/bin/accessos"
#!/usr/bin/env bash
export ACCESSOS_BASE_DIR="/opt/accessos"
export PYTHONPATH="/opt/accessos:/usr/local/lib/python3.12/dist-packages:$PYTHONPATH"

# Auto-detect profile on live boot unless explicitly overridden
if [ -z "${ACCESSOS_PROFILE:-}" ]; then
    export ACCESSOS_PROFILE="vm-real"
fi

exec /usr/bin/python3 -m accessos "$@"
RUNNER_EOF
chmod +x "$SQUASH_ROOT/usr/local/bin/accessos"

cat << 'SESSION_EOF' > "$SQUASH_ROOT/usr/local/bin/accessos-session"
#!/usr/bin/env bash
# AccessOS Dedicated Desktop Session Manager
export ACCESSOS_BASE_DIR="/opt/accessos"
export PYTHONPATH="/opt/accessos:/usr/local/lib/python3.12/dist-packages:$PYTHONPATH"
export ACCESSOS_PROFILE="vm-real"
export ACCESSOS_WINDOWED="0"

# Dark background
xsetroot -solid "#121316" 2>/dev/null || true

# Start window manager (xfwm4) in background so application windows have clean decorations
if command -v xfwm4 >/dev/null 2>&1; then
    xfwm4 --compositor=off --replace &
fi

# Run AccessOS as the main foreground desktop environment
exec /usr/bin/python3 -m accessos --fullscreen
SESSION_EOF
chmod +x "$SQUASH_ROOT/usr/local/bin/accessos-session"

# 4.4 Configure Dedicated LightDM Session (NO Mint Desktop)
log "Configuring dedicated AccessOS desktop session in LightDM..."
mkdir -p "$SQUASH_ROOT/usr/share/xsessions"
cat << 'XSESSION_EOF' > "$SQUASH_ROOT/usr/share/xsessions/accessos.desktop"
[Desktop Entry]
Name=AccessOS
Comment=AccessOS Dedicated Accessible Environment
Exec=/usr/local/bin/accessos-session
Type=Application
DesktopNames=AccessOS
XSESSION_EOF

mkdir -p "$SQUASH_ROOT/etc/lightdm/lightdm.conf.d"
cat << 'LIGHTDM_EOF' > "$SQUASH_ROOT/etc/lightdm/lightdm.conf.d/70-linuxmint.conf"
[Seat:*]
user-session=accessos
autologin-user=mint
autologin-user-timeout=0
LIGHTDM_EOF

# 4.5 Prune Non-Essential Clutter & Ubiquity Installer
log "Pruning non-essential desktop launchers and disk installer..."
CLUTTER_PATTERNS=(
    "libreoffice*"
    "thunderbird*"
    "hexchat*"
    "mintwelcome*"
    "mintupdate*"
    "mintinstall*"
    "gnome-mines*"
    "gnome-sudoku*"
    "solitaire*"
    "simple-scan*"
    "redshift*"
    "drawing*"
    "ubiquity*"
)
for pat in "${CLUTTER_PATTERNS[@]}"; do
    find "$SQUASH_ROOT/usr/share/applications" -name "$pat" -exec rm -f {} + 2>/dev/null || true
done
rm -f "$SQUASH_ROOT/etc/xdg/autostart/ubiquity-mint.desktop" \
      "$SQUASH_ROOT/usr/share/applications/ubiquity.desktop" 2>/dev/null || true

# 4.6 Hide Desktop Icons
log "Configuring Xfce desktop properties..."
mkdir -p "$SQUASH_ROOT/etc/xdg/xfce4/xfconf/xfce-perchannel-xml"
cat << 'XFCE_DESK_EOF' > "$SQUASH_ROOT/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml"
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-desktop" version="1.0">
  <property name="desktop-icons" type="empty">
    <property name="style" type="int" value="0"/>
  </property>
</channel>
XFCE_DESK_EOF

# 4.7 Update OS Release Metadata
log "Updating OS release branding..."
cat << 'OS_EOF' > "$SQUASH_ROOT/etc/os-release"
NAME="AccessOS"
VERSION="1.0 (Accessible Operating System)"
ID=accessos
ID_LIKE="linuxmint ubuntu debian"
PRETTY_NAME="AccessOS 1.0 (Accessible 64-bit)"
VERSION_ID="1.0"
HOME_URL="https://github.com/SRIRAM-B-CIT/AccessOS"
SUPPORT_URL="https://github.com/SRIRAM-B-CIT/AccessOS/issues"
BUG_REPORT_URL="https://github.com/SRIRAM-B-CIT/AccessOS/issues"
PRIVACY_POLICY_URL="https://github.com/SRIRAM-B-CIT/AccessOS"
UBUNTU_CODENAME=noble
OS_EOF

echo "AccessOS 1.0 \n \l" > "$SQUASH_ROOT/etc/issue"
echo "AccessOS 1.0" > "$SQUASH_ROOT/etc/issue.net"

# ── 5. Repack SquashFS Root ────────────────────────────────────────────────────
log "Repacking casper/filesystem.squashfs (this will take ~2-3 minutes)..."
rm -f "$ISO_ROOT/casper/filesystem.squashfs"
mksquashfs "$SQUASH_ROOT" "$ISO_ROOT/casper/filesystem.squashfs" \
    -comp xz -b 1048576 -noappend -all-root

# Update filesystem size
printf $(du -sx --block-size=1 "$SQUASH_ROOT" | cut -f1) > "$ISO_ROOT/casper/filesystem.size"

# ── 6. Master Bootable ISO with xorriso ─────────────────────────────────────────
log "Mastering standalone bootable AccessOS hybrid ISO..."
rm -f "$OUTPUT_ISO"

"$XORRISO_BIN" -as mkisofs \
    -r -V "AccessOS 1.0" \
    -o "$OUTPUT_ISO" \
    -J -l -b isolinux/isolinux.bin \
    -c isolinux/boot.cat \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    -isohybrid-mbr "$TOOLS_DIR/isohdpfx.bin" \
    -partition_offset 16 \
    -eltorito-alt-boot \
    -e boot/grub/efi.img \
    -no-emul-boot \
    -isohybrid-gpt-basdat \
    -isohybrid-apm-hfsplus \
    "$ISO_ROOT"

log "Generating SHA256 checksum..."
sha256sum "$OUTPUT_ISO" | awk '{print $1 "  AccessOS.iso"}' > "$OUTPUT_SHA"

log "=========================================================================="
log "AccessOS ISO build completed successfully!"
log "ISO Path     : $OUTPUT_ISO"
log "ISO Size     : $(ls -lh "$OUTPUT_ISO" | awk '{print $5}')"
log "SHA256 Hash  : $(cat "$OUTPUT_SHA")"
log "=========================================================================="
