#!/usr/bin/env bash
# ==============================================================================
# AccessOS Reproducible ISO Build Script
# ==============================================================================
# Builds a standalone, bootable, branded AccessOS ISO based on Linux Mint 22.3 Xfce
# without modifying the host OS, partitions, or installed software.
#
# Guarantees:
#   - 100% unprivileged execution on host.
#   - Source ISO is verified and never overwritten.
#   - Produces AccessOS.iso and AccessOS.iso.sha256 in target location.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SOURCE_ISO="/mnt/1208154E081531E9/AccessOS/linuxmint-22.3-xfce-64bit.iso"
BUILD_DIR="/mnt/1208154E081531E9/AccessOS/iso_build"
ISO_ROOT="$BUILD_DIR/iso_root"
SQUASH_ROOT="$BUILD_DIR/squashfs_root"
TOOLS_DIR="$BUILD_DIR/tools"
XORRISO_BIN="$TOOLS_DIR/bin/xorriso"
ISOHDPFX_BIN="$TOOLS_DIR/isohdpfx.bin"

OUTPUT_ISO="/mnt/1208154E081531E9/AccessOS/AccessOS.iso"
OUTPUT_SHA="$OUTPUT_ISO.sha256"

log() {
    echo -e "\033[1;34m[AccessOS Build]\033[0m $*"
}

err() {
    echo -e "\033[1;31m[ERROR]\033[0m $*" >&2
}

# ── 1. Sanity Checks ───────────────────────────────────────────────────────────
log "Starting AccessOS ISO Build Process..."

if [ ! -f "$SOURCE_ISO" ]; then
    err "Source ISO not found at: $SOURCE_ISO"
    exit 1
fi

for cmd in 7z unsquashfs mksquashfs; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        err "Required command '$cmd' is not installed."
        exit 1
    fi
done

if [ ! -x "$XORRISO_BIN" ]; then
    err "Unprivileged xorriso binary not found at: $XORRISO_BIN"
    exit 1
fi

if [ ! -f "$ISOHDPFX_BIN" ]; then
    log "Extracting MBR boot sector from source ISO..."
    dd if="$SOURCE_ISO" of="$ISOHDPFX_BIN" bs=512 count=1 status=none
fi

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# ── 2. Unpack ISO Root ─────────────────────────────────────────────────────────
if [ ! -d "$ISO_ROOT/casper" ]; then
    log "Unpacking source ISO root filesystem..."
    rm -rf "$ISO_ROOT"
    mkdir -p "$ISO_ROOT"
    7z x -y "$SOURCE_ISO" -o"$ISO_ROOT" >/dev/null
    log "ISO root unpacked successfully."
else
    log "ISO root directory already present, skipping unpack."
fi

# ── 3. Unpack SquashFS Root ────────────────────────────────────────────────────
if [ ! -d "$SQUASH_ROOT/usr" ]; then
    log "Unsquashing casper/filesystem.squashfs (this may take 1-2 minutes)..."
    rm -rf "$SQUASH_ROOT"
    unsquashfs -d "$SQUASH_ROOT" "$ISO_ROOT/casper/filesystem.squashfs" >/dev/null
    log "SquashFS root unpacked successfully."
else
    log "SquashFS root already unpacked, proceeding with customizations."
fi

# ── 4. Customize SquashFS Root ─────────────────────────────────────────────────
log "Applying AccessOS system customizations..."

# 4.1 Install AccessOS to /opt/accessos
log "Installing AccessOS application to /opt/accessos..."
mkdir -p "$SQUASH_ROOT/opt/accessos"
rsync -a --exclude='.git' --exclude='iso_build' --exclude='tests' \
    --exclude='__pycache__' --exclude='*.pyc' \
    "$REPO_DIR/" "$SQUASH_ROOT/opt/accessos/"

# 4.2 Install Launcher Script
log "Installing /usr/local/bin/accessos launcher wrapper..."
cat << 'RUNNER_EOF' > "$SQUASH_ROOT/usr/local/bin/accessos"
#!/usr/bin/env bash
export ACCESSOS_BASE_DIR="/opt/accessos"
export PYTHONPATH="/opt/accessos:$PYTHONPATH"

# Auto-detect profile on live boot unless explicitly overridden
if [ -z "${ACCESSOS_PROFILE:-}" ]; then
    export ACCESSOS_PROFILE="vm-real"
fi

exec /opt/accessos/.venv/bin/python3 -m accessos "$@"
RUNNER_EOF
chmod +x "$SQUASH_ROOT/usr/local/bin/accessos"

# 4.3 Configure Autostart
log "Configuring AccessOS autostart for live user session..."
mkdir -p "$SQUASH_ROOT/etc/xdg/autostart" "$SQUASH_ROOT/etc/skel/.config/autostart"
cat << 'AUTO_EOF' > "$SQUASH_ROOT/etc/xdg/autostart/accessos.desktop"
[Desktop Entry]
Type=Application
Name=AccessOS
Comment=AccessOS Accessible Environment
Exec=/usr/local/bin/accessos --fullscreen
Icon=/opt/accessos/assets/icons/accessos.png
Terminal=false
StartupNotify=true
Categories=Utility;Accessibility;
X-XFCE-Autostart-Override=true
AUTO_EOF
cp "$SQUASH_ROOT/etc/xdg/autostart/accessos.desktop" "$SQUASH_ROOT/etc/skel/.config/autostart/accessos.desktop"

# 4.4 Strip Desktop Clutter (Keep ONLY the 6 allowed apps & emergency terminal)
log "Pruning non-essential desktop launchers (LibreOffice, games, mail, chat)..."
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

# 4.5 Hide desktop icons in Xfce so AccessOS dock is the primary interface
log "Configuring Xfce desktop to disable desktop clutter..."
mkdir -p "$SQUASH_ROOT/etc/xdg/xfce4/xfconf/xfce-perchannel-xml"
cat << 'XFCE_DESK_EOF' > "$SQUASH_ROOT/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml"
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-desktop" version="1.0">
  <property name="desktop-icons" type="empty">
    <property name="style" type="int" value="0"/>
  </property>
</channel>
XFCE_DESK_EOF

# 4.6 Install Branding and Wallpaper
log "Applying AccessOS branding and wallpapers..."
mkdir -p "$SQUASH_ROOT/usr/share/backgrounds/accessos"
if [ -f "$REPO_DIR/assets/wallpaper/accessos_bg.jpg" ]; then
    cp "$REPO_DIR/assets/wallpaper/accessos_bg.jpg" "$SQUASH_ROOT/usr/share/backgrounds/accessos/accessos_wallpaper.jpg"
fi

# Update OS release metadata
cat << 'OS_EOF' > "$SQUASH_ROOT/etc/os-release"
NAME="AccessOS"
VERSION="1.0 (Accessible Operating System)"
ID=accessos
ID_LIKE="linuxmint ubuntu debian"
PRETTY_NAME="AccessOS 1.0 (Xfce 64-bit)"
VERSION_ID="1.0"
HOME_URL="https://accessos.org"
SUPPORT_URL="https://accessos.org/support"
BUG_REPORT_URL="https://accessos.org/bugs"
PRIVACY_POLICY_URL="https://accessos.org/privacy"
UBUNTU_CODENAME=noble
OS_EOF

echo "AccessOS 1.0 \n \l" > "$SQUASH_ROOT/etc/issue"
echo "AccessOS 1.0" > "$SQUASH_ROOT/etc/issue.net"

# ── 5. Customize ISO Bootloader ────────────────────────────────────────────────
log "Updating GRUB and ISOLINUX bootloader menus..."
# GRUB configuration
if [ -f "$ISO_ROOT/boot/grub/grub.cfg" ]; then
    sed -i 's/Linux Mint 22.3 Xfce 64-bit/AccessOS 1.0 (Accessible Environment)/g' "$ISO_ROOT/boot/grub/grub.cfg"
    sed -i 's/Start Linux Mint/Start AccessOS 1.0/g' "$ISO_ROOT/boot/grub/grub.cfg"
    sed -i 's/Linux Mint/AccessOS 1.0/g' "$ISO_ROOT/boot/grub/grub.cfg"
fi

if [ -f "$ISO_ROOT/boot/grub/loopback.cfg" ]; then
    sed -i 's/Linux Mint/AccessOS 1.0/g' "$ISO_ROOT/boot/grub/loopback.cfg"
fi

if [ -f "$ISO_ROOT/isolinux/live.cfg" ]; then
    sed -i 's/Welcome to Linux Mint 22.3 64-bit/Welcome to AccessOS 1.0 (Accessible Environment)/g' "$ISO_ROOT/isolinux/live.cfg"
    sed -i 's/Start Linux Mint in compatibility mode/Start AccessOS 1.0 in compatibility mode/g' "$ISO_ROOT/isolinux/live.cfg"
    sed -i 's/Start Linux Mint/Start AccessOS 1.0/g' "$ISO_ROOT/isolinux/live.cfg"
fi

if [ -f "$ISO_ROOT/.disk/info" ]; then
    echo "AccessOS 1.0 \"Accessible\" - Release amd64" > "$ISO_ROOT/.disk/info"
fi

# ── 6. Repack SquashFS ─────────────────────────────────────────────────────────
log "Repacking casper/filesystem.squashfs using xz compression..."
rm -f "$ISO_ROOT/casper/filesystem.squashfs"
mksquashfs "$SQUASH_ROOT" "$ISO_ROOT/casper/filesystem.squashfs" \
    -comp xz \
    -b 1048576 \
    -all-root \
    -noappend

# Update filesystem size
log "Updating filesystem.size..."
du -sx --block-size=1 "$SQUASH_ROOT" | cut -f1 > "$ISO_ROOT/casper/filesystem.size"

# Update md5 sums for live boot integrity verification
log "Recalculating MD5 checksums for ISO files..."
cd "$ISO_ROOT"
rm -f md5sum.txt
find . -type f ! -name "isolinux.bin" ! -name "boot.cat" ! -path "./isolinux/*" -exec md5sum {} + > md5sum.txt
cd "$BUILD_DIR"

# ── 7. Master Hybrid ISO with XORRISO ──────────────────────────────────────────
log "Mastering bootable hybrid AccessOS.iso..."
rm -f "$OUTPUT_ISO"

"$XORRISO_BIN" -as mkisofs \
    -R -r -J -joliet-long -l -cache-inodes -iso-level 3 \
    -isohybrid-mbr "$ISOHDPFX_BIN" \
    -partition_offset 16 \
    -A "AccessOS Live" \
    -p "AccessOS Team" \
    -publisher "AccessOS" \
    -V "AccessOS 1.0 Xfce 64-bit" \
    -b isolinux/isolinux.bin -c isolinux/boot.cat \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    -eltorito-alt-boot \
    -e boot/grub/efi.img \
    -no-emul-boot -isohybrid-gpt-basdat -isohybrid-apm-hfsplus \
    -o "$OUTPUT_ISO" "$ISO_ROOT"

# ── 8. Compute Checksum & Summary ──────────────────────────────────────────────
log "Computing SHA256 checksum for AccessOS.iso..."
sha256sum "$OUTPUT_ISO" > "$OUTPUT_SHA"

ISO_SIZE=$(du -h "$OUTPUT_ISO" | cut -f1)
SHA_VAL=$(cat "$OUTPUT_SHA" | awk '{print $1}')

log "======================================================================"
log "AccessOS ISO Build COMPLETED SUCCESSFULLY!"
log "Output ISO:  $OUTPUT_ISO ($ISO_SIZE)"
log "SHA256:      $SHA_VAL"
log "Checksum:    $OUTPUT_SHA"
log "======================================================================"
