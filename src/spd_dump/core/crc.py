"""CRC16 and Checksum implementations matching spreadtrum_flash C routines."""

CHK_FIXZERO = 1
CHK_ORIG = 2

# Precomputed lookup table for CCITT CRC-16 (poly 0x1021)
_CRC16_TABLE = [
    ((i << 8) ^ (((i << 8) & 0x8000) and 0x1021)) & 0xFFFF for i in range(256)
]


def spd_crc16(crc: int, data: bytes | bytearray | memoryview) -> int:
    """Calculate 16-bit CCITT CRC matching spreadtrum_flash common.c:spd_crc16.

    Polynomial: 0x1021, big-endian bitwise evaluation.
    """
    crc &= 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x11021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def spd_checksum(
    crc: int, data: bytes | bytearray | memoryview, final: int = CHK_FIXZERO
) -> int:
    """Calculate 16-bit Internet-style checksum matching spreadtrum_flash common.c:spd_checksum.

    Sums 16-bit words (little-endian: byte1 << 8 | byte0), adds final odd byte if present,
    folds 32-bit sum to 16 bits, inverts (~crc & 0xffff), and applies fixzero byte-swap.
    """
    n = len(data)
    i = 0
    while n > 1:
        crc += (data[i + 1] << 8) | data[i]
        i += 2
        n -= 2

    if n == 1:
        crc += data[i]

    if final:
        crc = (crc >> 16) + (crc & 0xFFFF)
        crc += crc >> 16
        crc = (~crc) & 0xFFFF
        if n < final:
            # If remaining bytes < final (e.g. 0 < 1 for even length), byte-swap
            crc = ((crc >> 8) | ((crc & 0xFF) << 8)) & 0xFFFF

    return crc & 0xFFFF
