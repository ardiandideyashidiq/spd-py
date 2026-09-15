"""Click CLI subcommand interface for Unisoc BSL tool."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

import click

from .boot.engine import BootEngine, parse_address_from_filename
from .core.channel import BslError, BslTimeoutError, SpdChannel
from .core.const import DEFAULT_BAUDRATE, DEFAULT_BLK_SIZE, BslStage
from .flasher.operations import (
    FlasherError,
    dump_all,
    dump_partition,
    erase_all,
    erase_partition,
    flash_all,
    flash_partition,
    read_chip_info,
    read_flash,
    read_mem,
    read_pactime,
    read_partition_table,
    reboot_device,
    repartition,
    set_active_slot,
    set_dm_verity,
    set_first_mode,
    write_flash,
    write_offset,
    write_physical_word,
    write_value,
)
from .transports.base import BaseTransport
from .transports.factory import create_transport
from .ui.console import console, print_banner, setup_logging
from .ui.progress import TransferProgressBar
from .ui.shell import SpdInteractiveShell
from .ui.tables import render_device_info, render_partition_table


class ContextObject:
    """Shared CLI state object."""

    def __init__(self) -> None:
        self.port: str | None = None
        self.transport_type: str = "auto"
        self.baudrate: int = DEFAULT_BAUDRATE
        self.simulate: bool = False
        self.usb_fd: int | None = None
        self.timeout: float = 10.0
        self.verbose: int = 0
        self.fdl1: Path | None = None
        self.fdl1_addr: int | None = None
        self.fdl2: Path | None = None
        self.fdl2_addr: int | None = None
        self.exec_addr: int | None = None
        self.kick: bool = False
        self.kick_to: int = 0

    def get_transport(self) -> BaseTransport:
        """Create and connect transport based on context settings."""
        trans = create_transport(
            transport_type=self.transport_type,
            port=self.port,
            baudrate=self.baudrate,
            usb_fd=self.usb_fd,
            simulate=self.simulate,
            default_timeout=self.timeout,
        )
        trans.connect()
        return trans

    def get_channel(self, auto_boot: bool = False) -> tuple[BaseTransport, SpdChannel]:
        """Establish connected channel and optionally boot FDL1/FDL2."""
        trans = self.get_transport()
        channel = SpdChannel(trans, default_timeout=self.timeout)

        # In simulation mode, mock device starts in FDL2 if auto_boot or flasher command
        if self.simulate and auto_boot:
            channel.stage = BslStage.FDL2
            channel.use_crc16 = True
            if hasattr(trans, "device"):
                trans.device.stage = BslStage.FDL2
                trans.device.use_crc16 = True

        if auto_boot and self.kick:
            engine = BootEngine(channel)
            engine.kick(bootmode=self.kick_to)

        if auto_boot and self.fdl1:
            engine = BootEngine(channel)
            f1_addr = (
                self.fdl1_addr or parse_address_from_filename(self.fdl1) or 0x40004000
            )
            f2_addr = None
            if self.fdl2:
                f2_addr = (
                    self.fdl2_addr
                    or parse_address_from_filename(self.fdl2)
                    or 0x9F000000
                )

            with TransferProgressBar("Booting FDL Stages") as pb:
                engine.boot(
                    fdl1=self.fdl1,
                    fdl1_addr=f1_addr,
                    fdl2=self.fdl2,
                    fdl2_addr=f2_addr,
                    exec_addr=self.exec_addr,
                    kick=self.kick,
                    kick_mode=self.kick_to,
                    progress_cb=lambda stage, curr, tot: pb.update(curr, tot),
                )

        return trans, channel


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-p", "--port", help="Serial COM / tty port (e.g. COM3, /dev/ttyUSB0).")
@click.option(
    "-t",
    "--transport",
    type=click.Choice(
        ["auto", "usb", "serial", "channel9", "sim"], case_sensitive=False
    ),
    default="auto",
    help="Communication backend interface.",
)
@click.option(
    "-b", "--baud", default=DEFAULT_BAUDRATE, help="Baud rate for serial connections."
)
@click.option(
    "--sim",
    "--simulate",
    is_flag=True,
    help="Enable in-memory Unisoc hardware simulation.",
)
@click.option(
    "--usb-fd", type=int, help="Android Termux USB file descriptor passthrough."
)
@click.option("-w", "--wait", default=10.0, type=float, help="Timeout in seconds.")
@click.option(
    "-v", "--verbose", count=True, help="Increase logging verbosity (-v, -vv)."
)
@click.option(
    "--fdl1",
    type=click.Path(exists=True, path_type=Path),
    help="FDL1 / SPL bootloader image.",
)
@click.option("--fdl1-addr", type=str, help="FDL1 load address (hex).")
@click.option(
    "--fdl2",
    type=click.Path(exists=True, path_type=Path),
    help="FDL2 / U-Boot bootloader image.",
)
@click.option("--fdl2-addr", type=str, help="FDL2 load address (hex).")
@click.option("--exec-addr", type=str, help="CVE-2022-38694 signature bypass address.")
@click.option(
    "--kick",
    is_flag=True,
    help="Kick device from diagnostic/calibration mode into download mode.",
)
@click.option("--kick-to", default=0, type=int, help="Target boot mode ID for kick.")
@click.pass_context
def cli(
    ctx: click.Context,
    port: str | None,
    transport: str,
    baud: int,
    sim: bool,
    usb_fd: int | None,
    wait: float,
    verbose: int,
    fdl1: Path | None,
    fdl1_addr: str | None,
    fdl2: Path | None,
    fdl2_addr: str | None,
    exec_addr: str | None,
    kick: bool,
    kick_to: int,
) -> None:
    """⚡ Unisoc / Spreadtrum Firmware Tool (spd-py)."""
    obj = ContextObject()
    obj.port = port
    obj.transport_type = transport
    obj.baudrate = baud
    obj.simulate = sim
    obj.usb_fd = usb_fd
    obj.timeout = wait
    obj.verbose = verbose
    obj.fdl1 = fdl1
    obj.fdl1_addr = int(fdl1_addr, 0) if fdl1_addr else None
    obj.fdl2 = fdl2
    obj.fdl2_addr = int(fdl2_addr, 0) if fdl2_addr else None
    obj.exec_addr = int(exec_addr, 0) if exec_addr else None
    obj.kick = kick
    obj.kick_to = kick_to
    ctx.obj = obj
    setup_logging(verbose)


@cli.command("boot")
@click.option(
    "--fdl1",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to FDL1.",
)
@click.option("--fdl1-addr", type=str, help="Hex address for FDL1.")
@click.option(
    "--fdl2", type=click.Path(exists=True, path_type=Path), help="Path to FDL2."
)
@click.option("--fdl2-addr", type=str, help="Hex address for FDL2.")
@click.option("--exec-addr", type=str, help="CVE-2022-38694 bypass address.")
@click.option("--kick", is_flag=True, help="Kick device from diag mode before booting.")
@click.option("--kick-to", default=0, type=int, help="Target mode ID for kick.")
@click.pass_obj
def cmd_boot(
    obj: ContextObject,
    fdl1: Path,
    fdl1_addr: str | None,
    fdl2: Path | None,
    fdl2_addr: str | None,
    exec_addr: str | None,
    kick: bool,
    kick_to: int,
) -> None:
    """Execute BSL boot sequence (FDL1 & FDL2 upload)."""
    trans = obj.get_transport()
    channel = SpdChannel(trans, default_timeout=obj.timeout)
    engine = BootEngine(channel)

    f1_addr = (
        int(fdl1_addr, 0)
        if fdl1_addr
        else parse_address_from_filename(fdl1) or 0x40004000
    )
    f2_addr = (
        int(fdl2_addr, 0)
        if fdl2_addr
        else (parse_address_from_filename(fdl2) or 0x9F000000 if fdl2 else None)
    )
    ex_addr = int(exec_addr, 0) if exec_addr else obj.exec_addr

    with TransferProgressBar("Booting FDL Stages") as pb:
        engine.boot(
            fdl1=fdl1,
            fdl1_addr=f1_addr,
            fdl2=fdl2,
            fdl2_addr=f2_addr,
            exec_addr=ex_addr,
            kick=kick or obj.kick,
            kick_mode=kick_to or obj.kick_to,
            progress_cb=lambda stage, curr, tot: pb.update(curr, tot),
        )

    console.print(
        f"[bold green]Boot sequence successful![/bold green] Device at {channel.stage.name}"
    )
    trans.disconnect()


@cli.command("kick")
@click.option(
    "--mode", "-m", default=0, type=int, help="Target boot mode ID (default: 0)."
)
@click.option("--at", is_flag=True, help="Send AT modem command sequence.")
@click.pass_obj
def cmd_kick(obj: ContextObject, mode: int, at: bool) -> None:
    """Kick phone from diagnostic / calibration mode into download mode."""
    trans, channel = obj.get_channel(auto_boot=False)
    try:
        engine = BootEngine(channel)
        success = engine.kick(bootmode=mode, at=at, timeout=obj.timeout)
        if success:
            console.print(
                "[bold green]✔ Device successfully kicked into download mode[/bold green]"
            )
        else:
            console.print(
                "[bold yellow]⚠ Kick command sent; verify phone state[/bold yellow]"
            )
    finally:
        trans.disconnect()


@cli.command("info")
@click.pass_obj
def cmd_info(obj: ContextObject) -> None:
    """Query chip UID, chip type, and hardware status."""
    trans, channel = obj.get_channel(auto_boot=True)
    info = read_chip_info(channel)
    try:
        raw_pt, unix_pt = read_pactime(channel)
        if unix_pt:
            dt = datetime.datetime.fromtimestamp(unix_pt, tz=datetime.UTC)
            info["PAC Build Time"] = (
                f"{dt.strftime('%Y-%m-%d %H:%M:%S UTC')} (raw: 0x{raw_pt:X})"
            )
    except (BslError, BslTimeoutError, FlasherError, OSError):
        pass
    render_device_info(info)
    trans.disconnect()


@cli.command("pactime")
@click.pass_obj
def cmd_pactime(obj: ContextObject) -> None:
    """Read PAC build timestamp from miscdata partition."""
    trans, channel = obj.get_channel(auto_boot=True)
    try:
        raw_pt, unix_pt = read_pactime(channel)
        dt = datetime.datetime.fromtimestamp(unix_pt, tz=datetime.UTC)
        console.print(
            f"[bold cyan]PAC Timestamp:[/bold cyan] {dt.strftime('%Y-%m-%d %H:%M:%S UTC')} (raw: 0x{raw_pt:X}, unix: {unix_pt})"
        )
    finally:
        trans.disconnect()


@cli.command("firstmode")
@click.argument("mode_id", type=int)
@click.pass_obj
def cmd_firstmode(obj: ContextObject, mode_id: int) -> None:
    """Set first boot mode (writes mode + 0x53464D00 to miscdata:0x2420)."""
    trans, channel = obj.get_channel(auto_boot=True)
    try:
        set_first_mode(channel, mode_id)
        console.print(f"[bold green]✔ Firstmode set to {mode_id}[/bold green]")
    finally:
        trans.disconnect()


@cli.command("partitions")
@click.option(
    "--xml", type=click.Path(path_type=Path), help="Export partition list to XML file."
)
@click.option(
    "--json",
    "json_path",
    type=click.Path(path_type=Path),
    help="Export partition manifest to JSON.",
)
@click.option(
    "--repartition",
    "repart_xml",
    type=click.Path(exists=True, path_type=Path),
    help="Repartition device storage from XML partition table.",
)
@click.pass_obj
def cmd_partitions(
    obj: ContextObject,
    xml: Path | None,
    json_path: Path | None,
    repart_xml: Path | None,
) -> None:
    """Read, export, or repartition device storage."""
    trans, channel = obj.get_channel(auto_boot=True)

    if repart_xml:
        count = repartition(channel, repart_xml)
        console.print(
            f"[bold green]Device repartitioned with {count} partitions from {repart_xml}[/bold green]"
        )

    ptable = read_partition_table(channel)
    render_partition_table(ptable)

    if xml:
        xml.write_text(ptable.to_xml(), encoding="utf-8")
        console.print(f"[green]Exported partition XML to {xml}[/green]")

    if json_path:
        ptable.save_manifest(json_path)
        console.print(f"[green]Exported partition manifest to {json_path}[/green]")

    trans.disconnect()


@cli.command("dump")
@click.argument("target")
@click.argument("output", required=False)
@click.option(
    "--blk-size", default=DEFAULT_BLK_SIZE, help="Transfer block size in bytes."
)
@click.option("--lite", is_flag=True, help="Exclude userdata and cache in full backup.")
@click.option(
    "--slot",
    type=click.Choice(["a", "b"], case_sensitive=False),
    help="Filter partitions by slot.",
)
@click.pass_obj
def cmd_dump(
    obj: ContextObject,
    target: str,
    output: str | None,
    blk_size: int,
    lite: bool,
    slot: str | None,
) -> None:
    """Dump a single partition or full firmware backup (use 'all' or 'all-lite')."""
    trans, channel = obj.get_channel(auto_boot=True)

    if target.lower() in ("all", "all-lite", "all_lite"):
        out_dir = Path(output or "backup")
        is_lite = lite or target.lower() in ("all-lite", "all_lite")
        with TransferProgressBar("Dumping all partitions") as pb:
            saved = dump_all(
                channel,
                out_dir=out_dir,
                lite=is_lite,
                slot=slot,
                blk_size=blk_size,
                progress_callback=lambda part_name, curr, tot: (
                    pb.set_description(f"Dumping {part_name}"),
                    pb.update(curr, tot),
                ),
            )
        console.print(
            f"[bold green]Full backup complete:[/bold green] saved {len(saved)} partitions to {out_dir}/"
        )
    else:
        out_path = Path(output or f"{target}.bin")
        with TransferProgressBar(f"Dumping {target}") as pb:
            dump_partition(
                channel,
                name=target,
                output_path=out_path,
                blk_size=blk_size,
                progress_callback=pb.callback(),
            )
        console.print(
            f"[bold green]Successfully dumped {target}[/bold green] -> {out_path}"
        )

    trans.disconnect()


@cli.command("flash")
@click.argument("target")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--blk-size", default=DEFAULT_BLK_SIZE, help="Transfer block size in bytes."
)
@click.option(
    "--slot",
    type=click.Choice(["a", "b"], case_sensitive=False),
    help="Target A/B slot.",
)
@click.pass_obj
def cmd_flash(
    obj: ContextObject,
    target: str,
    source: Path,
    blk_size: int,
    slot: str | None,
) -> None:
    """Flash a partition image or batch flash from directory (use 'all' for directory)."""
    trans, channel = obj.get_channel(auto_boot=True)

    if target.lower() == "all" and source.is_dir():
        with TransferProgressBar("Batch Flashing") as pb:
            flashed = flash_all(
                channel,
                in_dir=source,
                slot=slot,
                blk_size=blk_size,
                progress_callback=lambda part_name, curr, tot: (
                    pb.set_description(f"Flashing {part_name}"),
                    pb.update(curr, tot),
                ),
            )
        console.print(
            f"[bold green]Batch flash complete:[/bold green] flashed {len(flashed)} partitions"
        )
    else:
        with TransferProgressBar(f"Flashing {target}") as pb:
            flash_partition(
                channel,
                name=target,
                input_source=source,
                blk_size=blk_size,
                progress_callback=pb.callback(),
            )
        console.print(
            f"[bold green]Successfully flashed {target}[/bold green] from {source}"
        )

    trans.disconnect()


@cli.command("erase")
@click.argument("target")
@click.option(
    "-y", "--yes", is_flag=True, help="Bypass confirmation prompt for wipe operations."
)
@click.pass_obj
def cmd_erase(obj: ContextObject, target: str, yes: bool) -> None:
    """Erase a partition or wipe all storage ('all')."""
    trans, channel = obj.get_channel(auto_boot=True)

    if target.lower() == "all":
        if not yes and sys.stdin.isatty():
            click.confirm(
                "Are you sure you want to completely erase ALL flash storage?",
                abort=True,
            )
        erase_all(channel)
        console.print(
            "[bold green]Entire flash storage wiped successfully.[/bold green]"
        )
    else:
        erase_partition(channel, target)
        console.print(f"[bold green]Partition '{target}' erased.[/bold green]")

    trans.disconnect()


@cli.command("patch")
@click.argument("partition")
@click.argument("offset")
@click.argument("target")
@click.pass_obj
def cmd_patch(obj: ContextObject, partition: str, offset: str, target: str) -> None:
    """Write arbitrary value or binary file to partition at specified offset."""
    trans, channel = obj.get_channel(auto_boot=True)
    off = int(offset, 0)

    if Path(target).exists():
        data = Path(target).read_bytes()
        write_offset(channel, partition, off, data)
        console.print(
            f"[bold green]Written {len(data)} bytes from {target} to {partition}+0x{off:X}[/bold green]"
        )
    else:
        val = int(target, 0)
        write_value(channel, partition, off, val)
        console.print(
            f"[bold green]Written 0x{val:08X} to {partition}+0x{off:X}[/bold green]"
        )

    trans.disconnect()


@cli.command("reboot")
@click.option(
    "-m",
    "--mode",
    type=click.Choice(
        ["normal", "recovery", "fastboot", "poweroff"], case_sensitive=False
    ),
    default="normal",
    help="Target reboot mode.",
)
@click.pass_obj
def cmd_reboot(obj: ContextObject, mode: str) -> None:
    """Reboot or power off the device."""
    trans, channel = obj.get_channel(auto_boot=True)
    reboot_device(channel, mode=mode)
    console.print(f"[bold green]Device reboot triggered ({mode}).[/bold green]")
    trans.disconnect()


@cli.command("slot")
@click.argument("target_slot", type=click.Choice(["a", "b"], case_sensitive=False))
@click.pass_obj
def cmd_slot(obj: ContextObject, target_slot: str) -> None:
    """Set active boot slot for A/B (VAB) partitioned devices."""
    trans, channel = obj.get_channel(auto_boot=True)
    set_active_slot(channel, target_slot)
    console.print(
        f"[bold green]Active boot slot switched to '{target_slot.lower()}'.[/bold green]"
    )
    trans.disconnect()


@cli.command("security")
@click.argument(
    "action", type=click.Choice(["enable", "disable"], case_sensitive=False)
)
@click.pass_obj
def cmd_security(obj: ContextObject, action: str) -> None:
    """Toggle Android dm-verity verification."""
    trans, channel = obj.get_channel(auto_boot=True)
    enable = action.lower() == "enable"
    set_dm_verity(channel, enable=enable)
    console.print(f"[bold green]dm-verity has been {action.lower()}d.[/bold green]")
    trans.disconnect()


@cli.command("shell")
@click.pass_obj
def cmd_shell(obj: ContextObject) -> None:
    """Start the interactive REPL shell."""
    print_banner()
    trans, channel = obj.get_channel(auto_boot=True)
    shell = SpdInteractiveShell(channel)
    try:
        shell.run()
    finally:
        trans.disconnect()


@cli.command("simulate")
@click.option(
    "--delay-ms",
    default=10.0,
    type=float,
    help="Synthetic simulated delay per frame in ms.",
)
@click.pass_obj
def cmd_simulate(obj: ContextObject, delay_ms: float) -> None:
    """Run simulated demo session to inspect flashing and commands without hardware."""
    print_banner()
    console.print("[bold cyan]Running Unisoc Simulated Hardware Session[/bold cyan]\n")
    trans = create_transport(simulate=True, sim_delay_ms=delay_ms)
    trans.connect()
    channel = SpdChannel(trans, default_timeout=5.0)
    channel.stage = BslStage.FDL2
    channel.use_crc16 = True
    if hasattr(trans, "device"):
        trans.device.stage = BslStage.FDL2
        trans.device.use_crc16 = True

    console.print("[green]1. Querying Device Info...[/green]")
    info = read_chip_info(channel)
    render_device_info(info)

    console.print("\n[green]2. Reading Partition Table...[/green]")
    ptable = read_partition_table(channel)
    render_partition_table(ptable)

    console.print(
        "\n[green]3. Demonstrating Simulated Partition Flash (boot)...[/green]"
    )
    dummy_data = b"SIMULATED_ANDROID_BOOT_IMAGE" * 256
    with TransferProgressBar("Simulated Flashing") as pb:
        flash_partition(channel, "boot", dummy_data, progress_callback=pb.callback())

    console.print(
        "\n[bold green]Simulation demonstration completed successfully![/bold green]"
    )
    trans.disconnect()


@cli.group("raw")
def raw_group() -> None:
    """Direct physical memory and flash I/O operations (no partition table required)."""


@raw_group.command("read-mem")
@click.argument("addr")
@click.argument("size")
@click.argument("output", type=click.Path(path_type=Path))
@click.option("--blk-size", default=1024, help="Block size in bytes.")
@click.pass_obj
def cmd_raw_read_mem(
    obj: ContextObject, addr: str, size: str, output: Path, blk_size: int
) -> None:
    """Read physical RAM/memory from specified address to file (matches C dump_mem)."""
    trans, channel = obj.get_channel(auto_boot=True)
    a = int(addr, 0)
    s = int(size, 0)
    with TransferProgressBar(f"Reading Memory 0x{a:X}") as pb:
        read_mem(
            channel,
            a,
            s,
            output,
            blk_size=blk_size,
            progress_callback=pb.callback(),
        )
    console.print(f"[bold green]Saved memory dump to {output}[/bold green]")
    trans.disconnect()


@raw_group.command("read-flash")
@click.argument("addr")
@click.argument("offset")
@click.argument("size")
@click.argument("output", type=click.Path(path_type=Path))
@click.option("--blk-size", default=1024, help="Block size in bytes.")
@click.pass_obj
def cmd_raw_read_flash(
    obj: ContextObject,
    addr: str,
    offset: str,
    size: str,
    output: Path,
    blk_size: int,
) -> None:
    """Read raw flash from specified address + offset to file (matches C dump_flash)."""
    trans, channel = obj.get_channel(auto_boot=True)
    a = int(addr, 0)
    off = int(offset, 0)
    s = int(size, 0)
    with TransferProgressBar(f"Reading Flash 0x{a:X}") as pb:
        read_flash(
            channel,
            a,
            off,
            s,
            output,
            blk_size=blk_size,
            progress_callback=pb.callback(),
        )
    console.print(f"[bold green]Saved flash dump to {output}[/bold green]")
    trans.disconnect()


@raw_group.command("write-flash")
@click.argument("addr")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option("--blk-size", default=DEFAULT_BLK_SIZE, help="Block size in bytes.")
@click.pass_obj
def cmd_raw_write_flash(
    obj: ContextObject, addr: str, source: Path, blk_size: int
) -> None:
    """Write binary image directly to target physical memory/flash address."""
    trans, channel = obj.get_channel(auto_boot=True)
    a = int(addr, 0)
    with TransferProgressBar(f"Writing Flash 0x{a:X}") as pb:
        write_flash(
            channel,
            a,
            source,
            blk_size=blk_size,
            progress_callback=pb.callback(),
        )
    console.print(f"[bold green]Successfully wrote {source} to 0x{a:X}[/bold green]")
    trans.disconnect()


@raw_group.command("write-word")
@click.argument("addr")
@click.argument("value")
@click.pass_obj
def cmd_raw_write_word(obj: ContextObject, addr: str, value: str) -> None:
    """Write a 32-bit word directly to physical memory address (matches C write_word)."""
    trans, channel = obj.get_channel(auto_boot=True)
    a = int(addr, 0)
    v = int(value, 0)
    write_physical_word(channel, a, v)
    console.print(f"[bold green]Written 0x{v:08X} to 0x{a:08X}[/bold green]")
    trans.disconnect()
