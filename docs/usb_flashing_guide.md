# AccessOS USB Flashing & Boot Guide

> **CRITICAL SAFETY WARNING**:
> Flashing a USB drive completely overwrites all data on the target storage device.
> **NEVER flash to `/dev/nvme0n1` or any internal host drive partition!**
> Always verify the exact device node of your USB drive before executing any write command.

---

## 1. Prerequisites
- A USB drive with at least **4 GB** capacity.
- The built ISO file: `AccessOS.iso` (approx. 3.0 GB).
- Verified SHA256 checksum file: `AccessOS.iso.sha256`.

---

## 2. Verifying the Checksum
Before flashing, always verify the cryptographic integrity of the built ISO:
```bash
sha256sum -c AccessOS.iso.sha256
```
Expected output:
```
AccessOS.iso: OK
```

---

## 3. Identifying the Correct USB Device Node (Linux)

Insert your USB drive and run:
```bash
lsblk -o NAME,SIZE,TYPE,TRAN,MODEL,MOUNTPOINTS
```

Look for the drive where:
- `TRAN` is `usb`.
- `SIZE` matches your USB drive capacity (e.g. `14.9G` or `29.8G`).
- `NAME` is typically `sdb`, `sdc`, or `sdd` (NEVER `nvme0n1`!).

Example:
```
NAME        SIZE TYPE TRAN MODEL            MOUNTPOINTS
nvme0n1     477G disk      SAMSUNG MZVLB512
├─nvme0n1p1 100M part
├─nvme0n1p4 100G part                       /
└─nvme0n1p5 376G part                       /mnt/1208154E081531E9
sdb        14.9G disk usb  SanDisk Ultra    <-- THIS IS YOUR USB DRIVE
```
In this example, the target device is `/dev/sdb`.

---

## 4. Flashing Methods

### Option A: Command Line (`dd` — Recommended for Advanced Users)
1. Unmount any mounted partitions on the USB drive:
   ```bash
   sudo umount /dev/sdX* 2>/dev/null || true
   ```
   *(Replace `sdX` with your verified device letter, e.g. `sdb`)*

2. Write the hybrid ISO directly to the raw block device:
   ```bash
   sudo dd if=/mnt/1208154E081531E9/AccessOS/AccessOS.iso of=/dev/sdX bs=4M status=progress conv=fsync oflag=direct
   ```
   *(Replace `sdX` with your verified device letter)*

3. Flush all write caches to ensure data is completely written before unplugging:
   ```bash
   sync
   ```

### Option B: Graphical Tools (Recommended for Safe Visual Confirmation)
1. **Raspberry Pi Imager**:
   - Choose OS -> *Use custom* -> select `AccessOS.iso`.
   - Choose Storage -> select your verified USB drive.
   - Click *Write*.
2. **BalenaEtcher**:
   - Flash from file -> select `AccessOS.iso`.
   - Select target drive.
   - Click *Flash!*.

---

## 5. Booting AccessOS on the ThinkPad T480

1. Insert the flashed USB drive into one of the ThinkPad T480 USB-A or USB-C ports.
2. Power off the laptop completely.
3. Turn on the laptop and immediately tap the <kbd>F12</kbd> key repeatedly to open the **ThinkPad Temporary Boot Device Menu**.
   > *Note: Using <kbd>F12</kbd> boots from the USB once without modifying your internal UEFI boot order or changing host OS settings.*
4. Select your USB drive from the list and press <kbd>Enter</kbd>.
5. The AccessOS GRUB bootloader will appear:
   - Select **Start AccessOS 1.0 (Accessible Environment)**.
6. The system boots into live memory. The First-Boot Accessibility Setup Wizard will greet you automatically with spoken voice prompts.
