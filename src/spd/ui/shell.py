"""Interactive REPL shell powered by prompt_toolkit and Rich."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from ..flasher.operations import (
    FlasherError,
    dump_all,
    dump_partition,
    erase_all,
    erase_partition,
    flash_partition,
    read_chip_info,
    read_partition_table,
    reboot_device,
    set_active_slot,
    set_dm_verity,
    write_offset,
    write_value,
)
from .console import console
from .progress import TransferProgressBar
from .tables import render_device_info, render_partition_table

if TYPE_CHECKING:
    from ..core.channel import SpdChannel


SHELL_STYLE = Style.from_dict(
    {
        "prompt": "bold #00aa00",
        "stage": "#888888",
    }
)


class SpdInteractiveShell:
    """Interactive command-line environment for exploring and operating on connected devices."""

    COMMANDS: ClassVar[list[str]] = [
        "help",
        "info",
        "partitions",
        "dump",
        "flash",
        "erase",
        "patch",
        "slot",
        "verity",
        "reboot",
        "exit",
        "quit",
        # Legacy C command aliases
        "p",
        "r",
        "w",
        "e",
        "reset",
        "poweroff",
        "reboot-recovery",
        "reboot-fastboot",
    ]

    def __init__(self, channel: SpdChannel) -> None:
        self.channel = channel
        self.history = InMemoryHistory()
        self._cached_partitions: list[str] = []
        self._update_partition_names()

    def _update_partition_names(self) -> None:
        """Cache partition names for tab completion."""
        try:
            ptable = read_partition_table(self.channel)
            self._cached_partitions = [p.name for p in ptable.partitions]
        except (FlasherError, OSError):
            self._cached_partitions = []

    def run(self) -> None:
        """Run interactive REPL loop."""
        console.print("[bold cyan]Entered Unisoc Interactive Shell.[/bold cyan]")
        console.print(
            "Type [bold green]help[/bold green] for available commands, or [bold red]exit[/bold red] to quit.\n"
        )

        all_words = list(self.COMMANDS) + self._cached_partitions
        completer = WordCompleter(all_words, ignore_case=True)
        session = PromptSession(completer=completer, history=self.history)

        while True:
            try:
                stage_name = self.channel.stage.name
                prompt_text = [
                    ("class:prompt", "SPD "),
                    ("class:stage", f"({stage_name})> "),
                ]
                line = session.prompt(prompt_text, style=SHELL_STYLE).strip()
                if not line:
                    continue

                if not self._handle_command(line):
                    break
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Exiting interactive shell...[/dim]")
                break
            except (FlasherError, OSError, ValueError, KeyError) as e:
                console.print(f"[bold red]Error:[/bold red] {e}")

    def _handle_command(self, line: str) -> bool:
        """Parse and execute a single interactive command. Return False to exit."""
        args = shlex.split(line)
        if not args:
            return True

        cmd = args[0].lower()

        if cmd in ("exit", "quit", "q"):
            return False

        if cmd in ("help", "?"):
            self._print_help()
            return True

        if cmd in ("info", "chip"):
            info = read_chip_info(self.channel)
            render_device_info(info)
            return True

        if cmd in ("partitions", "p", "list", "part"):
            try:
                ptable = read_partition_table(self.channel)
                render_partition_table(ptable)
                self._update_partition_names()
            except (FlasherError, OSError) as e:
                console.print(
                    f"[bold red]Failed to read partition table:[/bold red] {e}"
                )
            return True

        if cmd in ("dump", "r", "read"):
            self._cmd_dump(args[1:])
            return True

        if cmd in ("flash", "w", "write"):
            self._cmd_flash(args[1:])
            return True

        if cmd in ("erase", "e"):
            self._cmd_erase(args[1:])
            return True

        if cmd in ("patch", "wof", "wov"):
            self._cmd_patch(args[1:])
            return True

        if cmd in ("slot", "set_active"):
            if len(args) < 2:
                console.print("[yellow]Usage: slot <a|b>[/yellow]")
            else:
                set_active_slot(self.channel, args[1])
                console.print(f"[green]Active slot set to {args[1]}[/green]")
            return True

        if cmd in ("verity",):
            enable = len(args) > 1 and args[1].lower() in ("1", "true", "enable")
            set_dm_verity(self.channel, enable=enable)
            console.print(
                f"[green]dm-verity {'enabled' if enable else 'disabled'}[/green]"
            )
            return True

        if cmd in ("reboot", "reset", "reboot-recovery", "reboot-fastboot", "poweroff"):
            mode = "normal"
            if cmd == "reboot-recovery" or (len(args) > 1 and args[1] == "recovery"):
                mode = "recovery"
            elif cmd == "reboot-fastboot" or (len(args) > 1 and args[1] == "fastboot"):
                mode = "fastboot"
            elif cmd in ("poweroff", "shutdown") or (
                len(args) > 1 and args[1] == "poweroff"
            ):
                mode = "poweroff"
            reboot_device(self.channel, mode=mode)
            console.print(
                f"[green]Device reboot command sent ({mode}). Exiting...[/green]"
            )
            return False

        console.print(
            f"[yellow]Unknown command '{cmd}'. Type 'help' for command list.[/yellow]"
        )
        return True

    def _cmd_dump(self, args: list[str]) -> None:
        """Handle dump / r command."""
        if not args:
            console.print(
                "[yellow]Usage: dump <partition_name|all|all-lite> [output_path][/yellow]"
            )
            return

        target = args[0].lower()
        if target in ("all", "all-lite", "all_lite"):
            out_dir = args[1] if len(args) > 1 else "backup"
            lite = target in ("all-lite", "all_lite")
            with TransferProgressBar("Dumping all partitions") as pb:
                saved = dump_all(
                    self.channel,
                    out_dir=out_dir,
                    lite=lite,
                    progress_callback=lambda part_name, curr, tot: (
                        pb.set_description(f"Dumping {part_name}"),
                        pb.update(curr, tot),
                    ),
                )
            console.print(
                f"[bold green]Dump complete:[/bold green] saved {len(saved)} partitions to {out_dir}/"
            )
            return

        part_name = args[0]
        out_file = args[1] if len(args) > 1 else f"{part_name}.bin"
        with TransferProgressBar(f"Dumping {part_name}") as pb:
            dump_partition(
                self.channel,
                name=part_name,
                output_path=out_file,
                progress_callback=pb.callback(),
            )
        console.print(f"[bold green]Dumped {part_name}[/bold green] -> {out_file}")

    def _cmd_flash(self, args: list[str]) -> None:
        """Handle flash / w command."""
        if len(args) < 2:
            console.print("[yellow]Usage: flash <partition_name> <image_file>[/yellow]")
            return
        part_name = args[0]
        img_path = Path(args[1])
        if not img_path.exists():
            console.print(f"[bold red]File not found:[/bold red] {img_path}")
            return
        with TransferProgressBar(f"Flashing {part_name}") as pb:
            flash_partition(
                self.channel,
                name=part_name,
                input_source=img_path,
                progress_callback=pb.callback(),
            )
        console.print(f"[bold green]Flashed {part_name}[/bold green] from {img_path}")

    def _cmd_erase(self, args: list[str]) -> None:
        """Handle erase / e command."""
        if not args:
            console.print("[yellow]Usage: erase <partition_name|all>[/yellow]")
            return
        if args[0].lower() == "all":
            if sys.stdin.isatty():
                ans = input("Are you sure you want to erase ALL storage? [y/N]: ")
                if ans.lower() != "y":
                    console.print("[dim]Cancelled.[/dim]")
                    return
            erase_all(self.channel)
            console.print("[bold green]Entire flash storage erased.[/bold green]")
        else:
            erase_partition(self.channel, args[0])
            console.print(f"[bold green]Partition '{args[0]}' erased.[/bold green]")

    def _cmd_patch(self, args: list[str]) -> None:
        """Handle patch command (wof / wov)."""
        if len(args) < 3:
            console.print(
                "[yellow]Usage: patch <partition> <offset> <value_hex|file_path>[/yellow]"
            )
            return
        part_name = args[0]
        offset = int(args[1], 0)
        target = args[2]

        if Path(target).exists():
            data = Path(target).read_bytes()
            write_offset(self.channel, part_name, offset, data)
            console.print(
                f"[green]Written {len(data)} bytes from {target} to {part_name}+0x{offset:X}[/green]"
            )
        else:
            val = int(target, 0)
            write_value(self.channel, part_name, offset, val)
            console.print(
                f"[green]Written 0x{val:08X} to {part_name}+0x{offset:X}[/green]"
            )

    def _print_help(self) -> None:
        """Print help summary."""
        console.print("\n[bold cyan]Available Commands:[/bold cyan]")
        console.print(
            "  [bold white]partitions[/bold white], [dim]p, list[/dim]         List on-flash partition table"
        )
        console.print(
            "  [bold white]dump[/bold white] <part|all> [path]        Dump partition or full backup (alias: r)"
        )
        console.print(
            "  [bold white]flash[/bold white] <part> <file>            Flash an image file to partition (alias: w)"
        )
        console.print(
            "  [bold white]erase[/bold white] <part|all>               Erase partition or wipe storage (alias: e)"
        )
        console.print(
            "  [bold white]patch[/bold white] <part> <off> <val|file>  Write value or file at offset (wof/wov)"
        )
        console.print(
            "  [bold white]slot[/bold white] <a|b>                     Switch active A/B slot"
        )
        console.print(
            "  [bold white]verity[/bold white] <0|1>                   Toggle dm-verity"
        )
        console.print(
            "  [bold white]info[/bold white]                          Display chip UID and hardware info"
        )
        console.print(
            "  [bold white]reboot[/bold white] [recovery|fastboot]      Reboot device (alias: reset)"
        )
        console.print(
            "  [bold white]exit[/bold white], [dim]quit[/dim]                    Exit shell\n"
        )
