"""Core protocol definitions, CRC calculation, HDLC framing, and communication channel."""

from .channel import BslError, BslTimeoutError, SpdChannel
from .const import (
    BSL_ERROR_MESSAGES,
    DEFAULT_BLK_SIZE,
    DEFAULT_NAND_ID,
    DEFAULT_TIMEOUT,
    FLAGS_64BIT,
    FLAGS_CRC16,
    FLAGS_TRANSCODE,
    HDLC_ESCAPE,
    HDLC_HEADER,
    BslCmd,
    BslRep,
    BslStage,
    get_response_description,
)
from .crc import CHK_FIXZERO, CHK_ORIG, spd_checksum, spd_crc16
from .framing import (
    FramingError,
    StreamFrameDecoder,
    decode_frame,
    encode_frame,
    transcode,
    untranscode,
)

__all__ = [
    "BSL_ERROR_MESSAGES",
    "CHK_FIXZERO",
    "CHK_ORIG",
    "DEFAULT_BLK_SIZE",
    "DEFAULT_NAND_ID",
    "DEFAULT_TIMEOUT",
    "FLAGS_64BIT",
    "FLAGS_CRC16",
    "FLAGS_TRANSCODE",
    "HDLC_ESCAPE",
    "HDLC_HEADER",
    "BslCmd",
    "BslError",
    "BslRep",
    "BslStage",
    "BslTimeoutError",
    "FramingError",
    "SpdChannel",
    "StreamFrameDecoder",
    "decode_frame",
    "encode_frame",
    "get_response_description",
    "spd_checksum",
    "spd_crc16",
    "transcode",
    "untranscode",
]
