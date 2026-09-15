"""NAND Flash and UBI calculation helpers (matching C common.c str_to_size_ubi)."""

from __future__ import annotations

import re


def parse_nand_id(nand_id: int) -> dict[str, int]:
    """Calculate NAND page, spare, and block geometry from nand_id (matching C spd_dump.c:807).

    - page_size = 2 ** (nand_id & 3) in KB
    - spare_size = 32 // (2 ** ((nand_id >> 2) & 3)) in bytes
    - block_size = 64 * (2 ** ((nand_id >> 4) & 3)) in KB
    """
    page_kb = 2 ** (nand_id & 3)
    spare_bytes = 32 // (2 ** ((nand_id >> 2) & 3))
    block_kb = 64 * (2 ** ((nand_id >> 4) & 3))

    return {
        "page_size_kb": page_kb,
        "page_size": page_kb * 1024,
        "spare_size": spare_bytes,
        "block_size_kb": block_kb,
        "block_size": block_kb * 1024,
    }


def parse_ubi_size(size_str: str, nand_info: dict[str, int] | None = None) -> int:
    """Parse size string with optional UBI overhead calculation (matching C str_to_size_ubi).

    Example strings:
    - 'ubi40m' -> calculates LEB (logical erase block) size excluding 2 pages of EC/VID headers
    - '40m', '1024k', '0x1000' -> standard sizes
    """
    s = size_str.strip().lower()

    if s.startswith("ubi"):
        # UBI size specified: e.g. ubi40m
        raw_size = parse_ubi_size(s[3:], nand_info=None)
        if not nand_info:
            nand_info = parse_nand_id(0x15)  # Default NAND ID in Unisoc BSL
        page_size = nand_info["page_size"]
        block_size = nand_info["block_size"]
        # In UBI, LEB size = block_size - 2 * page_size
        leb_size = block_size - (2 * page_size)
        if leb_size <= 0:
            return raw_size
        lebs = (raw_size + leb_size - 1) // leb_size
        return lebs * block_size

    # Standard size parsing
    match = re.match(r"^(\d+)([kmg]?)$", s)
    if match:
        val = int(match.group(1))
        unit = match.group(2)
        if unit == "k":
            return val * 1024
        elif unit == "m":
            return val * 1024 * 1024
        elif unit == "g":
            return val * 1024 * 1024 * 1024
        return val

    if s.startswith("0x"):
        return int(s, 16)

    return int(s)
