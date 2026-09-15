"""Unisoc BSL Bootloader Engine handling BROM handshake and FDL1/FDL2 staging."""

from __future__ import annotations

import re
import struct
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from ..core.channel import BslError, BslTimeoutError
from ..core.const import (
    DEFAULT_BLK_SIZE,
    BslCmd,
    BslRep,
    BslStage,
)
from ..core.framing import FramingError
from ..transports.base import TransportError

if TYPE_CHECKING:
    from ..core.channel import SpdChannel


class BootError(Exception):
    """Raised when the BSL handshake or boot stages fail."""


DIAG_AUTODLOADER_CMD = (
    bytes([0x7E, 0x00, 0x00, 0x00, 0x00, 0x20, 0x00, 0x68, 0x00])
    + b'AT+SPREF="AUTODLOADER"\r\n'
    + bytes([0x7E])
)


def build_diag_payload(bootmode: int = 0, at: bool = False) -> bytes:
    """Build diagnostic mode switch packet (matching C ChangeMode)."""
    payload = bytearray([0x7E, 0x00, 0x00, 0x00, 0x00, 0x08, 0x00, 0xFE, 0x00, 0x7E])
    if not bootmode:
        payload[8] = 0x82
    elif at:
        payload[8] = 0x81
    else:
        payload[8] = (bootmode + 0x80) & 0xFF
    return bytes(payload)


class BootEngine:
    """Manages the multi-stage BSL boot sequence (BROM -> FDL1 -> FDL2)."""

    def __init__(self, channel: SpdChannel) -> None:
        self.channel = channel

    def kick(
        self,
        bootmode: int = 0,
        at: bool = False,
        timeout: float = 10.0,
    ) -> bool:
        """Switch device from diagnostic/calibration mode into download (BROM) mode.

        Matches C ChangeMode() implementation.
        """
        logger.info(
            f"Kicking device to download mode (bootmode: {bootmode}, at: {at})..."
        )
        start_time = time.time()

        # 1. If bootmode == 0, send 10-byte 0x7E hello burst first
        if not bootmode:
            hello = bytes([0x7E] * 10)
            self.channel.transport.write(hello)
            resp = self.channel.transport.read(64, timeout=0.5)
            if resp and len(resp) >= 3 and resp[2] in (
                BslRep.VER,
                BslRep.VERIFY_ERROR,
                BslRep.UNKNOW_CMD,
                BslRep.ACK,
            ):
                logger.info("Device already responded in download/BROM mode")
                return True

        # 2. Send diag switch packet
        payload = build_diag_payload(bootmode=bootmode, at=at)
        self.channel.transport.write(payload)
        resp = self.channel.transport.read(64, timeout=1.0)

        if resp and len(resp) >= 3 and resp[2] in (
            BslRep.VER,
            BslRep.VERIFY_ERROR,
            BslRep.UNKNOW_CMD,
            BslRep.ACK,
        ):
            logger.info("Device successfully switched to download mode")
            return True

        # 3. If phone didn't acknowledge directly, fallback to AT+SPREF="AUTODLOADER"
        time.sleep(0.5)
        self.channel.transport.write(DIAG_AUTODLOADER_CMD)
        self.channel.transport.read(64, timeout=1.0)

        # 4. Wait for device reconnection / readiness
        while time.time() - start_time < timeout:
            try:
                self.channel.reset_decoder()
                self.channel.send_msg(BslCmd.CHECK_BAUD, bytes([0x7E] * 8))
                rep, _ = self.channel.exec_cmd(
                    BslCmd.CONNECT, timeout=0.5, check_ack=False
                )
                if rep in (BslRep.ACK, BslRep.VER):
                    logger.info("Device successfully reconnected in download mode!")
                    return True
            except (
                BslError,
                BslTimeoutError,
                FramingError,
                TransportError,
                OSError,
            ) as e:
                logger.trace(f"Reconnection poll failed: {e}")
            time.sleep(0.2)

        logger.warning(
            "Kick timeout reached; phone may need manual reboot into download mode."
        )
        return False

    def handshake(self, max_retries: int = 15, retry_interval: float = 0.2) -> BslStage:
        """Establish initial BSL handshake with target device.

        Sends CHECK_BAUD delimiter packets and CONNECT commands to synchronize with BROM/FDL.
        Returns the detected active BslStage.
        """
        logger.debug("Attempting handshake with Unisoc BSL...")

        for attempt in range(1, max_retries + 1):
            try:
                # 1. Send check-baud synchronization burst (0x7E)
                self.channel.send_msg(BslCmd.CHECK_BAUD, bytes([0x7E] * 8))
                time.sleep(0.05)

                # 2. Send BSL_CMD_CONNECT
                self.channel.reset_decoder()
                rep, payload = self.channel.exec_cmd(
                    BslCmd.CONNECT, timeout=0.5, check_ack=False
                )
                if rep in (BslRep.ACK, BslRep.VER):
                    # Check version or payload
                    ver_str = payload.decode("ascii", errors="ignore").strip()
                    logger.info(
                        f"Handshake successful on attempt {attempt}! Device reported: '{ver_str or 'OK'}'"
                    )

                    # If channel is currently disconnected, detect stage
                    if self.channel.stage == BslStage.DISCONNECTED:
                        self.channel.stage = BslStage.BROM
                    return self.channel.stage
            except (
                BslError,
                BslTimeoutError,
                FramingError,
                TransportError,
                OSError,
            ) as e:
                logger.trace(f"Handshake attempt {attempt} failed: {e}")
                time.sleep(retry_interval)

        raise BootError(
            "Failed to handshake with device. Ensure phone is connected in BROM/FDL mode."
        )

    def send_file(
        self,
        data: bytes,
        dest_addr: int,
        blk_size: int = DEFAULT_BLK_SIZE,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        """Upload a binary image (FDL1, FDL2, SML, TrustOS) to target memory address."""
        total_len = len(data)
        logger.debug(
            f"Sending image ({total_len} bytes) to address 0x{dest_addr:08X}..."
        )

        # 1. BSL_CMD_START_DATA: [Address: 4B BE] [Length: 4B BE]
        start_payload = struct.pack(">II", dest_addr, total_len)
        self.channel.exec_cmd(BslCmd.START_DATA, start_payload)

        # 2. BSL_CMD_MIDST_DATA: Data chunks
        offset = 0
        while offset < total_len:
            chunk = data[offset : offset + blk_size]
            self.channel.exec_cmd(BslCmd.MIDST_DATA, chunk)
            offset += len(chunk)
            if progress_callback:
                progress_callback(offset, total_len)

        # 3. BSL_CMD_END_DATA
        self.channel.exec_cmd(BslCmd.END_DATA)
        logger.debug("Image upload complete")

    def exec_data(self) -> None:
        """Trigger execution of uploaded FDL/SPL image."""
        logger.debug("Executing uploaded code...")
        self.channel.exec_cmd(BslCmd.EXEC_DATA)

    def change_baudrate(self, new_baud: int) -> None:
        """Request device switch to higher baudrate (e.g., 921600)."""
        logger.info(f"Requesting device baud rate change to {new_baud}...")
        payload = struct.pack(">I", new_baud)
        self.channel.exec_cmd(BslCmd.CHANGE_BAUD, payload)
        if hasattr(self.channel.transport, "set_baudrate"):
            self.channel.transport.set_baudrate(new_baud)
        time.sleep(0.05)

    def boot(
        self,
        fdl1: Path | bytes,
        fdl1_addr: int,
        fdl2: Path | bytes | None = None,
        fdl2_addr: int | None = None,
        exec_addr: int | None = None,
        kick: bool = False,
        kick_mode: int = 0,
        progress_cb: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Execute full multi-stage boot sequence from BROM to FDL2."""
        if kick:
            self.kick(bootmode=kick_mode)

        # Initial handshake
        self.handshake()

        # CVE-2022-38694 signature bypass if exec_addr provided
        if exec_addr is not None:
            logger.info(
                f"Applying BROM signature verification bypass at 0x{exec_addr:08X} (CVE-2022-38694)..."
            )
            self.channel.exec_cmd(BslCmd.START_DATA, struct.pack(">II", exec_addr, 0))
            self.channel.exec_cmd(BslCmd.END_DATA)

        # Stage 1: Load and execute FDL1
        fdl1_bytes = fdl1.read_bytes() if isinstance(fdl1, Path) else fdl1
        logger.info(f"Loading FDL1 ({len(fdl1_bytes)} bytes) to 0x{fdl1_addr:08X}...")

        def cb1(curr: int, tot: int) -> None:
            if progress_cb:
                progress_cb("FDL1", curr, tot)

        self.send_file(fdl1_bytes, fdl1_addr, progress_callback=cb1)
        self.exec_data()
        self.channel.stage = BslStage.FDL1
        time.sleep(0.1)

        # Handshake with FDL1
        self.handshake()

        # Stage 2: Load and execute FDL2 if provided
        if fdl2 is not None and fdl2_addr is not None:
            fdl2_bytes = fdl2.read_bytes() if isinstance(fdl2, Path) else fdl2
            logger.info(
                f"Loading FDL2 ({len(fdl2_bytes)} bytes) to 0x{fdl2_addr:08X}..."
            )

            def cb2(curr: int, tot: int) -> None:
                if progress_cb:
                    progress_cb("FDL2", curr, tot)

            self.send_file(fdl2_bytes, fdl2_addr, progress_callback=cb2)
            self.exec_data()
            self.channel.stage = BslStage.FDL2
            self.channel.use_crc16 = True  # FDL2 switches to CRC16
            time.sleep(0.1)

            # Handshake with FDL2
            self.handshake()
            logger.info(
                "Device successfully booted to FDL2 stage! Ready for operations."
            )


def parse_address_from_filename(filename: str | Path) -> int | None:
    """Extract hexadecimal address encoded in filename (e.g., 'fdl1_0x40004000.bin' -> 0x40004000)."""
    stem = Path(filename).stem
    match = re.search(r"0x([0-9a-fA-F]+)", stem)
    if match:
        return int(match.group(1), 16)
    return None
