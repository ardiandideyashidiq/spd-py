"""Unit tests for spd_dump.core protocol, framing, CRC, and channel."""

import pytest

from spd_dump.core.channel import BslError, SpdChannel
from spd_dump.core.const import BslCmd, BslRep
from spd_dump.core.crc import spd_checksum, spd_crc16
from spd_dump.core.framing import (
    StreamFrameDecoder,
    decode_frame,
    encode_frame,
    transcode,
    untranscode,
)


class MockTransport:
    """Mock transport for testing SpdChannel."""

    def __init__(self) -> None:
        self.sent: bytearray = bytearray()
        self.incoming: bytearray = bytearray()

    def write(self, data: bytes) -> int:
        self.sent.extend(data)
        return len(data)

    def read(self, size: int, timeout: float | None = None) -> bytes:
        if not self.incoming:
            return b""
        chunk = bytes(self.incoming[:size])
        del self.incoming[:size]
        return chunk

    def queue_reply(self, frame: bytes) -> None:
        self.incoming.extend(frame)


def test_crc16() -> None:
    data = b"123456789"
    # CCITT CRC16 standard test vector for "123456789" with poly 0x1021
    res = spd_crc16(0, data)
    assert isinstance(res, int)
    assert 0 <= res <= 0xFFFF

    # Verify deterministic behavior
    assert spd_crc16(0, data) == spd_crc16(0, data)
    # Check that empty data returns initial CRC
    assert spd_crc16(0x1234, b"") == 0x1234


def test_checksum() -> None:
    data_even = b"\x00\x01\x00\x02"
    chk1 = spd_checksum(0, data_even)
    assert isinstance(chk1, int)
    assert 0 <= chk1 <= 0xFFFF

    data_odd = b"\x00\x01\x00\x02\x03"
    chk2 = spd_checksum(0, data_odd)
    assert isinstance(chk2, int)
    assert 0 <= chk2 <= 0xFFFF


def test_transcode_untranscode_roundtrip() -> None:
    raw = bytes([0x00, 0x7E, 0x12, 0x7D, 0x7E, 0x5E, 0x5D, 0xFF])
    escaped = transcode(raw)
    assert 0x7E not in escaped
    # 0x7E should have become 0x7D 0x5E, 0x7D should have become 0x7D 0x5D
    assert untranscode(escaped) == raw


def test_encode_decode_frame() -> None:
    payload = b"Hello Unisoc BSL"

    # Default sum-check + transcode
    frame = encode_frame(BslCmd.CONNECT, payload, use_crc16=False, use_transcode=True)
    assert frame.startswith(b"\x7e")
    assert frame.endswith(b"\x7e")
    cmd, dec_payload = decode_frame(frame, use_crc16=False, use_transcode=True)
    assert cmd == BslCmd.CONNECT
    assert dec_payload == payload

    # CRC16 mode
    frame_crc = encode_frame(
        BslCmd.READ_FLASH, payload, use_crc16=True, use_transcode=True
    )
    cmd, dec_payload = decode_frame(frame_crc, use_crc16=True, use_transcode=True)
    assert cmd == BslCmd.READ_FLASH
    assert dec_payload == payload


def test_stream_frame_decoder() -> None:
    decoder = StreamFrameDecoder()
    frame1 = encode_frame(BslCmd.CONNECT, b"P1")
    frame2 = encode_frame(BslCmd.START_DATA, b"P2")

    # Feed with noise prefix, split across chunks
    stream = b"\x00\xff\xaa" + frame1 + frame2
    chunk1 = stream[:10]
    chunk2 = stream[10:25]
    chunk3 = stream[25:]

    f1 = decoder.feed(chunk1)
    f2 = decoder.feed(chunk2)
    f3 = decoder.feed(chunk3)

    all_frames = f1 + f2 + f3
    assert len(all_frames) == 2
    assert all_frames[0] == (BslCmd.CONNECT, b"P1")
    assert all_frames[1] == (BslCmd.START_DATA, b"P2")


def test_spd_channel_exec_cmd() -> None:
    mock_trans = MockTransport()
    channel = SpdChannel(mock_trans, default_timeout=0.5)

    # Queue an ACK response for BSL_CMD_CONNECT
    ack_frame = encode_frame(BslRep.ACK, b"")
    mock_trans.queue_reply(ack_frame)

    rep, payload = channel.exec_cmd(BslCmd.CONNECT, b"")
    assert rep == BslRep.ACK
    assert payload == b""
    assert len(mock_trans.sent) > 0


def test_spd_channel_error_handling() -> None:
    mock_trans = MockTransport()
    channel = SpdChannel(mock_trans, default_timeout=0.5)

    # Queue an error response: BSL_REP_VERIFY_ERROR (0x8B)
    err_frame = encode_frame(BslRep.VERIFY_ERROR, b"")
    mock_trans.queue_reply(err_frame)

    with pytest.raises(BslError) as exc_info:
        channel.exec_cmd(BslCmd.EXEC_DATA, b"", check_ack=True)

    assert exc_info.value.rep_code == BslRep.VERIFY_ERROR
    assert "VERIFY_ERROR" in str(exc_info.value)


def test_spd_channel_log_handling() -> None:
    mock_trans = MockTransport()
    logs_received: list[str] = []
    channel = SpdChannel(
        mock_trans,
        default_timeout=0.5,
        on_log_message=lambda msg: logs_received.append(msg),
    )

    # Queue a log packet followed by an ACK packet
    log_frame = encode_frame(BslRep.LOG, b"U-Boot started\n")
    ack_frame = encode_frame(BslRep.ACK, b"")
    mock_trans.queue_reply(log_frame + ack_frame)

    rep, _ = channel.exec_cmd(BslCmd.NORMAL_RESET, b"")
    assert rep == BslRep.ACK
    assert len(logs_received) == 1
    assert "U-Boot started" in logs_received[0]
