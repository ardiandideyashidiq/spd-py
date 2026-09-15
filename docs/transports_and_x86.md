# Transports & Platform Setup Guide

`spd-py` supports all platforms supported by the original C codebase: Linux, macOS, Android (Termux), and Windows (both modern x64 and legacy x86).

---

## 1. Linux Setup

### Permissions (udev rules)
To access Unisoc devices in BROM and FDL mode without `sudo`, create a udev rule:

```bash
sudo nano /etc/udev/rules.d/99-unisoc.rules
```

Add the following rule for Spreadtrum VID `1782`:
```udev
SUBSYSTEM=="usb", ATTR{idVendor}=="1782", MODE="0666", GROUP="plugdev"
```

Reload rules:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

## 2. Android (Termux) Setup

`spd-py` supports Termux on rooted or non-rooted Android phones via USB OTG.

1. Install Termux and Termux:API.
2. Grant Termux USB permission:
   ```bash
   pkg install termux-api python
   termux-usb -l
   ```
3. Run `spd` passing the USB file descriptor:
   ```bash
   termux-usb -e 'spd --usb-fd' /dev/bus/usb/001/002
   ```

---

## 3. Windows x64 (Modern)

On modern 64-bit Windows:
- If using official Unisoc / SPRD USB Drivers, Windows exposes `SPRD U2S Diag (COMx)`. `spd-py` will automatically detect and communicate over this virtual serial port using PySerial.
- If using WinUSB or libusb-win32 (via Zadig), `spd-py` accesses the device directly using PyUSB.

---

## 4. Windows x86 (Legacy SPRD Driver & Channel9.dll)

The original C tool included an x86 32-bit Windows build that interfaced with `Channel9.dll` from the official Unisoc ResearchDownload / UpgradeDownload tools.

`spd-py` includes dedicated support for this via `Channel9Transport`:
- On **32-bit Windows Python**: `spd-py` dynamically loads `Channel9.dll` via `ctypes` and invokes the native driver channels.
- On **64-bit Python** or if `Channel9.dll` is absent: `spd-py` displays an informational message and automatically falls back to `PySerial`, communicating directly with the `SPRD U2S Diag` COM port without requiring 32-bit DLLs.

To force Channel9 mode:
```bash
spd -t channel9 info
```
