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
  - XML partition list parser and binary generator (`to_bsl_binary`, `from_xml`).
  - JSON manifest export and import (`partitions.json`) for automated backups and restoring.
- **`spd.partitions.nand`**:
  - NAND flash geometry calculations (`parse_nand_id`).
  - UBI image volume sizing (`parse_ubi_size`) matching Spreadtrum formula for block overhead reservation.

---

## 4. Boot & Flasher Engine (`spd.boot` & `spd.flasher`)

- **`BootEngine`**: Multi-stage bootstrapping:
  - BROM synchronization burst.
  - CVE-2022-38694 signature verification bypass via `exec_addr`.
  - Diagnostic mode kick (`kick()` and `build_diag_payload()`) using `AUTODLOADER` commands to switch device from AT/diag ports to download mode.
  - FDL1 / FDL2 staging and execution.
- **`flasher.operations`**:
  - `dump_partition` & `dump_all` (with lite backup excluding userdata/cache).
  - `flash_partition` & `flash_all` batch directory flashing.
  - `erase_partition` & `erase_all`.
  - `write_offset` (`wof`) and `write_value` (`wov`).
  - `repartition`: Synthesizes BSL binary table from XML and issues `BSL_CMD_REPARTITION`.
  - Direct physical I/O: `read_mem` (`BSL_CMD_READ_MIDST`), `read_flash` (`BSL_CMD_READ_FLASH`), `write_flash`, and `write_physical_word`.
  - Device controls (`reboot`, `slot`, `security`, `info`, `pactime`, `firstmode`).

---

## 5. Android Subsystems & Firmware Integration

- **Android Bootloader Control (BCB)**:
  - `build_bootloader_control`: Formats 32-byte `bootloader_control` struct with CRC32 checksum at offset `0x800` of partition `misc`.
  - Supports standard Android A/B slot switching (`a` or `b`).
  - Fastboot and recovery triggers written into `misc` control command blocks.
- **Android Verified Boot (AVB)**:
  - `set_dm_verity`: Locates `vbmeta`, `vbmeta_a`, `vbmeta_b`, and `vbmeta_bak` partitions and patches verification flag byte at offset `0x7B`.
- **NV Item Checksum Generation**:
  - `prepare_nv_image`: Recalculates CRC16 over NV items and embeds 32-bit additive checksum in fixed headers, ensuring modified NV / calibration partitions are accepted by bootloaders without radio calibration errors.
- **PAC Build Metadata**:
  - `read_pactime`: Extracts 64-bit Windows FILETIME from `miscdata:0x81400` and decodes it to ISO 8601 UTC datetime.
- **First Boot Mode**:
  - `set_first_mode`: Encodes `mode + 0x53464D00` ("SFM\0") and writes to `miscdata:0x2420` via `BSL_CMD_SET_FIRST_MODE`.

