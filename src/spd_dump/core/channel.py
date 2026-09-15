"""High-level BSL protocol communication channel."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from loguru import logger

from .const import (
    DEFAULT_TIMEOUT,
    FLAGS_CRC16,
    FLAGS_TRANSCODE,
    BslCmd,
    BslRep,
    BslStage,
    get_response_description,
)
from .framing import StreamFrameDecoder, encode_frame

if TYPE_CHECKING:
    from ..transports.base import BaseTransport


class BslError(Exception):
    """Exception raised when a BSL command fails or returns an error status."""

    def __init__(
        self, rep_code: int, message: str | None = None, payload: bytes = b""
    ) -> None:
        self.rep_code = rep_code
        self.payload = payload
        desc = message or get_response_description(rep_code)
        super().__init__(f"BSL error 0x{rep_code:02X}: {desc}")


class BslTimeoutError(Exception):
    """Raised when an operation or response times out."""


class SpdChannel:
    """Unified communication channel handling packet framing, timeouts, and state tracking.

    Works identically with any BaseTransport implementation (USB, Serial, Channel9, Simulator).
    """

    def __init__(
        self,
        transport: BaseTransport,
        default_timeout: float = DEFAULT_TIMEOUT,
        on_log_message: Callable[[str], None] | None = None,
    ) -> None:
        self.transport = transport
        self.default_timeout = default_timeout
        self.stage = BslStage.DISCONNECTED
        self.flags = (
            FLAGS_TRANSCODE  # Default flags: transcode enabled, sum-check enabled
        )
        self.on_log_message = on_log_message or self._default_log_handler
        self._decoder = StreamFrameDecoder(
            use_crc16=self.use_crc16,
            use_transcode=self.use_transcode,
        )

    @property
    def use_crc16(self) -> bool:
        return bool(self.flags & FLAGS_CRC16)

    @use_crc16.setter
    def use_crc16(self, value: bool) -> None:
        if value:
            self.flags |= FLAGS_CRC16
        else:
            self.flags &= ~FLAGS_CRC16
        self._decoder.use_crc16 = value

    @property
    def use_transcode(self) -> bool:
        return bool(self.flags & FLAGS_TRANSCODE)

    @use_transcode.setter
    def use_transcode(self, value: bool) -> None:
        if value:
            self.flags |= FLAGS_TRANSCODE
        else:
            self.flags &= ~FLAGS_TRANSCODE
        self._decoder.use_transcode = value

    def _default_log_handler(self, msg: str) -> None:
        logger.debug(f"[Device Log] {msg.strip()}")

    def reset_decoder(self) -> None:
        """Reset internal frame decoder buffer."""
        self._decoder.reset()

    def send_msg(self, cmd_type: int | BslCmd, data: bytes = b"") -> None:
        """Frame and transmit a BSL command packet."""
        frame = encode_frame(
            cmd_type=cmd_type,
            data=data,
            use_crc16=self.use_crc16,
            use_transcode=self.use_transcode,
        )
        self.transport.write(frame)

    def recv_msg(self, timeout: float | None = None) -> tuple[int, bytes]:
        """Receive the next valid BSL response frame.

        Filters out asynchronous device logs (BSL_REP_LOG 0xFF).
        """
        deadline = time.monotonic() + (
            timeout if timeout is not None else self.default_timeout
        )

        while True:
            # Check if any frames already decoded
            remaining_time = max(0.05, deadline - time.monotonic())
            if time.monotonic() > deadline:
                raise BslTimeoutError("Timed out waiting for BSL response frame")

            chunk = self.transport.read(4096, timeout=remaining_time)
            if not chunk:
                if time.monotonic() >= deadline:
                    raise BslTimeoutError("Timed out waiting for BSL response frame")
                continue

            frames = self._decoder.feed(chunk)
            for rep_type, payload in frames:
                if rep_type == BslRep.LOG:
                    try:
                        text = payload.decode("utf-8", errors="replace")
                        self.on_log_message(text)
                    except UnicodeDecodeError as exc:
                        logger.debug(f"Failed to decode device log message: {exc}")
                    continue
                return rep_type, payload

    def exec_cmd(
        self,
        cmd_type: int | BslCmd,
        data: bytes = b"",
        timeout: float | None = None,
        check_ack: bool = True,
    ) -> tuple[int, bytes]:
        """Send a command and await the response.

        If check_ack is True, raises BslError if response is not BslRep.ACK (0x80).
        """
        self.send_msg(cmd_type, data)
        rep_type, payload = self.recv_msg(timeout=timeout)

        if check_ack and rep_type != BslRep.ACK:
            raise BslError(rep_type, payload=payload)

        return rep_type, payload

    def read_raw(self, size: int, timeout: float | None = None) -> bytes:
        """Read raw bytes directly from transport without framing."""
        return self.transport.read(size, timeout=timeout)

    def write_raw(self, data: bytes) -> int:
        """Write raw bytes directly to transport without framing."""
        return self.transport.write(data)
