"""Unit tests for transports and simulation mode."""

import pytest

from spd.core.channel import SpdChannel
from spd.core.const import BslCmd, BslRep
from spd.transports.base import TransportError
from spd.transports.channel9 import Channel9Transport
from spd.transports.factory import create_transport
from spd.transports.simulation import MockUnisocDevice, SimulationTransport


def test_simulation_transport_lifecycle() -> None:
    transport = SimulationTransport()
    assert not transport.is_connected
    transport.connect()
    assert transport.is_connected
    transport.disconnect()
    assert not transport.is_connected


def test_simulation_transport_with_channel() -> None:
    transport = SimulationTransport()
    transport.connect()

    channel = SpdChannel(transport, default_timeout=1.0)

    # Test BSL_CMD_CONNECT handshake
    rep, _payload = channel.exec_cmd(BslCmd.CONNECT)
    assert rep == BslRep.ACK

    # Test BSL_CMD_READ_CHIP_UID
    rep, uid = channel.exec_cmd(BslCmd.READ_CHIP_UID)
    assert rep == BslRep.ACK
    assert len(uid) == 16
    assert uid == bytes([0x12, 0x34, 0x56, 0x78] * 4)

    # Test BSL_CMD_READ_PARTITION
    channel.send_msg(BslCmd.READ_PARTITION)
    rep, ptable_data = channel.recv_msg()
    assert rep == BslRep.READ_PARTITION
    assert len(ptable_data) % 0x4C == 0

    transport.disconnect()


def test_simulation_mock_device_partitions() -> None:
    device = MockUnisocDevice()
    assert "boot" in device.partitions
    assert "recovery" in device.partitions
    assert device.partitions["boot"][:8] == b"ANDROID!"
    assert device.partitions["vbmeta"][:4] == b"AVB0"


def test_create_transport_simulation() -> None:
    transport = create_transport(simulate=True)
    assert isinstance(transport, SimulationTransport)
    assert transport.name == "SimulationTransport"


def test_create_transport_auto_raises_when_no_hardware() -> None:
    with pytest.raises(TransportError):
        create_transport(transport_type="auto")


def test_channel9_fallback_on_64bit_or_non_windows() -> None:
    ch9 = Channel9Transport(port_num=1)
    # Connect should fall back to PySerial
    try:
        ch9.connect()
    except TransportError:
        # Expected on machines without COM1
        pass
    assert ch9._fallback_serial is not None
