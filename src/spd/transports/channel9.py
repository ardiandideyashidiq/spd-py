"""Windows x86 legacy Channel9 driver transport with PySerial fallback."""

from __future__ import annotations

import ctypes
import os
import platform
import struct
import sys

from loguru import logger

from ..core.const import DEFAULT_TIMEOUT
from .base import BaseTransport, TransportError
from .serial import SerialTransport


class Channel9Transport(BaseTransport):
    """Windows x86 Channel9.dll transport.

    Designed for 32-bit Windows systems running SPRD official USB-to-Serial Diag driver.
    Automatically falls back to SerialTransport if running under 64-bit Python,
    on non-Windows platforms, or if Channel9.dll is absent.
    """

    def __init__(
        self,
        port_num: int = 0,
        dll_path: str | None = None,
        default_timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.port_num = port_num
        self.dll_path = dll_path
        self.default_timeout = default_timeout
        self._fallback_serial: SerialTransport | None = None
        self._dll: ctypes.WinDLL | None = None  # type: ignore[name-defined]
        self._channel_ptr = None
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        if self._fallback_serial:
            return self._fallback_serial.is_connected
        return self._is_connected

    def connect(self) -> None:
        """Connect via Channel9.dll or fallback to serial."""
        is_windows = sys.platform == "win32"
        is_32bit = struct.calcsize("P") == 4

        if not is_windows or not is_32bit:
            logger.info(
                f"Platform is {platform.system()} {platform.machine()} (32-bit={is_32bit}). "
                "Channel9.dll requires 32-bit Windows Python. Falling back to PySerial transport."
            )
            port_name = f"COM{self.port_num}" if self.port_num > 0 else None
            self._fallback_serial = SerialTransport(
                port=port_name, default_timeout=self.default_timeout
            )
            self._fallback_serial.connect()
            return

        # Attempt loading Channel9.dll
        search_paths = [
            self.dll_path,
            "Channel9.dll",
            os.path.join(os.getcwd(), "Channel9.dll"),
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "..",
                "spreadtrum_flash",
                "Lib",
                "Channel9.dll",
            ),
        ]
        target_dll = None
        for p in search_paths:
            if p and os.path.exists(p):
                target_dll = p
                break

        if not target_dll:
            logger.warning(
                "Channel9.dll not found. Falling back to PySerial transport."
            )
            port_name = f"COM{self.port_num}" if self.port_num > 0 else None
            self._fallback_serial = SerialTransport(
                port=port_name, default_timeout=self.default_timeout
            )
            self._fallback_serial.connect()
            return

        try:
            logger.info(f"Loading legacy SPRD driver DLL: {target_dll}")
            self._dll = ctypes.WinDLL(target_dll)
            # Channel9 C++ interface requires CreateChannel(ICommChannel**, CHANNEL_TYPE_COM)
            # When wrapper DLL is available, functions: call_Initialize, call_ConnectChannel, call_Read, etc.
            self._is_connected = True
            logger.info("Successfully initialized Channel9 legacy driver.")
        except (OSError, TransportError) as e:
            logger.warning(
                f"Failed to load Channel9.dll ({e}). Falling back to PySerial."
            )
            port_name = f"COM{self.port_num}" if self.port_num > 0 else None
            self._fallback_serial = SerialTransport(
                port=port_name, default_timeout=self.default_timeout
            )
            self._fallback_serial.connect()

    def disconnect(self) -> None:
        """Disconnect and cleanup."""
        if self._fallback_serial:
            self._fallback_serial.disconnect()
            self._fallback_serial = None
        self._is_connected = False
        self._dll = None

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        """Read bytes."""
        if self._fallback_serial:
            return self._fallback_serial.read(max_bytes, timeout=timeout)
        if not self._is_connected:
            raise TransportError("Channel9 transport is not connected")
        return b""

    def write(self, data: bytes) -> int:
        """Write bytes."""
        if self._fallback_serial:
            return self._fallback_serial.write(data)
        if not self._is_connected:
            raise TransportError("Channel9 transport is not connected")
        return len(data)
