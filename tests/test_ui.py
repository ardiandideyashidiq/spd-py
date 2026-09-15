"""Unit tests for UI components and interactive shell."""

from pathlib import Path

from spd.core.channel import SpdChannel
from spd.partitions.partition import Partition
from spd.partitions.table import PartitionTable
from spd.transports.simulation import SimulationTransport
from spd.ui.progress import TransferProgressBar
from spd.ui.shell import SpdInteractiveShell
from spd.ui.tables import render_device_info, render_partition_table


def test_progress_bar_context() -> None:
    with TransferProgressBar("Test Operation", total_bytes=1000) as pb:
        pb.update(500)
        cb = pb.callback()
        cb(800, 1000)


def test_render_tables() -> None:
    ptable = PartitionTable(
        [
            Partition(name="boot_a", size=64 * 1024 * 1024),
            Partition(name="boot_b", size=64 * 1024 * 1024),
            Partition(name="userdata", size=1024 * 1024 * 1024),
        ]
    )
    # Ensure render executes cleanly without exception
    render_partition_table(ptable)

    info = {"Chip UID": "1234567890ABCDEF", "Platform": "SC9863A"}
    render_device_info(info)


def test_shell_command_dispatch(tmp_path: Path, monkeypatch) -> None:
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans, default_timeout=1.0)

    # Patch read_partition_table to return small partitions so dump tests are instant
    import spd.flasher.operations as ops

    monkeypatch.setattr(
        ops,
        "read_partition_table",
        lambda ch: PartitionTable([Partition(name="boot", size=4096)]),
    )
    shell = SpdInteractiveShell(channel)

    # Test help
    assert shell._handle_command("help") is True

    # Test info
    assert shell._handle_command("info") is True

    # Test partitions & legacy alias 'p'
    assert shell._handle_command("partitions") is True
    assert shell._handle_command("p") is True

    # Test dump partition
    out_file = tmp_path / "boot.bin"
    assert shell._handle_command(f"dump boot {out_file}") is True
    assert out_file.exists()

    # Test legacy alias 'r'
    out_r = tmp_path / "boot_r.bin"
    assert shell._handle_command(f"r boot {out_r}") is True
    assert out_r.exists()

    # Test flash partition & legacy alias 'w'
    test_img = tmp_path / "test.img"
    test_img.write_bytes(b"TEST_IMAGE")
    assert shell._handle_command(f"flash boot {test_img}") is True
    assert shell._handle_command(f"w boot {test_img}") is True

    # Test erase & legacy alias 'e'
    assert shell._handle_command("erase boot") is True
    assert shell._handle_command("e boot") is True

    # Test patch
    assert shell._handle_command("patch boot 0x10 0x12345678") is True

    # Test slot and verity
    assert shell._handle_command("slot a") is True
    assert shell._handle_command("verity 0") is True

    # Test pactime and firstmode
    assert shell._handle_command("pactime") is True
    assert shell._handle_command("firstmode 2") is True

    # Test repartition
    xml_file = tmp_path / "part.xml"
    xml_file.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<PartitionSel>\n"
        '    <Part id="boot" size="64"/>\n'
        "</PartitionSel>"
    )
    assert shell._handle_command(f"repartition {xml_file}") is True

    # Test raw commands: read-mem, read-flash, write-flash, write-word
    mem_out = tmp_path / "mem.bin"
    assert shell._handle_command(f"read-mem 0x1000 64 {mem_out}") is True
    assert mem_out.exists()

    flash_out = tmp_path / "flash.bin"
    assert shell._handle_command(f"read-flash 0x2000 64 {flash_out}") is True
    assert flash_out.exists()

    flash_in = tmp_path / "flash.in"
    flash_in.write_bytes(b"DATA" * 16)
    assert shell._handle_command(f"write-flash 0x2000 {flash_in}") is True
    assert shell._handle_command("write-word 0x3000 0x12345678") is True

    # Test exit & quit
    assert shell._handle_command("exit") is False
    assert shell._handle_command("quit") is False

    # Test reboot (should return False to terminate shell)
    assert shell._handle_command("reboot") is False

    trans.disconnect()
