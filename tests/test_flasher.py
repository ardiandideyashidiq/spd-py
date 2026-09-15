"""Unit tests for flasher operations using SimulationTransport."""

from pathlib import Path

from spd.core.channel import SpdChannel
from spd.flasher.operations import (
    dump_all,
    dump_partition,
    erase_all,
    erase_partition,
    flash_all,
    flash_partition,
    read_chip_info,
    read_partition_table,
    reboot_device,
    set_active_slot,
    set_dm_verity,
    write_offset,
    write_value,
)
from spd.partitions.partition import Partition
from spd.partitions.table import PartitionTable
from spd.transports.simulation import MockUnisocDevice, SimulationTransport


def get_connected_channel() -> tuple[SimulationTransport, SpdChannel]:
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans, default_timeout=1.0)
    return trans, channel


def test_read_partition_table_operation() -> None:
    trans, channel = get_connected_channel()
    ptable = read_partition_table(channel)
    assert len(ptable) > 0
    assert ptable.get("boot") is not None
    trans.disconnect()


def test_dump_single_partition(tmp_path: Path) -> None:
    trans, channel = get_connected_channel()
    out_file = tmp_path / "boot.bin"
    progress: list[tuple[int, int]] = []

    bytes_read = dump_partition(
        channel,
        name="boot",
        output_path=out_file,
        size=8192,
        progress_callback=lambda c, t: progress.append((c, t)),
    )

    assert out_file.exists()
    assert bytes_read == 8192
    assert out_file.stat().st_size == 8192
    assert len(progress) > 0
    trans.disconnect()


def test_dump_all_operation(tmp_path: Path) -> None:
    mock_dev = MockUnisocDevice()
    # Use compact partitions for fast test execution
    mock_dev.partitions = {"boot": bytearray(4096), "userdata": bytearray(4096)}
    # Mock READ_PARTITION reply with just these two
    mock_dev._build_binary_partition_table = lambda: PartitionTable(  # type: ignore[method-assign]
        [Partition(name="boot", size=4096), Partition(name="userdata", size=4096)]
    ).to_xml()  # Not used directly, table parser will use mock entries
    trans = SimulationTransport(mock_device=mock_dev)
    trans.connect()
    channel = SpdChannel(trans, default_timeout=1.0)
    out_dir = tmp_path / "backup"

    # Mock read_partition_table to return small test table
    import spd.flasher.operations as ops

    orig_read_ptable = ops.read_partition_table
    ops.read_partition_table = lambda ch: PartitionTable(
        [Partition(name="boot", size=4096), Partition(name="userdata", size=4096)]
    )

    try:
        saved = dump_all(channel, out_dir=out_dir, lite=True, blk_size=4096)
    finally:
        ops.read_partition_table = orig_read_ptable
    assert (out_dir / "partitions.json").exists()
    assert len(saved) > 0
    # userdata shouldn't be dumped in lite mode
    assert not (out_dir / "userdata.bin").exists()
    trans.disconnect()


def test_flash_partition_operation(tmp_path: Path) -> None:
    trans, channel = get_connected_channel()
    img_data = b"MOCK_BOOT_IMAGE_DATA_12345"
    img_path = tmp_path / "boot.img"
    img_path.write_bytes(img_data)

    written = flash_partition(channel, name="boot", input_source=img_path)
    assert written == len(img_data)
    # Verify directly in mock device storage
    assert bytes(trans.device.partitions["boot"]) == img_data
    trans.disconnect()


def test_flash_all_operation(tmp_path: Path) -> None:
    trans, channel = get_connected_channel()
    firmware_dir = tmp_path / "fw"
    firmware_dir.mkdir()

    (firmware_dir / "boot.bin").write_bytes(b"NEW_BOOT")
    (firmware_dir / "recovery.bin").write_bytes(b"NEW_RECOVERY")

    flashed = flash_all(channel, in_dir=firmware_dir)
    assert "boot" in flashed
    assert "recovery" in flashed
    assert bytes(trans.device.partitions["boot"]) == b"NEW_BOOT"
    assert bytes(trans.device.partitions["recovery"]) == b"NEW_RECOVERY"
    trans.disconnect()


def test_erase_operations() -> None:
    trans, channel = get_connected_channel()
    erase_partition(channel, "boot")
    erase_all(channel)
    trans.disconnect()


def test_patch_and_value_operations() -> None:
    trans, channel = get_connected_channel()
    write_offset(channel, "boot", 0x100, b"PATCHED")
    write_value(channel, "boot", 0x200, 0x12345678)
    trans.disconnect()


def test_device_controls() -> None:
    trans, channel = get_connected_channel()
    set_active_slot(channel, "b")
    set_dm_verity(channel, enable=False)
    info = read_chip_info(channel)
    assert "Chip UID" in info
    reboot_device(channel, mode="recovery")
    reboot_device(channel, mode="fastboot")
    reboot_device(channel, mode="normal")
    reboot_device(channel, mode="poweroff")
    trans.disconnect()
