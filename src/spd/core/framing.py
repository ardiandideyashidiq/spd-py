"""HDLC framing and transcoding for Unisoc BSL communication."""

from __future__ import annotations

import struct

from .const import HDLC_ESCAPE, HDLC_ESCAPE_MASK, HDLC_HEADER, BslCmd
from .crc import spd_checksum, spd_crc16


class FramingError(Exception):
    """Raised when an HDLC frame is malformed or fails checksum validation."""


def transcode(data: bytes | bytearray) -> bytes:
    """Escape 0x7E and 0x7D bytes according to HDLC transcode rules."""
    out = bytearray()
    for b in data:
        if b in (HDLC_HEADER, HDLC_ESCAPE):
            out.append(HDLC_ESCAPE)
            out.append(b ^ HDLC_ESCAPE_MASK)
        else:
            out.append(b)
    return bytes(out)


def untranscode(data: bytes | bytearray) -> bytes:
    """Unescape HDLC escaped sequence (0x7D 0x5E -> 0x7E, 0x7D 0x5D -> 0x7D)."""
    out = bytearray()
    escape = False
    for b in data:
        if escape:
            out.append(b ^ HDLC_ESCAPE_MASK)
            escape = False
        elif b == HDLC_ESCAPE:
            escape = True
        else:
            out.append(b)
    if escape:
        raise FramingError("Frame ended with incomplete escape sequence")
    return bytes(out)


def encode_frame(
    cmd_type: int | BslCmd,
    data: bytes = b"",
    use_crc16: bool = False,
    use_transcode: bool = True,
) -> bytes:
    """Encode a command and payload into a framed BSL packet.

    Format before escaping:
    [Type: 2B BE] [Len: 2B BE] [Payload: Len bytes] [Checksum/CRC: 2B BE]
    Enclosed between HDLC_HEADER (0x7E).
    """
    if cmd_type == BslCmd.CHECK_BAUD:
        # CHECK_BAUD is sent as raw 0x7E bytes
        count = len(data) if data else 1
        return bytes([HDLC_HEADER] * count)

    data_len = len(data)
    if data_len > 0xFFFF:
        raise FramingError(f"Payload length {data_len} exceeds max 65535 bytes")

    # Construct unescaped body
    header = struct.pack(">HH", int(cmd_type), data_len)
    body = header + data

    if use_crc16:
        chk = spd_crc16(0, body)
    else:
        chk = spd_checksum(0, body)

    full_packet = body + struct.pack(">H", chk)

    if use_transcode:
        encoded = transcode(full_packet)
    else:
        encoded = full_packet

    return bytes([HDLC_HEADER]) + encoded + bytes([HDLC_HEADER])


def decode_frame(
    raw_frame: bytes,
    use_crc16: bool = False,
    use_transcode: bool = True,
) -> tuple[int, bytes]:
    """Decode an extracted HDLC frame (including or excluding surrounding 0x7E).

    Returns:
        (rep_type, payload)
    Raises:
        FramingError on checksum mismatch or corrupt format.
    """
    # Strip leading/trailing 0x7E
    frame = raw_frame.strip(bytes([HDLC_HEADER]))
    if not frame:
        raise FramingError("Empty frame")

    if use_transcode:
        unpacked = untranscode(frame)
    else:
        unpacked = frame

    if len(unpacked) < 6:  # 2 bytes type + 2 bytes len + 2 bytes chk
        raise FramingError(f"Frame length {len(unpacked)} too short (< 6 bytes)")

    rep_type, data_len = struct.unpack_from(">HH", unpacked, 0)
    expected_len = 4 + data_len + 2
    if len(unpacked) != expected_len:
        raise FramingError(
            f"Frame size mismatch: header declares payload len {data_len} (total {expected_len}), got {len(unpacked)}"
        )

    payload = unpacked[4 : 4 + data_len]
    (received_chk,) = struct.unpack_from(">H", unpacked, 4 + data_len)

    body = unpacked[: 4 + data_len]
    if use_crc16:
        calc_chk = spd_crc16(0, body)
    else:
        calc_chk = spd_checksum(0, body)

    if calc_chk != received_chk:
        raise FramingError(
            f"Checksum error for response 0x{rep_type:02X}: calculated 0x{calc_chk:04X} != received 0x{received_chk:04X}"
        )

    return rep_type, payload


class StreamFrameDecoder:
    """Streaming decoder that accumulates incoming chunks and extracts valid frames."""

    def __init__(self, use_crc16: bool = False, use_transcode: bool = True) -> None:
        self.use_crc16 = use_crc16
        self.use_transcode = use_transcode
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[tuple[int, bytes]]:
        """Feed new received data and return all newly completed (cmd_type, payload) frames."""
        self._buffer.extend(chunk)
        frames: list[tuple[int, bytes]] = []

        while True:
            # Look for starting 0x7E
            start_idx = self._buffer.find(HDLC_HEADER)
            if start_idx == -1:
                self._buffer.clear()
                break

            # Discard any junk before start delimiter
            if start_idx > 0:
                del self._buffer[:start_idx]

            # Look for terminating 0x7E
            end_idx = self._buffer.find(HDLC_HEADER, 1)
            if end_idx == -1:
                # Incomplete frame, wait for more data
                break

            # If consecutive 0x7E headers (e.g. 0x7E 0x7E), skip first one
            if end_idx == 1:
                del self._buffer[:1]
                continue

            raw_frame = bytes(self._buffer[: end_idx + 1])
            del self._buffer[: end_idx + 1]

            try:
                decoded = decode_frame(
                    raw_frame,
                    use_crc16=self.use_crc16,
                    use_transcode=self.use_transcode,
                )
                frames.append(decoded)
            except FramingError:
                # Frame corrupted, keep searching next frames
                continue

        return frames

    def reset(self) -> None:
        """Clear internal buffer."""
        self._buffer.clear()
