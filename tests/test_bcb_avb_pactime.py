"""Unit tests for Android BCB, AVB dm-verity, firstmode, and pactime."""

from __future__ import annotations

import struct
import zlib

from click.testing import CliRunner

from spd.cli import cli
from spd.core.channel import SpdChannel
from spd.flasher.operations import (
    build_bootloader_control,
    read_pactime,
    reboot_device,
    set_active_slot,
    set_dm_verity,
    set_first_mode,
)
from spd.transports.simulation import SimulationTransport


def test_build_bootloader_control() -> None:
    """Verify Android BCB structure layout, magic, and CRC32."""
    bcb_a = build_bootloader_control("a")
    assert len(bcb_a) == 32
    assert bcb_a[:4] == b"_a\x00\x00"

    magic, version = struct.unpack_from("<II", bcb_a, 4)
    assert magic == 0x42414342
    assert version == 0x201

    # Check CRC32 matches over first 28 bytes
    crc_expected = zlib.crc32(bcb_a[:28]) & 0xFFFFFFFF
    crc_actual = struct.unpack_from("<I", bcb_a, 28)[0]
    assert crc_actual == crc_expected

    # Test slot b
    bcb_b = build_bootloader_control("b")
    assert bcb_b[:4] == b"_b\x00\x00"


def test_set_active_slot_misc_write() -> None:
    """Verify set_active_slot writes BCB to partition misc at 0x800."""
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans)

    set_active_slot(channel, "b")
    misc_buf = trans.device.partitions["misc"]
    bcb_written = misc_buf[0x800 : 0x800 + 32]
    assert bcb_written[:4] == b"_b\x00\x00"

    trans.disconnect()


def test_reboot_device_recovery_and_fastboot() -> None:
    """Verify reboot to recovery and fastboot writes BCB command to misc:0x0."""
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans)

    # Test recovery
    reboot_device(channel, mode="recovery")
    misc_buf = trans.device.partitions["misc"]
    assert misc_buf[:13] == b"boot-recovery"

    # Test fastboot
    reboot_device(channel, mode="fastboot")
    assert misc_buf[:13] == b"boot-recovery"
    assert b"recovery\n--fastboot\n" in misc_buf[0x40:0x80]

    trans.disconnect()


def test_dm_verity_vbmeta_patch() -> None:
    """Verify set_dm_verity patches byte 0x7B across vbmeta partitions."""
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans)

    # Disable verity (writes 0x00)
    patched = set_dm_verity(channel, enable=False)
    assert "vbmeta" in patched
    assert trans.device.partitions["vbmeta"][0x7B] == 0x00

    # Enable verity (writes 0x02)
    patched = set_dm_verity(channel, enable=True)
    assert "vbmeta" in patched
    assert trans.device.partitions["vbmeta"][0x7B] == 0x02

    trans.disconnect()


def test_firstmode_miscdata_write() -> None:
    """Verify set_first_mode writes mode + 0x53464D00 to miscdata:0x2420."""
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans)

    set_first_mode(channel, mode_id=5)
    miscdata_buf = trans.device.partitions["miscdata"]
    val = struct.unpack_from("<I", miscdata_buf, 0x2420)[0]
    assert val == 5 + 0x53464D00

    trans.disconnect()


def test_read_pactime() -> None:
    """Verify read_pactime reads from miscdata:0x81400."""
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans)

    raw_time, unix_time = read_pactime(channel)
    assert raw_time > 0
    assert unix_time == 1705320000

    trans.disconnect()


def test_cli_pactime_and_firstmode() -> None:
    """Test CLI commands 'spd pactime' and 'spd firstmode'."""
    runner = CliRunner()
    res1 = runner.invoke(cli, ["--sim", "pactime"])
    assert res1.exit_code == 0
    assert "PAC Timestamp" in res1.output

    res2 = runner.invoke(cli, ["--sim", "firstmode", "2"])
    assert res2.exit_code == 0
    assert "Firstmode set to 2" in res2.output
