"""Unit tests for partition parsing and BootEngine."""

from pathlib import Path

from spd.boot.engine import BootEngine, parse_address_from_filename
from spd.core.channel import SpdChannel
from spd.core.const import BslStage
from spd.partitions.partition import Partition
from spd.partitions.table import PartitionTable
from spd.transports.simulation import MockUnisocDevice, SimulationTransport


def test_partition_model() -> None:
    p = Partition(name="boot", size=64 * 1024 * 1024)
    assert p.size_human == "64.00 MB"
    assert not p.is_userdata_or_cache
    assert p.is_in_slot("a")
    assert p.is_in_slot("b")

    p_user = Partition(name="userdata", size=1024 * 1024 * 1024)
    assert p_user.is_userdata_or_cache

    p_a = Partition(name="system_a", size=128 * 1024 * 1024)
    assert p_a.is_in_slot("a")
    assert not p_a.is_in_slot("b")


def test_partition_table_binary_parsing() -> None:
    mock = MockUnisocDevice()
    raw_ptable = mock._build_binary_partition_table()

    ptable = PartitionTable.parse_bsl_binary(raw_ptable)
    assert len(ptable) == len(mock.DEFAULT_PARTITIONS) - 1

    boot_part = ptable.get("boot")
    assert boot_part is not None
    assert boot_part.name == "boot"
    assert boot_part.size == 64 * 1024 * 1024

    userdata = ptable.get("userdata")
    assert userdata is not None
    assert userdata.size == 512 * 1024 * 1024


def test_partition_table_xml_parsing() -> None:
    xml_content = """<?xml version="1.0"?>
    <Partitions>
        <Partition id="splloader" size="256K"/>
        <Partition id="uboot" size="2M"/>
        <Partition id="boot" size="64M"/>
    </Partitions>
    """
    ptable = PartitionTable.parse_xml(xml_content)
    assert len(ptable) == 3
    assert ptable.get("splloader").size == 256 * 1024
    assert ptable.get("uboot").size == 2 * 1024 * 1024
    assert ptable.get("boot").size == 64 * 1024 * 1024


def test_partition_manifest_roundtrip(tmp_path: Path) -> None:
    p1 = Partition(name="boot", size=64 * 1024 * 1024)
    p2 = Partition(name="vendor", size=128 * 1024 * 1024)
    table = PartitionTable(partitions=[p1, p2], storage_type="EMMC")

    manifest_path = tmp_path / "partitions.json"
    table.save_manifest(manifest_path)
    assert manifest_path.exists()

    loaded = PartitionTable.load_manifest(manifest_path)
    assert len(loaded) == 2
    assert loaded.get("boot").size == 64 * 1024 * 1024
    assert loaded.get("vendor").size == 128 * 1024 * 1024


def test_parse_address_from_filename() -> None:
    assert parse_address_from_filename("fdl1_0x40004000.bin") == 0x40004000
    assert parse_address_from_filename("fdl2-0x9F000000.img") == 0x9F000000
    assert parse_address_from_filename("/path/to/custom_0x00010000.bin") == 0x00010000
    assert parse_address_from_filename("boot.img") is None


def test_boot_engine_with_simulation() -> None:
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans, default_timeout=1.0)
    engine = BootEngine(channel)

    progress_events: list[tuple[str, int, int]] = []

    def on_prog(stage: str, curr: int, tot: int) -> None:
        progress_events.append((stage, curr, tot))

    fdl1_dummy = b"\x00" * 8192
    fdl2_dummy = b"\x00" * 16384

    engine.boot(
        fdl1=fdl1_dummy,
        fdl1_addr=0x40004000,
        fdl2=fdl2_dummy,
        fdl2_addr=0x9F000000,
        exec_addr=0x34000000,
        progress_cb=on_prog,
    )

    assert channel.stage == BslStage.FDL2
    assert channel.use_crc16 is True
    assert len(progress_events) > 0
    assert any(e[0] == "FDL1" for e in progress_events)
    assert any(e[0] == "FDL2" for e in progress_events)

    trans.disconnect()
