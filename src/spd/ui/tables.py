"""Rich table formatters for partition tables, device info, and hex data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from .console import console

if TYPE_CHECKING:
    from ..partitions.table import PartitionTable


def render_partition_table(ptable: PartitionTable, title: str | None = None) -> None:
    """Render a styled Rich table displaying partition list."""
    display_title = title or f"Partition Table ({ptable.storage_type})"
    table = Table(
        title=f"[bold cyan]{display_title}[/bold cyan]",
        header_style="bold magenta",
        show_lines=False,
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Partition Name", style="bold white", width=28)
    table.add_column("Size", justify="right", style="cyan", width=14)
    table.add_column("Hex Size", justify="right", style="dim", width=12)
    table.add_column("Slot", justify="center", style="yellow", width=6)

    for idx, part in enumerate(ptable.partitions, start=1):
        slot = "-"
        if part.name.lower().endswith("_a"):
            slot = "A"
        elif part.name.lower().endswith("_b"):
            slot = "B"

        table.add_row(
            str(idx),
            part.name,
            part.size_human,
            f"0x{part.size:08X}",
            slot,
        )

    console.print(table)


def render_device_info(info: dict[str, str], title: str = "Device Information") -> None:
    """Render a styled Rich table for hardware device information."""
    table = Table(title=f"[bold cyan]{title}[/bold cyan]", header_style="bold magenta")
    table.add_column("Property", style="bold white", width=20)
    table.add_column("Value", style="cyan")

    for k, v in info.items():
        table.add_row(k, v)

    console.print(table)
