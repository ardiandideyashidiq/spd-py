"""Unit tests for diagnostic mode kick and autodloader switcher."""

from __future__ import annotations

from click.testing import CliRunner

from spd.boot.engine import (
    DIAG_AUTODLOADER_CMD,
    BootEngine,
    build_diag_payload,
)
from spd.cli import cli
from spd.core.channel import SpdChannel
from spd.transports.simulation import SimulationTransport


def test_build_diag_payload() -> None:
    """Verify diag payload byte layout matching C ChangeMode."""
    # bootmode == 0 defaults to 0x82
    p0 = build_diag_payload(bootmode=0, at=False)
    assert len(p0) == 10
    assert p0[0] == 0x7E and p0[9] == 0x7E
    assert p0[7] == 0xFE
    assert p0[8] == 0x82

    # at == True sets 0x81
    pat = build_diag_payload(bootmode=1, at=True)
    assert pat[8] == 0x81

    # custom mode e.g. mode=2 -> 2 + 0x80 = 0x82
    p2 = build_diag_payload(bootmode=2, at=False)
    assert p2[8] == 0x82


def test_diag_autodloader_cmd() -> None:
    """Verify AT+SPREF=AUTODLOADER command format."""
    assert b'AT+SPREF="AUTODLOADER"\r\n' in DIAG_AUTODLOADER_CMD
    assert DIAG_AUTODLOADER_CMD[0] == 0x7E
    assert DIAG_AUTODLOADER_CMD[-1] == 0x7E


def test_boot_engine_kick() -> None:
    """Test BootEngine.kick in simulated environment."""
    trans = SimulationTransport()
    trans.connect()
    channel = SpdChannel(trans)
    engine = BootEngine(channel)

    success = engine.kick(bootmode=0, timeout=2.0)
    assert success is True
    trans.disconnect()


def test_cli_kick_command() -> None:
    """Test 'spd kick' subcommand with simulation runner."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--sim", "kick", "--mode", "0"])
    assert result.exit_code == 0
    assert "successfully kicked" in result.output.lower()


def test_cli_boot_with_kick(tmp_path) -> None:
    """Test 'spd boot --kick' command in simulation."""
    runner = CliRunner()
    dummy_fdl1 = tmp_path / "fdl1_0x40004000.bin"
    dummy_fdl1.write_bytes(b"\x00" * 512)

    result = runner.invoke(
        cli,
        [
            "--sim",
            "boot",
            "--fdl1",
            str(dummy_fdl1),
            "--kick",
        ],
    )
    assert result.exit_code == 0
    assert "boot sequence successful" in result.output.lower()
