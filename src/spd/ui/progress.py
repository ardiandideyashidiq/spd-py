"""Rich live transfer progress bar for flashing and dumping operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

if TYPE_CHECKING:
    from collections.abc import Callable

from .console import console


class TransferProgressBar:
    """Rich live progress manager for binary transfer operations."""

    def __init__(self, description: str = "Transferring", total_bytes: int = 0) -> None:
        self.description = description
        self.total_bytes = total_bytes
        self._progress: Progress | None = None
        self._task_id: TaskID | None = None

    def __enter__(self) -> Self:
        self._progress = Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=35),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
            console=console,
            transient=False,
        )
        self._progress.start()
        self._task_id = self._progress.add_task(
            self.description, total=self.total_bytes
        )
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None

    def update(self, current_bytes: int, total_bytes: int | None = None) -> None:
        """Update current transferred bytes and optional total."""
        if self._progress is not None and self._task_id is not None:
            if total_bytes is not None and total_bytes > 0:
                self._progress.update(
                    self._task_id, total=total_bytes, completed=current_bytes
                )
            else:
                self._progress.update(self._task_id, completed=current_bytes)

    def set_description(self, text: str) -> None:
        """Change task title."""
        if self._progress is not None and self._task_id is not None:
            self._progress.update(self._task_id, description=text)

    def callback(self) -> Callable[[int, int], None]:
        """Return a callback compatible with dump_partition / flash_partition."""

        def _cb(curr: int, tot: int) -> None:
            self.update(curr, tot)

        return _cb
