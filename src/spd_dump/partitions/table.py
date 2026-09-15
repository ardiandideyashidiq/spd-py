"""Partition table parsing, generation, and manifest operations."""

from __future__ import annotations

import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from loguru import logger

from .partition import Partition


class PartitionTableError(Exception):
    """Raised on invalid partition table data or parsing failures."""


class PartitionTable:
    """Manages collection of partitions on target device."""

    def __init__(
        self,
        partitions: list[Partition] | None = None,
        storage_type: str = "EMMC/UFS",
        sector_size: int = 512,
    ) -> None:
        self.partitions: list[Partition] = partitions or []
        self.storage_type = storage_type
        self.sector_size = sector_size

    def __len__(self) -> int:
        return len(self.partitions)

    def __iter__(self):
        return iter(self.partitions)

    def get(self, name: str) -> Partition | None:
        """Find partition by exact or case-insensitive name."""
        target = name.strip().lower()
        for part in self.partitions:
            if part.name.lower() == target:
                return part
        return None

    def filter_slot(self, slot: str) -> list[Partition]:
        """Return partitions belonging to the given slot ('a' or 'b')."""
        return [p for p in self.partitions if p.is_in_slot(slot)]

    def filter_backup(
        self, lite: bool = False, slot: str | None = None
    ) -> list[Partition]:
        """Return partitions for backup (all or all_lite excluding userdata/cache/inactive slot)."""
        parts = self.partitions
        if slot:
            parts = [p for p in parts if p.is_in_slot(slot)]
        if lite:
            parts = [p for p in parts if not p.is_userdata_or_cache]
        return parts

    @classmethod
    def parse_bsl_binary(cls, raw_data: bytes) -> PartitionTable:
        """Parse raw binary partition table returned by BSL_CMD_READ_PARTITION (0xBA).

        Structure matches Unisoc BSL standard:
        Repeated entries of 0x4C (76) bytes:
        - 0x00..0x48: UTF-16LE Partition Name (null terminated)
        - 0x48..0x4C: uint32 LE size
        Divisor auto-detection: checks bit shift for MB vs sector scaling.
        """
        if not raw_data or len(raw_data) % 0x4C != 0:
            raise PartitionTableError(
                f"Binary partition table data length ({len(raw_data)}) is not a multiple of 0x4C (76) bytes"
            )

        n_entries = len(raw_data) // 0x4C
        divisor = 10

        # Auto-detect divisor like common.c:1174-1180
        for i in range(n_entries):
            offset = i * 0x4C
            size_val = struct.unpack_from("<I", raw_data, offset + 0x48)[0]
            while divisor > 0 and not (size_val >> divisor):
                divisor -= 1

        storage_type = "EMMC" if divisor == 10 else "UFS"
        partitions: list[Partition] = []

        for i in range(n_entries):
            offset = i * 0x4C
            name_bytes = raw_data[offset : offset + 0x48]
            try:
                name_raw = name_bytes.decode("utf-16le", errors="ignore")
                name = name_raw.split("\x00")[0].strip()
            except Exception as e:
                raise PartitionTableError(
                    f"Failed to decode partition name at index {i}: {e}"
                ) from e

            if not name:
                continue

            size_val = struct.unpack_from("<I", raw_data, offset + 0x48)[0]
            # Convert size to bytes based on detected divisor
            size_bytes = int(size_val) << (20 - divisor)

            partitions.append(
                Partition(
                    name=name,
                    size=size_bytes,
                    part_id=i + 1,
                )
            )

        logger.debug(
            f"Parsed {len(partitions)} partitions from BSL binary table (storage: {storage_type})"
        )
        return cls(partitions=partitions, storage_type=storage_type)

    @classmethod
    def parse_xml(cls, xml_text: str) -> PartitionTable:
        """Parse Unisoc partition list XML (SC6531 / Android partition XMLs)."""
        partitions: list[Partition] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            raise PartitionTableError(f"XML parse error: {e}") from e

        part_id = 1
        for elem in root.iter("Partition"):
            name = (
                elem.attrib.get("id")
                or elem.attrib.get("name")
                or elem.attrib.get("id_name")
            )
            if not name:
                continue

            size_str = elem.attrib.get("size", "0")
            size_bytes = 0
            try:
                if size_str.lower().startswith("0x"):
                    size_bytes = int(size_str, 16)
                elif size_str.lower().endswith("m"):
                    size_bytes = int(size_str[:-1]) * 1024 * 1024
                elif size_str.lower().endswith("k"):
                    size_bytes = int(size_str[:-1]) * 1024
                else:
                    size_bytes = int(size_str)
                    # If size is small, it might be in MB (Unisoc legacy convention)
                    if size_bytes < 10000 and size_bytes > 0:
                        size_bytes *= 1024 * 1024
            except ValueError:
                pass

            partitions.append(Partition(name=name, size=size_bytes, part_id=part_id))
            part_id += 1

        return cls(partitions=partitions)

    def to_xml(self) -> str:
        """Export partitions as Unisoc XML partition list."""
        root = ET.Element("Partitions")
        for p in self.partitions:
            size_mb = max(1, p.size // (1024 * 1024))
            ET.SubElement(root, "Partition", {"id": p.name, "size": str(size_mb)})
        return ET.tostring(root, encoding="utf-8").decode("utf-8")

    def save_manifest(self, file_path: str | Path) -> None:
        """Save partition table as a JSON manifest file for backup / restore."""
        path = Path(file_path)
        data = {
            "storage_type": self.storage_type,
            "sector_size": self.sector_size,
            "partitions": [p.to_dict() for p in self.partitions],
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load_manifest(cls, file_path: str | Path) -> PartitionTable:
        """Load partition table from a JSON manifest file."""
        path = Path(file_path)
        if not path.exists():
            raise PartitionTableError(f"Manifest file not found: {path}")
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        parts = [Partition.from_dict(d) for d in data.get("partitions", [])]
        return cls(
            partitions=parts,
            storage_type=data.get("storage_type", "EMMC/UFS"),
            sector_size=data.get("sector_size", 512),
        )
