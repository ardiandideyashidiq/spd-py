# spd-py: Unisoc / Spreadtrum Firmware Tool

Python implementation of the Unisoc BSL flasher and firmware dumper, porting and superseding `spreadtrum_flash` (`spd_dump`).

## Features

- Subcommand CLI: `dump`, `flash`, `erase`, `partitions`, `reboot`, `slot`, `security`, `kick`, `pactime`, `firstmode`, `raw`
- Interactive REPL shell with tab completion and legacy single-letter aliases
- Zero-hardware testing: `--sim` runs every command against a mock device
- Platforms: Linux, macOS, Android (Termux OTG), Windows x64, Windows x86 legacy (Channel9.dll)

## Install

```bash
uv tool install https://github.com/ardiandideyashidiq/spd-py.git
```

## Usage

```bash
spd --sim shell                    # interactive shell (simulated device)
spd info                           # device info
spd partitions                     # partition table
spd dump boot boot.img             # dump a partition
spd dump all backup/ --lite        # backup (excluding userdata/cache)
spd flash boot boot.img            # flash a partition
spd flash all ./firmware_folder/   # batch flash a folder
spd reboot -m recovery             # reboot
```

## Documentation

- [CLI reference](docs/cli_reference.md)
- [Architecture](docs/architecture.md)
- [Simulation mode](docs/simulation_mode.md)
- [Transports & platform setup](docs/transports_and_x86.md)

## Tests

```bash
uv run pytest            # full suite, no hardware needed
uv run ruff check src tests
```

## Credits

Ports and supersedes the original C implementation of [spreadtrum_flash](https://github.com/TomKing062/spreadtrum_flash) (`spd_dump`).

## License

MIT.