# spd-py: Unisoc / Spreadtrum Firmware Tool

A modern, modular, cross-platform Python implementation of the Unisoc BSL (Bootloader Serial Link) flasher and firmware dumper, porting and superseding `spreadtrum_flash` (`spd_dump`).

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## Features

- **Intuitive Subcommand CLI**: Clean verbs (`dump`, `flash`, `erase`, `partitions`, `reboot`, `slot`, `security`, `kick`, `pactime`, `firstmode`, `raw`) replace cryptic single-letter commands.
- **100% C Codebase Feature Parity**:
  - Diagnostic mode kick & autodloader commands (`spd kick`, `--kick`).
  - Android Bootloader Control (BCB) A/B slot switching (`spd slot`).
  - Android Verified Boot (AVB) dm-verity disabler across vbmeta partitions (`spd security`).
  - Direct physical memory (RAM) and raw flash memory read/write operations (`spd raw`).
  - Storage repartitioning via XML partition tables (`spd partitions --repartition`).
  - Automatic NV item checksum generation (CRC16 + additive word check) during flash.
  - NAND flash geometry and UBI volume size calculations.
  - PAC firmware creation timestamp decoding (`spd pactime`).
- **Rich Terminal Experience**: Live transfer speed progress bars (ETA, MB/s, percent) and styled tables for partition listings and device properties.
- **Interactive REPL Shell**: Powered by `prompt_toolkit` and `rich` with tab completion, history, and legacy aliases (`r`, `w`, `e`, `p`, etc.).
- **Zero-Hardware Simulation**: Built-in mock Unisoc device (`--sim` flag) for instant testing of all commands without a physical phone.
- **All Platforms Supported**:
  - **Linux**: Direct USB access via `pyusb` and serial ports.
  - **macOS**: USB and serial support.
  - **Android (Termux)**: OTG passthrough via `--usb-fd`.
  - **Windows x64**: Native USB & virtual COM port support.
  - **Windows x86 Legacy**: Dedicated `Channel9.dll` support with automatic fallback to `pyserial`.
- **DRY & Modular Architecture**: HDLC framing, CRC16, checksums, and packet handling live in `spd.core` and are never duplicated.

---

## Quick Start

### Installation

Using `uv`:
```bash
git clone https://github.com/TomKing062/spreadtrum_flash.git  # or clone spd-py repository
cd spd-py
uv sync
```

Or with `pip`:
```bash
pip install .
```

### Basic Commands

```bash
# 1. Interactive REPL shell (try it in simulation mode!)
spd --sim shell

# 2. Query device info
spd info

# 3. View partition table
spd partitions

# 4. Dump single partition
spd dump boot boot.img

# 5. Full backup (excluding userdata and cache)
spd dump all backup/ --lite

# 6. Flash partition
spd flash boot boot.img

# 7. Batch flash folder
spd flash all ./firmware_folder/

# 8. Reboot device
spd reboot -m recovery
```

---

## Documentation

Detailed technical documentation is available in the [`docs/`](docs/) directory:

- [CLI Reference Guide](docs/cli_reference.md): All subcommands, options, and usage examples.
- [Architecture & Modularity Guide](docs/architecture.md): Protocol framing, channel state machine, and modular layer breakdown.
- [Transports & Platform Setup](docs/transports_and_x86.md): Linux udev rules, Android Termux OTG, Windows x64, and Windows x86 Channel9 setup.
- [Simulation Mode Guide](docs/simulation_mode.md): Complete guide to zero-hardware virtual device testing.

---

## Running Tests

Run the complete test suite:
```bash
uv run pytest
```

Check code quality with Ruff:
```bash
uv run ruff check
uv run ruff format --check
```

---

## Credits

This project ports and supersedes the original C implementation of [spreadtrum_flash](https://github.com/TomKing062/spreadtrum_flash) (`spd_dump`).

---

## License

MIT License.
