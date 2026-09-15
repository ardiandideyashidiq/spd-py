"""PyUSB transport for Unisoc devices (Linux, macOS, Windows, Termux)."""

from __future__ import annotations

import sys

import usb.core
import usb.util
from loguru import logger

from ..core.const import DEFAULT_TIMEOUT, SPRD_PIDS, SPRD_VID
from .base import BaseTransport, TransportError


class UsbTransport(BaseTransport):
    """USB communication backend using PyUSB / libusb."""

    def __init__(
        self,
        vid: int = SPRD_VID,
        pid: int | None = None,
        usb_fd: int | None = None,
        default_timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.vid = vid
        self.pid = pid
        self.usb_fd = usb_fd
        self.default_timeout = default_timeout
        self.dev: usb.core.Device | None = None
        self.ep_in: usb.core.Endpoint | None = None
        self.ep_out: usb.core.Endpoint | None = None
        self.interface_number: int = 0
        self._detached_kernel_driver: bool = False

    @property
    def is_connected(self) -> bool:
        return (
            self.dev is not None and self.ep_in is not None and self.ep_out is not None
        )

    def connect(self) -> None:
        """Find device, configure endpoints, and claim interface."""
        if self.is_connected:
            return

        logger.debug(f"Searching for USB device VID: 0x{self.vid:04X}...")

        if self.usb_fd is not None:
            # Android Termux OTG passthrough via file descriptor
            try:
                from usb.backend import libusb1

                backend = libusb1.get_backend()
                if backend and hasattr(backend.lib, "libusb_wrap_sys_device"):
                    import ctypes

                    handle = ctypes.c_void_p()
                    res = backend.lib.libusb_wrap_sys_device(
                        backend.ctx, ctypes.c_int(self.usb_fd), ctypes.byref(handle)
                    )
                    if res != 0:
                        raise TransportError(
                            f"libusb_wrap_sys_device failed with error code {res}"
                        )
                    dev_ptr = backend.lib.libusb_get_device(handle)
                    self.dev = usb.core.Device(dev_ptr, backend)
                else:
                    raise TransportError(
                        "libusb backend does not support wrapping file descriptors on this platform"
                    )
            except Exception as e:
                raise TransportError(
                    f"Failed to initialize USB with file descriptor {self.usb_fd}: {e}"
                ) from e
        else:
            # Standard PyUSB device search
            if self.pid is not None:
                self.dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
            else:
                # Search across known Unisoc PIDs or any matching VID
                def match_sprd(d: usb.core.Device) -> bool:
                    if d.idVendor != self.vid:
                        return False
                    return self.pid is None or d.idProduct in SPRD_PIDS

                self.dev = usb.core.find(custom_match=match_sprd)

        if self.dev is None:
            raise TransportError(
                f"No Unisoc device found (VID: 0x{self.vid:04X}"
                + (f", PID: 0x{self.pid:04X})" if self.pid else ")")
                + ". Ensure phone is in BROM/FDL download mode (hold Vol- / Vol+ while plugging in)."
            )

        logger.info(
            f"Found Unisoc USB device: VID=0x{self.dev.idVendor:04X}, PID=0x{self.dev.idProduct:04X}"
        )

        try:
            # Detach kernel driver if active (Linux/Android)
            if sys.platform.startswith("linux"):
                try:
                    if self.dev.is_kernel_driver_active(0):
                        self.dev.detach_kernel_driver(0)
                        self._detached_kernel_driver = True
                except (NotImplementedError, usb.core.USBError):
                    pass

            self.dev.set_configuration()
            cfg = self.dev.get_active_configuration()

            # Find bulk IN and OUT endpoints
            intf = cfg[(0, 0)]
            self.interface_number = intf.bInterfaceNumber

            ep_in = None
            ep_out = None
            for ep in intf:
                if (
                    usb.util.endpoint_direction(ep.bEndpointAddress)
                    == usb.util.ENDPOINT_IN
                    and usb.util.endpoint_type(ep.bmAttributes)
                    == usb.util.ENDPOINT_TYPE_BULK
                ):
                    ep_in = ep
                elif (
                    usb.util.endpoint_direction(ep.bEndpointAddress)
                    == usb.util.ENDPOINT_OUT
                    and usb.util.endpoint_type(ep.bmAttributes)
                    == usb.util.ENDPOINT_TYPE_BULK
                ):
                    ep_out = ep

            if ep_in is None or ep_out is None:
                raise TransportError(
                    "Failed to find bulk IN/OUT endpoints on Unisoc USB interface"
                )

            self.ep_in = ep_in
            self.ep_out = ep_out
            logger.debug(
                f"Configured USB endpoints: IN=0x{self.ep_in.bEndpointAddress:02X}, OUT=0x{self.ep_out.bEndpointAddress:02X}"
            )
        except usb.core.USBError as e:
            raise TransportError(f"USB configuration failed: {e}") from e

    def disconnect(self) -> None:
        """Release claimed interface and dispose device handle."""
        if self.dev is not None:
            try:
                usb.util.dispose_resources(self.dev)
                if self._detached_kernel_driver and sys.platform.startswith("linux"):
                    try:
                        self.dev.attach_kernel_driver(self.interface_number)
                    except (usb.core.USBError, NotImplementedError) as err:
                        logger.debug(f"Could not re-attach kernel driver: {err}")
            except usb.core.USBError as e:
                logger.debug(f"Error during USB cleanup: {e}")
            finally:
                self.dev = None
                self.ep_in = None
                self.ep_out = None

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        """Read bulk data from device."""
        if not self.is_connected or self.ep_in is None:
            raise TransportError("USB transport is not connected")

        timeout_ms = int(
            (timeout if timeout is not None else self.default_timeout) * 1000
        )
        try:
            raw = self.ep_in.read(max_bytes, timeout=max_ms(1, timeout_ms))
            return bytes(raw)
        except usb.core.USBTimeoutError:
            return b""
        except usb.core.USBError as e:
            # Code 110/ETIMEDOUT or specific timeouts
            if "timeout" in str(e).lower() or e.errno in (110, 60):
                return b""
            raise TransportError(f"USB read error: {e}") from e

    def write(self, data: bytes) -> int:
        """Write bulk data to device."""
        if not self.is_connected or self.ep_out is None:
            raise TransportError("USB transport is not connected")

        timeout_ms = int(self.default_timeout * 1000)
        try:
            return self.ep_out.write(data, timeout=max_ms(1000, timeout_ms))
        except usb.core.USBError as e:
            raise TransportError(f"USB write error: {e}") from e


def max_ms(floor_ms: int, timeout_ms: int) -> int:
    return max(floor_ms, timeout_ms)
