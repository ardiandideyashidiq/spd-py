"""Unit tests for XML repartitioning, fixed NV item checksumming, and NAND UBI sizing."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from spd.cli import cli
from spd.core.channel import SpdChannel
from spd.flasher.operations import (
    flash_nv_partition,
    prepare_nv_image,
    repartition,
)
from spd.partitions.nand import parse_nand_id, parse_ubi_size
from spd.transports.simulation import SimulationTransport


def test_parse_nand_id() -> None:
    """Verify NAND geometry calculation matching C spd_dump.c."""
    info = parse_nand_id(0x15)
    assert info["page_size_kb"] == 2 ** (0x15 & 3)  # 2KB
    assert info["spare_size"] == 32 // (2 ** ((0x15 >> 2) & 3))
    assert info["block_size_kb"] == 64 * (2 ** ((0x15 >> 4) & 3))


def test_parse_ubi_size() -> None:
    """Verify UBI size parsing with LEB overhead."""
    # Standard sizes
    assert parse_ubi_size("40m") == 40 * 1024 * 1024
    assert parse_ubi_size("1024k") == 1024 * 1024
    assert parse_ubi_size("0x1000") == 0x1000

    # UBI size with LEB overhead
    ubi_size = parse_ubi_size("ubi40m")
    assert ubi_size >= 40 * 1024 * 1024


def test_prepare_nv_image() -> None:
    """Verify NV image CRC header and checksum computation."""
    raw_nv = b"NV" + b"\x00" * 510 + b"\x00\x00\x01\x00" + b"TEST_NV_DATA"
    proc_data, cs = prepare_nv_image(raw_nv)
    assert len(proc_data) > 0
    assert cs > 0


def test_flash_nv_partition() -> None:
    """Test flashing fixed NV partition in simulation."""
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans)

    nv_data = b"NV" + b"\x00" * 510 + b"FIXED_NV_CONTENTS" * 16
    written = flash_nv_partition(channel, "fixnv1", nv_data)
    assert written > 0

    trans.disconnect()


def test_repartition_xml(tmp_path: Path) -> None:
    """Test device repartitioning from XML file."""
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans)

    xml_content = """<Partitions>
    <Partition id="splloader" size="1"/>
    <Partition id="uboot" size="4"/>
    <Partition id="custom_test" size="16"/>
</Partitions>"""
    xml_file = tmp_path / "partitions.xml"
    xml_file.write_text(xml_content, encoding="utf-8")

    count = repartition(channel, xml_file)
    assert count == 3
    assert "custom_test" in trans.device.partitions

    trans.disconnect()


def test_cli_partitions_repartition(tmp_path: Path) -> None:
    """Test CLI 'spd partitions --repartition <xml>' in simulation."""
    runner = CliRunner()
    xml_content = """<Partitions>
    <Partition id="splloader" size="1"/>
    <Partition id="new_part" size="8"/>
</Partitions>"""
    xml_file = tmp_path / "repart.xml"
    xml_file.write_text(xml_content, encoding="utf-8")

    result = runner.invoke(cli, ["--sim", "partitions", "--repartition", str(xml_file)])
    assert result.exit_code == 0
    assert "Device repartitioned" in result.output
