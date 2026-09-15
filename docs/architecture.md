# Architecture & Modularity Guide

`spd-py` is engineered around strict modularity, single-responsibility layers, and DRY principles so protocol logic is implemented once and shared across all backends.

```
                  +-----------------------------------+
                  |             Click CLI             |
                  |     (Subcommands & CLI Parser)    |
                  +-----------------+-----------------+
                                    |
                  +-----------------v-----------------+
                  |      Interactive REPL Shell       |
                  |    (prompt_toolkit + Rich UI)     |
                  +-----------------+-----------------+
                                    |
         +--------------------------+--------------------------+
         |                                                     |
+--------v--------+                                   +--------v--------+
|  BootEngine     |                                   | FlasherEngine   |
| (FDL1/2 Staging)|                                   | (Dump, Flash,   |
+--------+--------+                                   |  Erase, Patch)  |
         |                                            +--------+--------+
         |                                                     |
         +--------------------------+--------------------------+
                                    |
                  +-----------------v-----------------+
                  |            SpdChannel             |
                  | (Packet Framing, State, Timeouts) |
                  +-----------------+-----------------+
                                    |
                  +-----------------v-----------------+
                  |        Core Protocol Layer        |
                  |  - HDLC Framing (0x7E / 0x7D)     |
                  |  - CRC16 & Sum-Check Algorithms   |
                  |  - BslCmd / BslRep Enums          |
                  +-----------------+-----------------+
                                    |
                  +-----------------v-----------------+
                  |       BaseTransport Interface     |
                  +--+-----------+-----------+-----+--+
                     |           |           |     |
      +--------------+     +-----+----+      |     +-------------+
      |                    |          |      |                   |
+-----v-----+        +-----v----+   +-v------v--+          +-----v-----+
| Usb       |        | Serial   |   | Channel9  |          | Simulation|
| (PyUSB /  |        | (PySerial|   | (x86 DLL  |          | (Virtual  |
|  libusb)  |        |  COM/tty)|   |  Fallback)|          |  Hardware)|
+-----------+        +----------+   +-----------+          +-----------+
```

---

## 1. Core Protocol Layer (`spd.core`)

The protocol layer implements the Unisoc / Spreadtrum BSL frame standard:
- **`const.py`**: Clean, type-safe `IntEnum` classes (`BslCmd`, `BslRep`, `BslStage`) and human-readable error descriptions.
- **`crc.py`**:
  - `spd_crc16`: CCITT polynomial `0x1021`, bitwise MSB evaluation.
  - `spd_checksum`: Internet sum-check algorithm with 16-bit fold, inversion, and fixzero byte-swap.
- **`framing.py`**:
  - HDLC packet packaging delimited by `0x7E`.
  - Transcoding / escaping where `0x7E` -> `0x7D 0x5E` and `0x7D` -> `0x7D 0x5D`.
  - `StreamFrameDecoder`: Resilient streaming decoder handling fragmented USB/Serial reads and noisy initial bursts.
- **`channel.py`**:
  - `SpdChannel`: Wraps any transport, provides `send_msg`, `recv_msg`, `exec_cmd`, and filters asynchronous device logs (`BSL_REP_LOG`).

---

## 2. Pluggable Transport Layer (`spd.transports`)

All physical communication mechanisms inherit from `BaseTransport`:
- **`UsbTransport`**: Native bulk USB I/O using PyUSB. Automatically locates VID `0x1782` (Spreadtrum), claims endpoints, detaches Linux kernel drivers, and supports Android Termux `--usb-fd`.
- **`SerialTransport`**: Full COM and tty serial support with auto-detection of SPRD Virtual COM ports via `pyserial`. Supports dynamic baud rate switching.
- **`Channel9Transport`**: 32-bit Windows legacy driver integration. Interacts directly with SPRD official `Channel9.dll` on 32-bit Windows, with transparent fallback to `SerialTransport` on 64-bit systems.
- **`SimulationTransport`**: Full virtual in-memory mock Unisoc state machine. Accurately simulates BROM, FDL1, and FDL2 handshakes, partition table parsing, and synthetic flash storage.

---

## 3. Partition Management (`spd.partitions`)

- **`Partition`**: Dataclass model representing partition boundaries, size, slot detection (`_a`, `_b`), and user-data classification.
- **`PartitionTable`**:
  - Binary BSL partition table parser matching Unisoc `0x4C` entry structure with divisor detection.
  - XML partition list parser and generator.
  - JSON manifest export and import (`partitions.json`) for automated backups and restoring.

---

## 4. Boot & Flasher Engine (`spd.boot` & `spd.flasher`)

- **`BootEngine`**: Multi-stage bootstrapping:
  - BROM synchronization burst.
  - CVE-2022-38694 signature verification bypass via `exec_addr`.
  - FDL1 / FDL2 staging and execution.
- **`flasher.operations`**:
  - `dump_partition` & `dump_all` (with lite backup excluding userdata/cache).
  - `flash_partition` & `flash_all` batch directory flashing.
  - `erase_partition` & `erase_all`.
  - `write_offset` (`wof`) and `write_value` (`wov`).
  - Device controls (`reboot`, `slot`, `security`, `info`).
