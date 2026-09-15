"""End-to-end integration tests for Click CLI subcommands."""

from pathlib import Path

from click.testing import CliRunner

from spd_dump.cli import cli


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Unisoc / Spreadtrum Firmware Tool" in result.output
    assert "boot" in result.output
    assert "dump" in result.output
    assert "flash" in result.output
    assert "partitions" in result.output
    assert "simulate" in result.output


def test_cli_sim_info() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--sim", "info"])
    assert result.exit_code == 0
    assert "Chip UID" in result.output


def test_cli_sim_partitions(tmp_path: Path) -> None:
    runner = CliRunner()
    xml_out = tmp_path / "parts.xml"
    result = runner.invoke(cli, ["--sim", "partitions", "--xml", str(xml_out)])
    assert result.exit_code == 0
    assert "boot" in result.output
    assert xml_out.exists()


def test_cli_sim_dump(tmp_path: Path, monkeypatch) -> None:
    import spd_dump.flasher.operations as ops
    from spd_dump.partitions.partition import Partition
    from spd_dump.partitions.table import PartitionTable

    monkeypatch.setattr(
        ops,
        "read_partition_table",
        lambda ch: PartitionTable([Partition(name="boot", size=4096)]),
    )
    runner = CliRunner()
    out_file = tmp_path / "boot.bin"
    result = runner.invoke(
        cli, ["--sim", "dump", "boot", str(out_file), "--blk-size", "4096"]
    )
    assert result.exit_code == 0
    assert out_file.exists()


def test_cli_sim_flash(tmp_path: Path) -> None:
    runner = CliRunner()
    in_file = tmp_path / "boot.img"
    in_file.write_bytes(b"TEST_IMAGE_PAYLOAD_12345678")
    result = runner.invoke(cli, ["--sim", "flash", "boot", str(in_file)])
    assert result.exit_code == 0
    assert "Successfully flashed boot" in result.output


def test_cli_sim_erase() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--sim", "erase", "boot"])
    assert result.exit_code == 0
    assert "Partition 'boot' erased" in result.output


def test_cli_sim_patch() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--sim", "patch", "boot", "0x100", "0xCAFE"])
    assert result.exit_code == 0
    assert "Written 0x0000CAFE" in result.output


def test_cli_sim_slot_and_security() -> None:
    runner = CliRunner()
    res1 = runner.invoke(cli, ["--sim", "slot", "a"])
    assert res1.exit_code == 0

    res2 = runner.invoke(cli, ["--sim", "security", "disable"])
    assert res2.exit_code == 0


def test_cli_sim_reboot() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--sim", "reboot", "-m", "recovery"])
    assert result.exit_code == 0
    assert "Device reboot triggered" in result.output


def test_cli_sim_simulate_demo() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["simulate", "--delay-ms", "0"])
    assert result.exit_code == 0
    assert "Simulation demonstration completed successfully!" in result.output
