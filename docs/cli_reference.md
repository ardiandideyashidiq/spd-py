# CLI Reference Guide (`spd`)

`spd` is the next-generation CLI utility for Spreadtrum / Unisoc devices, replacing the legacy `spd_dump` C tool.

## Global Options

The following options can be provided to any `spd` command:

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--port` | `-p` | Serial COM or tty path (`COM3`, `/dev/ttyUSB0`) | Auto-detect |
| `--transport` | `-t` | Backend transport: `auto`, `usb`, `serial`, `channel9`, `sim` | `auto` |
| `--baud` | `-b` | Serial baud rate | `115200` |
| `--sim`, `--simulate` | | Enable in-memory virtual hardware simulation | `False` |
| `--usb-fd` | | Android Termux OTG file descriptor passthrough | None |
| `--wait` | `-w` | Connection and response timeout in seconds | `10.0` |
| `--verbose` | `-v` | Increase log verbosity (`-v` for DEBUG, `-vv` for TRACE) | INFO |
| `--fdl1` | | Optional FDL1 image to auto-boot device | None |
| `--fdl1-addr` | | FDL1 load address in hex (e.g. `0x40004000`) | From file |
| `--fdl2` | | Optional FDL2 image to auto-boot device | None |
| `--fdl2-addr` | | FDL2 load address in hex (e.g. `0x9F000000`) | From file |
| `--exec-addr` | | CVE-2022-38694 signature bypass address | None |
| `--help` | `-h` | Show help and usage summary | |

---

## Subcommands

### 1. `spd boot`
Execute the multi-stage BSL boot sequence (handshake -> FDL1 -> exec -> FDL2 -> exec).

```bash
spd boot --fdl1 uboot/fdl1.bin --fdl1-addr 0x40004000 --fdl2 uboot/fdl2.bin --fdl2-addr 0x9F000000
```
If the hex address is encoded in the file name (e.g., `fdl1_0x40004000.bin`), the address options are optional:
```bash
spd boot --fdl1 fdl1_0x40004000.bin --fdl2 fdl2_0x9F000000.bin
```

---

### 2. `spd info`
Query chip UID, chip type, and hardware status.

```bash
spd info
spd --sim info
```

---

### 3. `spd partitions`
Inspect on-flash partition table, or export it to XML or JSON manifest.

```bash
# Display formatted Rich partition table
spd partitions

# Export to XML
spd partitions --xml partitions.xml

# Export to JSON manifest for backup
spd partitions --json manifest.json
```

---

### 4. `spd dump`
Read and dump partition contents to local files with live Rich progress bars.

```bash
# Dump a single partition
spd dump boot boot.img

# Dump full firmware backup (creates backup/ with partitions.json manifest)
spd dump all backup/

# Dump full firmware excluding userdata, cache, and blackbox
spd dump all-lite backup/

# Filter backup by active slot
spd dump all backup/ --slot a
```

---

### 5. `spd flash`
Flash binary image(s) to target partition(s) with live progress and checksumming.

```bash
# Flash a single partition
spd flash boot boot.img

# Batch flash all partitions from a folder matching partitions.json manifest
spd flash all ./firmware_folder/

# Target a specific slot
spd flash all ./firmware_folder/ --slot b
```

---

### 6. `spd erase`
Erase a partition or perform a factory wipe.

```bash
# Erase a single partition
spd erase cache

# Erase all flash partitions (prompts for confirmation)
spd erase all

# Bypass confirmation prompt
spd erase all --yes
```

---

### 7. `spd patch`
Write arbitrary values or binary files directly to a partition at a specific offset (`wof` / `wov`).

```bash
# Write 32-bit hex value at offset 0x100
spd patch misc 0x100 0x12345678

# Write binary payload at offset 0x200
spd patch splash 0x200 logo.bin
```

---

### 8. `spd reboot`
Reboot or power off the target device.

```bash
# Normal reboot
spd reboot

# Reboot directly to recovery mode
spd reboot -m recovery

# Reboot directly to fastboot mode
spd reboot -m fastboot

# Power off
spd reboot -m poweroff
```

---

### 9. `spd slot`
Select active boot slot on A/B and Virtual A/B partitioned devices.

```bash
spd slot a
spd slot b
```

---

### 10. `spd security`
Enable or disable Android dm-verity verification on target device.

```bash
spd security disable
spd security enable
```

---

### 11. `spd shell`
Start the interactive REPL shell with auto-completion, live partition caching, and legacy C command aliases (`r`, `w`, `e`, `p`, etc.).

```bash
spd shell
spd --sim shell
```

---

### 12. `spd simulate`
Run an automated simulation session demonstrating hardware connection, partition query, and simulated flashing.

```bash
spd simulate
```
