"""Rich console configuration, styling, and Loguru logging bridge."""

from __future__ import annotations

import sys

from loguru import logger
from rich.console import Console
from rich.theme import Theme

SPD_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "header": "bold magenta",
        "dim": "dim",
        "accent": "bold cyan",
        "partition": "bold white on blue",
    }
)

console = Console(theme=SPD_THEME)


class RichLoguruHandler:
    """Loguru logging handler that formats logs cleanly through Rich console."""

    def write(self, message: str) -> None:
        text = message.strip()
        if text:
            console.print(f"[dim]{text}[/dim]")


def setup_logging(verbose: int = 0) -> None:
    """Configure log level according to verbosity flag (-v, -vv)."""
    logger.remove()

    if verbose == 0:
        level = "INFO"
    elif verbose == 1:
        level = "DEBUG"
    else:
        level = "TRACE"

    fmt = "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    logger.add(sys.stderr, level=level, format=fmt, colorize=True)


def print_banner() -> None:
    """Print stylish banner for Unisoc Flash Tool."""
    console.print(
        "[bold cyan]⚡ Unisoc / Spreadtrum Flash Tool (spd-py)[/bold cyan] [dim]v0.1.0[/dim]",
        style="header",
    )
    console.print("[dim]Next-generation BSL protocol firmware utility[/dim]\n")
