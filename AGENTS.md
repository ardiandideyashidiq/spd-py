# AGENTS.md

Unisoc BSL firmware tool (`spd-py`). Python 3.13 (`.python-version`), src layout, uv-managed.

## Commands

```bash
uv run pytest                                      # full suite (72 tests, ~1.4s, no hardware)
uv run ruff check src tests                        # lint
uv run ruff format --check src tests               # format check (currently 1 file unformatted: src/spd/cli.py)
uv run ruff format src tests                       # auto-fix formatting
```

All tests use the `--sim` simulation transport internally — no physical device needed.

## Structure

- `src/spd/` — main package, entry point `spd.__main__:main`
  - `cli.py` — Click subcommand tree (`spd` CLI), uses rich-click for panels
  - `core/` — HDLC framing, CRC16, BslCmd/BslRep enums, SpdChannel (packet send/recv)
  - `transports/` — BaseTransport subclasses: USB, Serial, Channel9 (x86 Windows DLL), Simulation
  - `transports/simulation.py` — full in-memory BROM/FDL state machine, used via `--sim`
  - `boot/` — BootEngine (FDL1/FDL2 staging), kick/autodloader
  - `flasher/` — FlasherEngine (dump, flash, erase, patch, repartition, NV checksum, NAND UBI)
  - `partitions/` — partition table parsing, XML export
  - `ui/` — Rich console/tables, prompt_toolkit REPL shell, progress bars
- `tests/` — 10 test files, use Click `CliRunner`, `monkeypatch` for isolation
- `docs/` — architecture, CLI reference, simulation mode, transport/platform setup

## Gotchas

- Package was recently renamed from `spd_dump` to `spd` — old references may linger in comments.
- No `tool.ruff` or `tool.pytest` config in `pyproject.toml` — uses ruff/pytest defaults.
- No CI workflows, no pre-commit hooks, no Makefile.
- Build system is hatchling (`hatch.build.targets.wheel.packages = ["src/spd"]`).
- CLI aliases: `b`/`k`/`i`/`d`/`f`/`e`/`r`/`sh` map to full subcommand names.
- Hardware commands are safe to run with `--sim`; without it they need a real Unisoc device.
