"""Partition data model and helper methods."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Partition:
    """Representation of an on-flash partition."""

    name: str
    size: int  # Size in bytes
    offset: int = 0
    part_id: int = 0
    flags: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def size_human(self) -> str:
        """Return human-readable size string (e.g., '64.00 MB', '256.00 KB')."""
        if self.size < 1024:
            return f"{self.size} B"
        if self.size < 1024 * 1024:
            return f"{self.size / 1024:.2f} KB"
        if self.size < 1024 * 1024 * 1024:
            return f"{self.size / (1024 * 1024):.2f} MB"
        return f"{self.size / (1024 * 1024 * 1024):.2f} GB"

    @property
    def is_userdata_or_cache(self) -> bool:
        """Return True if partition contains transient or private user data."""
        lower = self.name.lower()
        return lower in ("userdata", "data", "cache", "blackbox", "miscdata")

    def is_in_slot(self, slot: str) -> bool:
        """Check if partition belongs to slot ('a' or 'b') for VAB/A-B partitioned devices."""
        slot_suffix = f"_{slot.lower()}"
        if self.name.lower().endswith(slot_suffix):
            return True
        # If partition has no slot suffix (common partitions like splloader, persist), it belongs to both
        return not (
            self.name.lower().endswith("_a") or self.name.lower().endswith("_b")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "size": self.size,
            "size_human": self.size_human,
            "offset": self.offset,
            "part_id": self.part_id,
            "flags": self.flags,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Partition:
        return cls(
            name=data["name"],
            size=int(data["size"]),
            offset=int(data.get("offset", 0)),
            part_id=int(data.get("part_id", 0)),
            flags=int(data.get("flags", 0)),
            extra=data.get("extra", {}),
        )
