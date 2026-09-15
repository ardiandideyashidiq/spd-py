"""Unit tests for raw physical memory and flash I/O operations."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from spd.cli import cli
from spd.core.channel import SpdChannel
from spd.flasher.operations import (
    read_flash,
    read_mem,
    write_flash,
    write_physical_word,
)
from spd.transports.simulation import SimulationTransport


def test_read_mem(tmp_path: Path) -> None:
    """Test reading physical RAM memory via BSL_CMD_READ_MIDST."""
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans)

    out_file = tmp_path / "mem_dump.bin"
    bytes_read = read_mem(channel, start_addr=0x80000000, size=2048, output_path=out_file)
    assert bytes_read == 2048
    assert out_file.exists()
    assert len(out_file.read_bytes()) == 2048

    trans.disconnect()


def test_read_flash(tmp_path: Path) -> None:
    """Test reading raw physical flash via BSL_CMD_READ_FLASH."""
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans)

    out_file = tmp_path / "flash_dump.bin"
    bytes_read = read_flash(
        channel,
        addr=0x10000000,
        offset=0x1000,
        size=4096,
        output_path=out_file,
    )
    assert bytes_read == 4096
    assert out_file.exists()
    assert len(out_file.read_bytes()) == 4096

    trans.disconnect()


def test_write_flash_and_word() -> None:
    """Test writing bytes and 32-bit word directly to physical memory."""
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans)

    # Test writing buffer
    test_data = b"UNISOC_DIRECT_MEMORY_TEST" * 32
    written = write_flash(channel, addr=0x80000000, input_source=test_data)
    assert written == len(test_data)

    # Test writing single 32-bit word
    write_physical_word(channel, addr=0x80001000, value=0xDEADBEEF)

    trans.disconnect()


def test_cli_raw_commands(tmp_path: Path) -> None:
    """Test 'spd raw' CLI subcommands with simulation runner."""
    runner = CliRunner()

    mem_out = tmp_path / "cli_mem.bin"
    res1 = runner.invoke(cli, ["--sim", "raw", "read-mem", "0x80000000", "512", str(mem_out)])
    assert res1.exit_code == 0
    assert mem_out.exists()

    flash_out = tmp_path / "cli_flash.bin"
    res2 = runner.invoke(cli, ["--sim", "raw", "read-flash", "0x0", "0x0", "1024", str(flash_out)])
    assert res2.exit_code == 0
    assert flash_out.exists()

    dummy_bin = tmp_path / "payload.bin"
    dummy_bin.write_bytes(b"\x90" * 128)
    res3 = runner.invoke(cli, ["--sim", "raw", "write-flash", "0x80000000", str(dummy_bin)])
    assert res3.exit_code == 0

    res4 = runner.invoke(cli, ["--sim", "raw", "write-word", "0x80000000", "0xCAFEBABE"])
    assert res4.exit_code == 0
