"""Serial / COM port transport using PySerial."""

from __future__ import annotations

import serial
import serial.tools.list_ports
from loguru import logger

from ..core.const import DEFAULT_BAUDRATE, DEFAULT_TIMEOUT, SPRD_VID
from .base import BaseTransport, TransportError


class SerialTransport(BaseTransport):
    """Serial communication backend using PySerial."""

    def __init__(
        self,
        port: str | None = None,
        baudrate: int = DEFAULT_BAUDRATE,
        default_timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.default_timeout = default_timeout
        self.serial: serial.Serial | None = None

    @property
    def is_connected(self) -> bool:
        return self.serial is not None and self.serial.is_open

    def connect(self) -> None:
        """Open the serial port. If port is None, auto-detects SPRD serial ports."""
        if self.is_connected:
            return

        port_name = self.port
        if not port_name:
            port_name = self.find_sprd_port()
            if not port_name:
                raise TransportError(
                    "No Unisoc / Spreadtrum serial port detected. Please specify --port manually."
                )

        logger.info(f"Connecting to serial port {port_name} at {self.baudrate} baud...")
        try:
            self.serial = serial.Serial(
                port=port_name,
                baudrate=self.baudrate,
                timeout=self.default_timeout,
                write_timeout=self.default_timeout,
            )
            # Toggle DTR/RTS as standard for boot mode handshake
            self.serial.dtr = False
            self.serial.rts = False
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
        except serial.SerialException as e:
            raise TransportError(f"Failed to open serial port {port_name}: {e}") from e

    def disconnect(self) -> None:
        """Close serial port."""
        if self.serial is not None:
            try:
                if self.serial.is_open:
                    self.serial.close()
            except serial.SerialException as e:
                logger.debug(f"Error closing serial port: {e}")
            finally:
                self.serial = None

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        """Read data from serial port within timeout."""
        if not self.is_connected or self.serial is None:
            raise TransportError("Serial transport is not connected")

        orig_timeout = self.serial.timeout
        try:
            if timeout is not None:
                self.serial.timeout = timeout
            data = self.serial.read(max_bytes)
            return data
        except serial.SerialException as e:
            raise TransportError(f"Serial read error: {e}") from e
        finally:
            if timeout is not None:
                self.serial.timeout = orig_timeout

    def write(self, data: bytes) -> int:
        """Write data to serial port."""
        if not self.is_connected or self.serial is None:
            raise TransportError("Serial transport is not connected")

        try:
            n = self.serial.write(data)
            self.serial.flush()
            return n
        except serial.SerialException as e:
            raise TransportError(f"Serial write error: {e}") from e

    def set_baudrate(self, new_baud: int) -> None:
        """Change current serial baud rate."""
        if self.serial and self.serial.is_open:
            logger.info(f"Switching serial port baud rate to {new_baud}...")
            self.baudrate = new_baud
            self.serial.baudrate = new_baud
            self.serial.flush()

    @staticmethod
    def find_sprd_port() -> str | None:
        """Auto-detect Unisoc / Spreadtrum serial/COM port."""
        ports = serial.tools.list_ports.comports()
        for p in ports:
            # Check VID or description strings
            if (
                p.vid == SPRD_VID
                or "SPRD" in (p.description or "").upper()
                or "UNISOC" in (p.description or "").upper()
            ):
                return p.device
        return None
