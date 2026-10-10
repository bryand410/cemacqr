"""CRC-16 as required by EMV QRCPS — and not the CRC most people implement.

The specification is explicit:

    The checksum shall be calculated according to [ISO/IEC 13239] using the
    polynomial '1021' (hex) and initial value 'FFFF' (hex). The data over which
    the checksum is calculated shall cover all data objects, including their ID,
    Length and Value, to be included in the QR Code, in their respective order,
    as well as the ID and Length of the CRC itself (but excluding its Value).

    -- EMV QR Code Specification for Payment Systems, Merchant-Presented Mode,
       v1.1, section 4.7.3.1

Read those numbers again. Polynomial ``0x1021``, initial value ``0xFFFF``. That
is a **16-bit** CRC — the variant usually catalogued as CRC-16/CCITT-FALSE — and
it renders as exactly **four** hexadecimal characters.

It is not CRC-32, and the distinction is the single easiest way to build a QR
code that no reader in the region will accept. Several published descriptions of
the CEMAC common QR code announce a "CRC-32", almost certainly because CRC-32 is
the checksum a developer reaches for by default. CRC-32 over the same bytes
produces ``7F7AE5AA`` where the specification's own worked example requires
``A13A``: eight hex characters where four are permitted, and a value that is not
even a truncation of the correct one. You cannot detect the error by looking at
a QR code that renders — only by checking it.

The correct value, verified against the specification's Annex B.7 example, is
reproduced in the test suite as a golden vector.
"""

from __future__ import annotations

__all__ = ["CRC_INITIAL", "CRC_POLYNOMIAL", "crc16", "crc16_hex"]

#: Generator polynomial from EMV QRCPS v1.1 section 4.7.3.1.
CRC_POLYNOMIAL = 0x1021

#: Initial register value from EMV QRCPS v1.1 section 4.7.3.1.
CRC_INITIAL = 0xFFFF

#: Width, in hexadecimal characters, of the encoded checksum.
CRC_HEX_WIDTH = 4


def _build_table() -> tuple[int, ...]:
    """Precompute the 256-entry table for the polynomial.

    Doing this once at import keeps :func:`crc16` branch-light and makes the
    bit-level definition below the only thing a reader has to verify.
    """
    table = []
    for byte in range(256):
        register = byte << 8
        for _ in range(8):
            carry = register & 0x8000
            register = (register << 1) & 0xFFFF
            if carry:
                register ^= CRC_POLYNOMIAL
        table.append(register)
    return tuple(table)


_TABLE = _build_table()


def crc16(data: bytes) -> int:
    """Return the EMV QRCPS checksum of ``data`` as a 16-bit integer.

    ``data`` must be the UTF-8 encoding of the payload. The specification counts
    lengths in *characters* but the checksum is computed over the bytes actually
    transmitted, and for any payload containing a non-ASCII character those two
    are not the same number.

    >>> crc16(b"123456789")
    0x29B1
    """
    register = CRC_INITIAL
    for byte in data:
        register = ((register << 8) & 0xFFFF) ^ _TABLE[((register >> 8) ^ byte) & 0xFF]
    return register


def crc16_hex(data: bytes) -> str:
    """Return the checksum as the four uppercase hexadecimal characters EMVCo requires.

    EMV QRCPS v1.1 section 4.7.3.2: each nibble is converted to the corresponding
    character, and hex values ``A`` to ``F`` must be **uppercase**.

    >>> crc16_hex(b"123456789")
    '29B1'
    """
    return "%04X" % crc16(data)
