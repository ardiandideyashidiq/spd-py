"""Flasher operations: partition dump, flash, erase, patch, and device controls."""

from __future__ import annotations

import struct
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from ..core.channel import BslError, BslTimeoutError
from ..core.const import (
    DEFAULT_BLK_SIZE,
    BslCmd,
    BslRep,
)
from ..partitions.table import PartitionTable

if TYPE_CHECKING:
    from ..core.channel import SpdChannel


class FlasherError(Exception):
    """Raised when flash, dump, or partition operations fail."""


def build_partition_select_payload(name: str, size: int, mode64: bool = False) -> bytes:
    """Build binary partition selector payload (72B UTF-16LE name + 32/64-bit size)."""
    # 72 bytes name buffer in UTF-16LE
    name_encoded = name.encode("utf-16le")[:72]
    name_buf = bytearray(72)
    name_buf[: len(name_encoded)] = name_encoded

    size_lo = size & 0xFFFFFFFF
    if mode64:
        size_hi = (size >> 32) & 0xFFFFFFFF
        # 72 bytes name + 4B size_lo + 4B size_hi + 8B dummy = 88 bytes
        return bytes(name_buf) + struct.pack("<IIQ", size_lo, size_hi, 0)
    # 72 bytes name + 4B size_lo = 76 bytes
    return bytes(name_buf) + struct.pack("<I", size_lo)


def read_partition_table(channel: SpdChannel) -> PartitionTable:
    """Query and parse partition table from device."""
    logger.debug("Requesting device partition table (BSL_CMD_READ_PARTITION)...")
    rep, payload = channel.exec_cmd(BslCmd.READ_PARTITION, check_ack=False)
    if rep != BslRep.READ_PARTITION and rep != BslRep.ACK:
        raise FlasherError(f"Device rejected READ_PARTITION (response: 0x{rep:02X})")
    return PartitionTable.parse_bsl_binary(payload)


def dump_partition(
    channel: SpdChannel,
    name: str,
    output_path: str | Path,
    offset: int = 0,
    size: int | None = None,
    blk_size: int = DEFAULT_BLK_SIZE,
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    """Dump partition contents to a file."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # If size is not specified, resolve from partition table
    if size is None:
        ptable = read_partition_table(channel)
        part = ptable.get(name)
        if not part:
            raise FlasherError(f"Partition '{name}' not found in partition table")
        size = part.size

    mode64 = (offset + size) > 0xFFFFFFFF
    select_payload = build_partition_select_payload(name, offset + size, mode64=mode64)

    logger.info(
        f"Starting read of partition '{name}' ({size} bytes, offset: 0x{offset:X})..."
    )
    channel.exec_cmd(BslCmd.READ_START, select_payload)

    total_read = 0
    curr_offset = offset

    try:
        with out_file.open("wb") as f:
            while curr_offset < offset + size:
                remaining = (offset + size) - curr_offset
                chunk_len = min(remaining, blk_size)

                if mode64:
                    midst_payload = struct.pack(
                        "<III", chunk_len, curr_offset & 0xFFFFFFFF, curr_offset >> 32
                    )
                else:
                    midst_payload = struct.pack(
                        "<II", chunk_len, curr_offset & 0xFFFFFFFF
                    )

                rep, chunk = channel.exec_cmd(
                    BslCmd.READ_MIDST, midst_payload, check_ack=False
                )
                if rep not in (BslRep.ACK, BslRep.READ_FLASH):
                    raise FlasherError(
                        f"READ_MIDST failed at offset 0x{curr_offset:X} with response 0x{rep:02X}"
                    )

                if not chunk:
                    break

                f.write(chunk)
                n = len(chunk)
                total_read += n
                curr_offset += n

                if progress_callback:
                    progress_callback(total_read, size)
    finally:
        channel.exec_cmd(BslCmd.READ_END, check_ack=False)

    logger.info(
        f"Successfully dumped partition '{name}' to {out_file} ({total_read} bytes)"
    )
    return total_read


def dump_all(
    channel: SpdChannel,
    out_dir: str | Path,
    lite: bool = False,
    slot: str | None = None,
    blk_size: int = DEFAULT_BLK_SIZE,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> list[Path]:
    """Perform full firmware backup into target directory with JSON manifest."""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)

    ptable = read_partition_table(channel)
    parts_to_dump = ptable.filter_backup(lite=lite, slot=slot)

    # Save manifest first
    manifest_path = directory / "partitions.json"
    ptable.save_manifest(manifest_path)

    saved_files: list[Path] = []
    total_parts = len(parts_to_dump)

    for idx, part in enumerate(parts_to_dump, start=1):
        target_path = directory / f"{part.name}.bin"
        logger.info(f"[{idx}/{total_parts}] Dumping {part.name} ({part.size_human})...")

        p_name = part.name

        def cb(curr: int, tot: int, name: str = p_name) -> None:
            if progress_callback:
                progress_callback(name, curr, tot)

        dump_partition(
            channel,
            name=part.name,
            output_path=target_path,
            size=part.size,
            blk_size=blk_size,
            progress_callback=cb,
        )
        saved_files.append(target_path)

    logger.info(f"Completed backup of {len(saved_files)} partitions into {directory}")
    return saved_files


def flash_partition(
    channel: SpdChannel,
    name: str,
    input_source: str | Path | bytes,
    blk_size: int = DEFAULT_BLK_SIZE,
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    """Flash a binary image to the specified partition."""
    if isinstance(input_source, (str, Path)):
        src_path = Path(input_source)
        if not src_path.exists():
            raise FlasherError(f"Image file not found: {src_path}")
        data = src_path.read_bytes()
    else:
        data = input_source

    total_len = len(data)
    mode64 = total_len > 0xFFFFFFFF
    start_payload = build_partition_select_payload(name, total_len, mode64=mode64)

    logger.info(f"Flashing partition '{name}' ({total_len} bytes)...")
    channel.exec_cmd(BslCmd.START_DATA, start_payload)

    offset = 0
    try:
        while offset < total_len:
            chunk = data[offset : offset + blk_size]
            channel.exec_cmd(BslCmd.MIDST_DATA, chunk)
            offset += len(chunk)
            if progress_callback:
                progress_callback(offset, total_len)
    finally:
        channel.exec_cmd(BslCmd.END_DATA)

    logger.info(f"Successfully flashed partition '{name}' ({offset} bytes)")
    return offset


def flash_all(
    channel: SpdChannel,
    in_dir: str | Path,
    slot: str | None = None,
    blk_size: int = DEFAULT_BLK_SIZE,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> list[str]:
    """Flash multiple partitions from a directory containing images and manifest."""
    directory = Path(in_dir)
    manifest_path = directory / "partitions.json"
    if manifest_path.exists():
        ptable = PartitionTable.load_manifest(manifest_path)
    else:
        ptable = read_partition_table(channel)

    flashed: list[str] = []
    candidates = ptable.filter_slot(slot) if slot else ptable.partitions

    for part in candidates:
        img_candidates = [
            directory / f"{part.name}.bin",
            directory / f"{part.name}.img",
            directory / f"{part.name}",
        ]
        found = next((c for c in img_candidates if c.exists()), None)
        if not found:
            continue

        p_name = part.name

        def cb(curr: int, tot: int, name: str = p_name) -> None:
            if progress_callback:
                progress_callback(name, curr, tot)

        flash_partition(
            channel,
            name=part.name,
            input_source=found,
            blk_size=blk_size,
            progress_callback=cb,
        )
        flashed.append(part.name)

    logger.info(f"Batch flashing completed: flashed {len(flashed)} partitions")
    return flashed


def erase_partition(channel: SpdChannel, name: str, size: int = 0) -> None:
    """Erase target partition on flash storage."""
    logger.info(f"Erasing partition '{name}'...")
    payload = build_partition_select_payload(name, size)
    channel.exec_cmd(BslCmd.ERASE_FLASH, payload)
    logger.info(f"Partition '{name}' erased successfully")


def erase_all(channel: SpdChannel) -> None:
    """Erase entire device storage (Factory Wipe). Use with extreme caution."""
    logger.warning("Erasing entire flash storage...")
    channel.exec_cmd(BslCmd.ERASE_FLASH, b"")
    logger.info("Storage wipe completed")


def write_offset(
    channel: SpdChannel,
    name: str,
    offset: int,
    data: bytes,
) -> None:
    """Write arbitrary binary data at specific partition offset."""
    logger.info(
        f"Writing {len(data)} bytes to partition '{name}' at offset 0x{offset:X}..."
    )
    # BSL_CMD_WRITE_PARTITION_VALUE
    payload = struct.pack("<I", offset) + data
    channel.exec_cmd(BslCmd.WRITE_PARTITION_VALUE, payload)


def write_value(
    channel: SpdChannel,
    name: str,
    offset: int,
    value: int,
) -> None:
    """Write a 32-bit unsigned value to partition at offset."""
    val_bytes = struct.pack("<I", value & 0xFFFFFFFF)
    write_offset(channel, name, offset, val_bytes)


def reboot_device(channel: SpdChannel, mode: str = "normal") -> None:
    """Reboot or power off the connected device."""
    target_mode = mode.lower().strip()
    logger.info(f"Rebooting device (mode: {target_mode})...")

    if target_mode in ("poweroff", "shutdown"):
        channel.exec_cmd(BslCmd.POWER_OFF, check_ack=False)
    elif target_mode == "recovery":
        channel.exec_cmd(BslCmd.SET_FIRST_MODE, struct.pack(">I", 1), check_ack=False)
        channel.exec_cmd(BslCmd.NORMAL_RESET, check_ack=False)
    elif target_mode == "fastboot":
        channel.exec_cmd(BslCmd.SET_FIRST_MODE, struct.pack(">I", 2), check_ack=False)
        channel.exec_cmd(BslCmd.NORMAL_RESET, check_ack=False)
    else:
        channel.exec_cmd(BslCmd.NORMAL_RESET, check_ack=False)


def set_active_slot(channel: SpdChannel, slot: str) -> None:
    """Set active boot slot ('a' or 'b') for VAB/A-B devices."""
    slot_id = 0 if slot.lower() == "a" else 1
    logger.info(f"Setting active boot slot to '{slot.lower()}' (id {slot_id})...")
    channel.exec_cmd(BslCmd.SET_FIRST_MODE, struct.pack(">I", 0x10 + slot_id))


def set_dm_verity(channel: SpdChannel, enable: bool = False) -> None:
    """Disable or enable dm-verity on Android partitions."""
    action = "Enabling" if enable else "Disabling"
    logger.info(f"{action} dm-verity...")
    val = 1 if enable else 0
    channel.exec_cmd(BslCmd.DISABLE_SELINUX, struct.pack(">I", val), check_ack=False)


def read_chip_info(channel: SpdChannel) -> dict[str, str]:
    """Query chip UID, chip type, and storage info."""
    info: dict[str, str] = {}
    try:
        _, uid = channel.exec_cmd(BslCmd.READ_CHIP_UID)
        info["Chip UID"] = uid.hex().upper()
    except (BslError, BslTimeoutError, OSError):
        info["Chip UID"] = "Unknown"

    try:
        _, ctype = channel.exec_cmd(BslCmd.READ_CHIP_TYPE)
        if len(ctype) >= 4:
            val = struct.unpack(">I", ctype[:4])[0]
            info["Chip Type"] = f"0x{val:04X}"
    except (BslError, BslTimeoutError, OSError):
        info["Chip Type"] = "Unknown"

    return info
