"""Transport factory and auto-detection routines."""

from __future__ import annotations

import sys

from loguru import logger

from ..core.const import DEFAULT_BAUDRATE, DEFAULT_TIMEOUT, SPRD_VID
from .base import BaseTransport, TransportError
from .channel9 import Channel9Transport
from .serial import SerialTransport
from .simulation import SimulationTransport
from .usb import UsbTransport


def create_transport(
    transport_type: str = "auto",
    port: str | None = None,
    baudrate: int = DEFAULT_BAUDRATE,
    vid: int = SPRD_VID,
    pid: int | None = None,
    usb_fd: int | None = None,
    simulate: bool = False,
    default_timeout: float = DEFAULT_TIMEOUT,
    sim_delay_ms: float = 0.0,
) -> BaseTransport:
    """Create and return the appropriate transport based on configuration and auto-detection.

    Supported transport_type values:
    - 'auto': Automatically detect USB device first, then Serial COM/tty port.
    - 'usb': Explicitly use PyUSB / libusb.
    - 'serial': Explicitly use PySerial on specified or auto-discovered COM port.
    - 'channel9': Use Windows x86 Channel9.dll driver with PySerial fallback.
    - 'sim': In-memory simulation mode (virtual Unisoc device).
    """
    mode = transport_type.lower().strip()

    if simulate or mode in ("sim", "simulate", "mock"):
        logger.info("Using Unisoc simulated hardware transport")
        return SimulationTransport(synthetic_delay_ms=sim_delay_ms)

    if usb_fd is not None or mode == "usb":
        return UsbTransport(
            vid=vid, pid=pid, usb_fd=usb_fd, default_timeout=default_timeout
        )

    if port is not None or mode == "serial":
        return SerialTransport(
            port=port, baudrate=baudrate, default_timeout=default_timeout
        )

    if mode in ("channel9", "sprd", "legacy"):
        port_num = 0
        if port and port.upper().startswith("COM"):
            try:
                port_num = int(port[3:])
            except ValueError:
                pass
        return Channel9Transport(port_num=port_num, default_timeout=default_timeout)

    # AUTO mode detection:
    # 1. First probe PyUSB
    try:
        usb_trans = UsbTransport(vid=vid, pid=pid, default_timeout=default_timeout)
        usb_trans.connect()
        logger.info("Auto-detected Unisoc USB device via PyUSB")
        return usb_trans
    except TransportError:
        logger.debug("No Unisoc USB device detected via PyUSB, probing serial ports...")

    # 2. Probe Serial COM ports
    sprd_port = SerialTransport.find_sprd_port()
    if sprd_port:
        logger.info(f"Auto-detected Unisoc serial port at {sprd_port}")
        return SerialTransport(
            port=sprd_port, baudrate=baudrate, default_timeout=default_timeout
        )

    # 3. Check Windows 32-bit Channel9
    if sys.platform == "win32":
        try:
            ch9 = Channel9Transport(default_timeout=default_timeout)
            ch9.connect()
            return ch9
        except TransportError as err:
            logger.debug(f"Channel9 probe failed: {err}")

    raise TransportError(
        "No Unisoc / Spreadtrum device detected (checked USB VID 0x1782 and Serial COM ports). "
        "Ensure phone is connected in BROM/FDL download mode (hold Vol- or Vol+ while connecting USB), "
        "or specify --sim to run in simulation mode."
    )
