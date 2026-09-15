"""Constants, command codes, response codes, and protocol enums for Unisoc BSL."""

from enum import IntEnum, unique

HDLC_HEADER = 0x7E
HDLC_ESCAPE = 0x7D
HDLC_ESCAPE_MASK = 0x20

# Protocol feature flags (matching common.h)
FLAGS_CRC16 = 1 << 0
FLAGS_TRANSCODE = 1 << 1
FLAGS_64BIT = 1 << 2

# Operational defaults
DEFAULT_NAND_ID = 0x15
DEFAULT_BLK_SIZE = 0x1000  # 4096 bytes
MAX_BLK_SIZE = 65535
DEFAULT_TIMEOUT = 10.0  # seconds
DEFAULT_BAUDRATE = 115200

# USB identifiers
SPRD_VID = 0x1782
SPRD_PIDS = (0x4D00, 0x5D00, 0x0001, 0x0002, 0x0003)


class BslStage(IntEnum):
    """Execution stages of Unisoc BSL."""
    DISCONNECTED = 0
    BROM = 1
    FDL1 = 2
    FDL2 = 3


@unique
class BslCmd(IntEnum):
    """Unisoc BSL protocol request command IDs."""
    CONNECT = 0x00
    START_DATA = 0x01
    MIDST_DATA = 0x02
    END_DATA = 0x03
    EXEC_DATA = 0x04
    NORMAL_RESET = 0x05
    READ_FLASH = 0x06
    READ_CHIP_TYPE = 0x07
    READ_NVITEM = 0x08
    CHANGE_BAUD = 0x09
    ERASE_FLASH = 0x0A
    REPARTITION = 0x0B
    READ_FLASH_TYPE = 0x0C
    READ_FLASH_INFO = 0x0D
    READ_SECTOR_SIZE = 0x0F
    READ_START = 0x10
    READ_MIDST = 0x11
    READ_END = 0x12
    KEEP_CHARGE = 0x13
    EXTTABLE = 0x14
    READ_FLASH_UID = 0x15
    READ_SOFTSIM_EID = 0x16
    POWER_OFF = 0x17
    CHECK_ROOT = 0x19
    READ_CHIP_UID = 0x1A
    ENABLE_WRITE_FLASH = 0x1B
    ENABLE_SECUREBOOT = 0x1C
    IDENTIFY_START = 0x1D
    IDENTIFY_END = 0x1E
    READ_CU_REF = 0x1F
    READ_REFINFO = 0x20
    DISABLE_TRANSCODE = 0x21
    WRITE_APR_INFO = 0x22
    CUST_DUMMY = 0x23
    READ_RF_TRANSCEIVER_TYPE = 0x24
    ENABLE_DEBUG_MODE = 0x25
    DDR_CHECK = 0x26
    SELF_REFRESH = 0x27
    ENABLE_RAW_DATA = 0x28
    READ_NAND_BLOCK_INFO = 0x29
    SET_FIRST_MODE = 0x2A
    SET_RANDOM_DATA = 0x2B
    SET_TIME_STAMP = 0x2C
    READ_PARTITION = 0x2D
    READ_VCUR_DATA = 0x2E
    WRITE_VPAC_DATA = 0x2F
    MIDST_RAW_START = 0x31
    FLUSH_DATA = 0x32
    MIDST_RAW_START2 = 0x33
    ENABLE_UBOOT_LOG = 0x34
    DUMP_UBOOT_LOG = 0x35
    DISABLE_SELINUX = 0x40
    AUTH_BEGIN = 0x41
    AUTH_END = 0x42
    EMMC_CID = 0x43
    OPEN_WATCH_DOG = 0x44
    CLOSE_WATCH_DOG = 0x45
    POWEROFF_NOKEY = 0x46
    WRITE_EFUSE = 0x47
    READ_PARTITION_VALUE = 0x48
    WRITE_PARTITION_VALUE = 0x49
    WRITE_DOWNLOAD_TIMESTAMP = 0x50
    PARTITION_SIGNATURE = 0x51
    CHECK_BAUD = 0x7E
    END_PROCESS = 0x7F
    SEND_FLAG = 0xCC


@unique
class BslRep(IntEnum):
    """Unisoc BSL protocol response status codes."""
    ACK = 0x80
    VER = 0x81
    INVALID_CMD = 0x82
    UNKNOW_CMD = 0x83
    OPERATION_FAILED = 0x84
    NOT_SUPPORT_BAUDRATE = 0x85
    DOWN_NOT_START = 0x86
    DOWN_MULTI_START = 0x87
    DOWN_EARLY_END = 0x88
    DOWN_DEST_ERROR = 0x89
    DOWN_SIZE_ERROR = 0x8A
    VERIFY_ERROR = 0x8B
    NOT_VERIFY = 0x8C
    PHONE_NOT_ENOUGH_MEMORY = 0x8D
    PHONE_WAIT_INPUT_TIMEOUT = 0x8E
    PHONE_SUCCEED = 0x8F
    PHONE_VALID_BAUDRATE = 0x90
    PHONE_REPEAT_CONTINUE = 0x91
    PHONE_REPEAT_BREAK = 0x92
    READ_FLASH = 0x93
    READ_CHIP_TYPE = 0x94
    READ_NVITEM = 0x95
    INCOMPATIBLE_PARTITION = 0x96
    UNKNOWN_DEVICE = 0x97
    INVALID_DEVICE_SIZE = 0x98
    ILLEGAL_SDRAM = 0x99
    WRONG_SDRAM_PARAMETER = 0x9A
    READ_FLASH_INFO = 0x9B
    READ_SECTOR_SIZE = 0x9C
    READ_FLASH_TYPE = 0x9D
    READ_FLASH_UID = 0x9E
    READ_SOFTSIM_EID = 0x9F
    ERROR_CHECKSUM = 0xA0
    CHECKSUM_DIFF = 0xA1
    WRITE_ERROR = 0xA2
    CHIPID_NOT_MATCH = 0xA3
    FLASH_CFG_ERROR = 0xA4
    DOWN_STL_SIZE_ERROR = 0xA5
    PHONE_IS_ROOTED = 0xA7
    SEC_VERIFY_ERROR = 0xAA
    READ_CHIP_UID = 0xAB
    NOT_ENABLE_WRITE_FLASH = 0xAC
    ENABLE_SECUREBOOT_ERROR = 0xAD
    IDENTIFY_START = 0xAE
    IDENTIFY_END = 0xAF
    READ_CU_REF = 0xB0
    READ_REFINFO = 0xB1
    CUST_DUMMY = 0xB2
    FLASH_WRITTEN_PROTECTION = 0xB3
    FLASH_INITIALIZING_FAIL = 0xB4
    RF_TRANSCEIVER_TYPE = 0xB5
    DDR_CHECK_ERROR = 0xB6
    SELF_REFRESH_ERROR = 0xB7
    READ_NAND_BLOCK_INFO = 0xB8
    RANDOM_DATA_ERROR = 0xB9
    READ_PARTITION = 0xBA
    DUMP_UBOOT_LOG = 0xBB
    READ_VCUR_DATA = 0xBC
    AUTH_M1_DATA = 0xBD
    READ_PARTITION_VALUE = 0xBE
    UNSUPPORT_PARTITION = 0xBF
    EMMC_CID_DATA = 0xC0
    MAGIC_ERROR = 0xD0
    REPARTITION_ERROR = 0xD1
    READ_FLASH_ERROR = 0xD2
    MALLOC_ERROR = 0xD3
    UNSUPPORTED_COMMAND = 0xFE
    LOG = 0xFF


BSL_ERROR_MESSAGES: dict[int, str] = {
    BslRep.INVALID_CMD: "Invalid command rejected by device",
    BslRep.UNKNOW_CMD: "Unknown command not recognized by device",
    BslRep.OPERATION_FAILED: "Operation failed",
    BslRep.NOT_SUPPORT_BAUDRATE: "Baud rate not supported",
    BslRep.DOWN_NOT_START: "Data download has not been initialized",
    BslRep.DOWN_MULTI_START: "Data download already started",
    BslRep.DOWN_EARLY_END: "Data download ended unexpectedly early",
    BslRep.DOWN_DEST_ERROR: "Destination address invalid",
    BslRep.DOWN_SIZE_ERROR: "Download size error",
    BslRep.VERIFY_ERROR: "Signature/data verification error",
    BslRep.NOT_VERIFY: "Not verified",
    BslRep.PHONE_NOT_ENOUGH_MEMORY: "Device out of memory",
    BslRep.PHONE_WAIT_INPUT_TIMEOUT: "Device timed out waiting for input",
    BslRep.INCOMPATIBLE_PARTITION: "Incompatible partition layout",
    BslRep.UNKNOWN_DEVICE: "Unknown flash storage device",
    BslRep.INVALID_DEVICE_SIZE: "Invalid device storage size",
    BslRep.ILLEGAL_SDRAM: "Illegal SDRAM configuration",
    BslRep.WRONG_SDRAM_PARAMETER: "Wrong SDRAM parameters",
    BslRep.ERROR_CHECKSUM: "Checksum error in transmitted packet",
    BslRep.CHECKSUM_DIFF: "Checksum difference detected",
    BslRep.WRITE_ERROR: "Flash write error",
    BslRep.CHIPID_NOT_MATCH: "Chip ID does not match target",
    BslRep.FLASH_CFG_ERROR: "Flash configuration error",
    BslRep.PHONE_IS_ROOTED: "Device root status detected",
    BslRep.SEC_VERIFY_ERROR: "Security verification failed",
    BslRep.NOT_ENABLE_WRITE_FLASH: "Flash write protection enabled",
    BslRep.FLASH_WRITTEN_PROTECTION: "Flash write protection active",
    BslRep.FLASH_INITIALIZING_FAIL: "Flash initialization failed",
    BslRep.UNSUPPORT_PARTITION: "Partition operation unsupported",
    BslRep.MAGIC_ERROR: "Protocol magic mismatch",
    BslRep.REPARTITION_ERROR: "Repartitioning failed",
    BslRep.READ_FLASH_ERROR: "Flash read error",
    BslRep.MALLOC_ERROR: "Device memory allocation error",
    BslRep.UNSUPPORTED_COMMAND: "Command unsupported on this boot stage",
}


def get_response_description(rep_code: int) -> str:
    """Return a friendly description for a BSL response code."""
    try:
        rep = BslRep(rep_code)
        if rep == BslRep.ACK:
            return "OK (ACK)"
        if rep in BSL_ERROR_MESSAGES:
            return f"{rep.name}: {BSL_ERROR_MESSAGES[rep]}"
        return f"{rep.name} (0x{rep_code:02X})"
    except ValueError:
        return f"UNKNOWN_RESPONSE_CODE (0x{rep_code:02X})"
