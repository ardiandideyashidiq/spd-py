# Simulation Mode Guide

`spd-py` includes an in-memory virtual Unisoc BSL device simulator. This allows testing, development, CI/CD validation, and demonstrations without needing a physical phone connected.

---

## Features of the Simulator

- **Full BSL Protocol State Machine**: Transitions cleanly from `BROM` to `FDL1` and `FDL2`.
- **Synthetic Flash Storage**: Preloaded with standard Unisoc partitions:
  - `splloader` (256 KB)
  - `uboot` (2 MB)
  - `sml` (1 MB)
  - `trustos` (2 MB)
  - `boot` (64 MB, preloaded with Android boot image magic `ANDROID!`)
  - `recovery` (64 MB)
  - `vbmeta` (1 MB, preloaded with AVB magic `AVB0`)
  - `system` (256 MB)
  - `vendor` (128 MB)
  - `userdata` (512 MB)
- **Accurate Binary Partition Table**: Returns authentic `0x4C`-byte Unisoc partition tables with sector divisor scaling matching real devices.
- **Flashing & Dumping Verification**: Flash writes update in-memory partition buffers, and dumps return written data or valid patterns.
- **Realistic UI Feedback**: Live Rich progress bars report transfer speeds, percentages, and ETA.

---

## How to Use Simulation Mode

### 1. Flag on Any Command (`--sim`)
Pass `--sim` to any `spd` subcommand to execute it against the simulator:

```bash
# Query simulated device information
spd --sim info

# Inspect simulated partition table
spd --sim partitions

# Dump simulated boot partition
spd --sim dump boot /tmp/mock_boot.img

# Flash a simulated partition
spd --sim flash boot /tmp/mock_boot.img

# Test interactive shell in simulation mode
spd --sim shell
```

### 2. Standalone Simulation Demo (`spd simulate`)
Run an interactive demonstration of device detection, info query, partition listing, and flashing:

```bash
spd simulate --delay-ms 5
```
