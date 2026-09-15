"""High-fidelity Unisoc BSL hardware simulator and virtual device transport."""

from __future__ import annotations

import collections
import struct
import time
from typing import ClassVar

from loguru import logger

from ..core.const import (
    BslCmd,
    BslRep,
    BslStage,
)
from ..core.framing import decode_frame, encode_frame
from .base import BaseTransport


class MockUnisocDevice:
    """Full state-machine simulation of a Unisoc / Spreadtrum device in BROM/FDL mode."""

    DEFAULT_PARTITIONS: ClassVar[list[tuple[str, int]]] = [
        ("splloader", 256 * 1024),
        ("uboot", 2 * 1024 * 1024),
        ("sml", 1 * 1024 * 1024),
        ("trustos", 2 * 1024 * 1024),
        ("teecfg", 1 * 1024 * 1024),
        ("boot", 64 * 1024 * 1024),
        ("recovery", 64 * 1024 * 1024),
        ("misc", 1024 * 1024),
        ("miscdata", 1024 * 1024),
        ("vbmeta", 1024 * 1024),
        ("vbmeta_bak", 1024 * 1024),
        ("vbmeta_system", 1024 * 1024),
        ("vbmeta_vendor", 1024 * 1024),
        ("dtbo", 8 * 1024 * 1024),
        ("socko", 32 * 1024 * 1024),
        ("odmko", 32 * 1024 * 1024),
        ("system", 256 * 1024 * 1024),
        ("vendor", 128 * 1024 * 1024),
        ("product", 128 * 1024 * 1024),
        ("cache", 64 * 1024 * 1024),
        ("userdata", 512 * 1024 * 1024),
    ]

    def __init__(self, synthetic_delay_ms: float = 0.0) -> None:
        self.stage = BslStage.BROM
        self.synthetic_delay_ms = synthetic_delay_ms
        self.chip_uid = bytes([0x12, 0x34, 0x56, 0x78] * 4)
        self.chip_type = 0x9863  # Unisoc SC9863A / T606 / T616
        self.use_crc16 = False
        self.use_transcode = True
        self.baudrate = 115200
        self.active_slot = "a"
        self.dm_verity = True

        # In-memory flash storage
        self.partitions: dict[str, bytearray] = {}
        self._init_partitions()

        # Active operation buffers
        self._active_write_part: str | None = None
        self._active_write_buffer = bytearray()
        self._active_read_part: str | None = None
        self._active_read_offset = 0
        self._active_read_size = 0

    def _init_partitions(self) -> None:
        """Create mock synthetic partitions with valid image headers."""
        for name, size in self.DEFAULT_PARTITIONS:
            buf = bytearray(
                min(size, 1024 * 1024)
            )  # Cap memory buffer at 1MB per part in sim
            if name == "boot":
                # Inject Android boot header magic
                buf[:8] = b"ANDROID!"
            elif name.startswith("vbmeta"):
                # Inject AVB magic
                buf[:4] = b"AVB0"
            elif name == "uboot":
                buf[:4] = b"UBOT"
            self.partitions[name] = buf

        # Initialize synthetic PAC timestamp at miscdata:0x81400 (2024-01-15 12:00:00 UTC)
        if "miscdata" in self.partitions:
            pactime_raw = (1705320000 + 11644473600) * 10_000_000
            struct.pack_into("<Q", self.partitions["miscdata"], 0x81400, pactime_raw)

    def handle_raw_frame(self, raw_frame: bytes) -> list[bytes]:
        """Process an incoming HDLC frame and return response frame(s)."""
        if self.synthetic_delay_ms > 0:
            time.sleep(self.synthetic_delay_ms / 1000.0)

        # Handle raw CHECK_BAUD delimiter packets
        if set(raw_frame) == {0x7E}:
            # Device acknowledges baud check
            return [
                encode_frame(
                    BslRep.ACK,
                    b"",
                    use_crc16=self.use_crc16,
                    use_transcode=self.use_transcode,
                )
            ]

        # Handle diag mode kick packets (0xFE command or AUTODLOADER AT command)
        is_diag_fe = (
            len(raw_frame) == 10
            and raw_frame[0] == 0x7E
            and raw_frame[7] == 0xFE
            and raw_frame[9] == 0x7E
        )
        if b"AUTODLOADER" in raw_frame or is_diag_fe:
            return [
                encode_frame(
                    BslRep.VER,
                    b"SPRD3",
                    use_crc16=self.use_crc16,
                    use_transcode=self.use_transcode,
                )
            ]

        cmd_type, payload = decode_frame(
            raw_frame,
            use_crc16=self.use_crc16,
            use_transcode=self.use_transcode,
        )

        responses: list[tuple[int, bytes]] = []

        if cmd_type == BslCmd.CONNECT:
            responses.append((BslRep.ACK, b""))

        elif cmd_type == BslCmd.CHANGE_BAUD:
            if len(payload) >= 4:
                (self.baudrate,) = struct.unpack(">I", payload[:4])
            responses.append((BslRep.ACK, b""))

        elif cmd_type == BslCmd.DISABLE_TRANSCODE:
            self.use_transcode = False
            responses.append((BslRep.ACK, b""))

        elif cmd_type == BslCmd.START_DATA:
            # Download file or write to partition
            self._active_write_buffer.clear()
            if len(payload) >= 72:
                name_raw = (
                    payload[:72]
                    .decode("utf-16le", errors="ignore")
                    .split("\x00")[0]
                    .strip()
                )
                if name_raw:
                    self._active_write_part = name_raw
            responses.append((BslRep.ACK, b""))

        elif cmd_type == BslCmd.MIDST_DATA:
            self._active_write_buffer.extend(payload)
            responses.append((BslRep.ACK, b""))

        elif cmd_type == BslCmd.END_DATA:
            if self._active_write_part and self._active_write_part in self.partitions:
                self.partitions[self._active_write_part] = bytearray(
                    self._active_write_buffer
                )
            self._active_write_part = None
            responses.append((BslRep.ACK, b""))

        elif cmd_type == BslCmd.EXEC_DATA:
            # Transition execution stage
            if self.stage == BslStage.BROM:
                self.stage = BslStage.FDL1
                responses.append(
                    (BslRep.LOG, b"[Unisoc BROM] Jump to FDL1 successful\n")
                )
            elif self.stage == BslStage.FDL1:
                self.stage = BslStage.FDL2
                self.use_crc16 = True  # FDL2 typically enables CRC16
                responses.append(
                    (BslRep.LOG, b"[Unisoc FDL2] U-Boot 2020.07 (Simulated) Ready\n")
                )
            responses.append((BslRep.ACK, b""))

        elif cmd_type == BslCmd.READ_CHIP_UID:
            responses.append((BslRep.ACK, self.chip_uid))

        elif cmd_type == BslCmd.READ_CHIP_TYPE:
            responses.append((BslRep.ACK, struct.pack(">I", self.chip_type)))

        elif cmd_type == BslCmd.READ_PARTITION:
            # Build binary partition table matching Unisoc 0x4C entry format
            ptable_bytes = self._build_binary_partition_table()
            responses.append((BslRep.READ_PARTITION, ptable_bytes))

        elif cmd_type == BslCmd.READ_START:
            # Payload contains target name / id / size
            if len(payload) >= 72:
                name_raw = (
                    payload[:72]
                    .decode("utf-16le", errors="ignore")
                    .split("\x00")[0]
                    .strip()
                )
                if name_raw:
                    self._active_read_part = name_raw
            responses.append((BslRep.ACK, struct.pack(">I", 0x1000)))  # blk_size = 4096

        elif cmd_type == BslCmd.READ_FLASH:
            addr, size, offset = 0, 1024, 0
            if len(payload) >= 12:
                addr, size, offset = struct.unpack(">III", payload[:12])
            chunk = bytes([(addr + offset + i) & 0xFF for i in range(size)])
            responses.append((BslRep.READ_FLASH, chunk))

        elif cmd_type == BslCmd.READ_MIDST:
            size = 4096
            offset = 0
            if not self._active_read_part and len(payload) >= 12:
                # Memory dump format: BE (offset, size, 0)
                offset, size, _ = struct.unpack(">III", payload[:12])
            elif len(payload) >= 8:
                size, offset = struct.unpack("<II", payload[:8])

            # Return synthetic data pattern or partition data if available
            if self._active_read_part and self._active_read_part in self.partitions:
                part_buf = self.partitions[self._active_read_part]
                chunk = bytes(part_buf[offset : offset + size])
                if len(chunk) < size:
                    chunk += bytes(
                        [
                            (offset + len(chunk) + i) & 0xFF
                            for i in range(size - len(chunk))
                        ]
                    )
            else:
                chunk = bytes([(offset + i) & 0xFF for i in range(size)])
            responses.append((BslRep.READ_FLASH, chunk))

        elif cmd_type == BslCmd.WRITE_PARTITION_VALUE:
            if len(payload) >= 4:
                offset = struct.unpack("<I", payload[:4])[0]
                data = payload[4:]
                if self._active_read_part and self._active_read_part in self.partitions:
                    part_buf = self.partitions[self._active_read_part]
                    if offset + len(data) <= len(part_buf):
                        part_buf[offset : offset + len(data)] = data
            responses.append((BslRep.ACK, b""))

        elif cmd_type == BslCmd.READ_END or cmd_type == BslCmd.ERASE_FLASH:
            self._active_read_part = None
            responses.append((BslRep.ACK, b""))

        elif cmd_type == BslCmd.NORMAL_RESET:
            self.stage = BslStage.BROM
            responses.append((BslRep.ACK, b""))

        elif cmd_type == BslCmd.POWER_OFF:
            self.stage = BslStage.DISCONNECTED
            responses.append((BslRep.ACK, b""))

        elif (
            cmd_type == BslCmd.SET_FIRST_MODE
            or cmd_type == BslCmd.CHECK_ROOT
            or cmd_type == BslCmd.DISABLE_SELINUX
        ):
            responses.append((BslRep.ACK, b""))

        else:
            # Default ACK for any supported custom command
            responses.append((BslRep.ACK, b""))

        out_frames: list[bytes] = []
        for rep_code, rep_payload in responses:
            out_frames.append(
                encode_frame(
                    rep_code,
                    rep_payload,
                    use_crc16=self.use_crc16,
                    use_transcode=self.use_transcode,
                )
            )
        return out_frames

    def _build_binary_partition_table(self) -> bytes:
        """Construct binary partition table buffer (0x4C bytes per partition)."""
        table = bytearray()
        divisor = 10
        for name, size in self.DEFAULT_PARTITIONS:
            if name == "splloader":
                # splloader is physical boot0/boot1 block, not in GPT partition table
                continue
            entry = bytearray(0x4C)
            # Encode name in UTF-16LE (up to 36 chars = 72 bytes)
            name_utf16 = name.encode("utf-16le")[:72]
            entry[: len(name_utf16)] = name_utf16
            # Size at offset 0x48 (4 bytes LE)
            size_val = (size >> (20 - divisor)) & 0xFFFFFFFF
            struct.pack_into("<I", entry, 0x48, size_val)
            table.extend(entry)
        return bytes(table)


class SimulationTransport(BaseTransport):
    """In-memory transport directly wired to a MockUnisocDevice."""

    def __init__(
        self,
        mock_device: MockUnisocDevice | None = None,
        synthetic_delay_ms: float = 0.0,
    ) -> None:
        self.device = mock_device or MockUnisocDevice(
            synthetic_delay_ms=synthetic_delay_ms
        )
        self._incoming = collections.deque[bytes]()
        self._connected = False
        self._in_buffer = bytearray()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        self._connected = True
        logger.info("Connected to Unisoc Simulated Mock Device")

    def disconnect(self) -> None:
        self._connected = False
        self._incoming.clear()
        logger.info("Disconnected from Unisoc Simulated Mock Device")

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        if not self._connected:
            return b""
        if not self._incoming:
            return b""
        chunk = self._incoming.popleft()
        if len(chunk) > max_bytes:
            self._incoming.appendleft(chunk[max_bytes:])
            return chunk[:max_bytes]
        return chunk

    def write(self, data: bytes) -> int:
        if not self._connected:
            return 0

        self._in_buffer.extend(data)

        # Check if complete HDLC frames are enclosed
        while True:
            start_idx = self._in_buffer.find(0x7E)
            if start_idx == -1:
                self._in_buffer.clear()
                break
            if start_idx > 0:
                del self._in_buffer[:start_idx]

            end_idx = self._in_buffer.find(0x7E, 1)
            if end_idx == -1:
                # Raw CHECK_BAUD frame (consecutive 0x7E)
                if len(self._in_buffer) >= 1 and set(self._in_buffer) == {0x7E}:
                    replies = self.device.handle_raw_frame(bytes(self._in_buffer))
                    for r in replies:
                        self._incoming.append(r)
                    self._in_buffer.clear()
                break

            raw_frame = bytes(self._in_buffer[: end_idx + 1])
            del self._in_buffer[: end_idx + 1]

            replies = self.device.handle_raw_frame(raw_frame)
            for r in replies:
                self._incoming.append(r)

        return len(data)
