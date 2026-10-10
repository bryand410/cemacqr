"""The checksum, and the mistake this library exists to prevent.

The specification's own worked example (Annex B.7) is the authority here. If a
future version of EMVCo changes the polynomial, these tests fail — which is the
point.
"""

from __future__ import annotations

import zlib

import pytest

from cemacqr import crc16, crc16_hex
from cemacqr.crc import CRC_INITIAL, CRC_POLYNOMIAL

#: The payload from EMV QRCPS v1.1, Annex B.7, with its checksum removed.
SPEC_BODY = (
    "00020101021229300012D156000000000510A93FO3230Q31280012D15600000001030812345678"
    "520441115802CN5914BEST TRANSPORT6007BEIJING64200002ZH0104\u6700\u4f73\u8fd0\u8f93"
    "0202\u5317\u4eac540523.7253031565502016233030412340603***0708A60086670902ME"
    "91320016A0112233449988770708123456786304"
)

#: The checksum the specification prints for that payload.
SPEC_CRC = "A13A"


class TestDefinition:
    def test_polynomial_and_initial_value_are_the_specified_ones(self):
        assert CRC_POLYNOMIAL == 0x1021
        assert CRC_INITIAL == 0xFFFF

    def test_standard_check_value(self):
        # The check value every catalogue lists for CRC-16/CCITT-FALSE.
        assert crc16(b"123456789") == 0x29B1

    def test_empty_input_returns_the_initial_value(self):
        assert crc16(b"") == CRC_INITIAL

    def test_result_is_sixteen_bits(self):
        for candidate in (b"", b"\x00", b"a", b"\xff" * 64, SPEC_BODY.encode("utf-8")):
            assert 0 <= crc16(candidate) <= 0xFFFF


class TestAgainstTheSpecificationExample:
    def test_the_specification_checksum_is_reproduced(self):
        assert crc16_hex(SPEC_BODY.encode("utf-8")) == SPEC_CRC

    def test_it_is_four_characters(self):
        assert len(crc16_hex(SPEC_BODY.encode("utf-8"))) == 4

    def test_it_is_uppercase(self):
        computed = crc16_hex(SPEC_BODY.encode("utf-8"))
        assert computed == computed.upper()

    def test_a_single_flipped_character_changes_the_checksum(self):
        mutated = SPEC_BODY.replace("BEST TRANSPORT", "BEST TRANSPORU")
        assert crc16_hex(mutated.encode("utf-8")) != SPEC_CRC


class TestItIsNotCRC32:
    """The error that published descriptions of the CEMAC QR code invite.

    Several accounts of the CEMAC common QR code state that it is protected by a
    "CRC-32". EMV QRCPS v1.1 section 4.7.3.1 says otherwise, and these tests make
    the difference impossible to miss.
    """

    def test_crc32_gives_a_different_value(self):
        from_crc32 = "%08X" % (zlib.crc32(SPEC_BODY.encode("utf-8")) & 0xFFFFFFFF)
        assert from_crc32 == "7F7AE5AA"
        assert from_crc32 != SPEC_CRC

    def test_the_correct_value_is_not_a_truncation_of_crc32(self):
        from_crc32 = "%08X" % (zlib.crc32(SPEC_BODY.encode("utf-8")) & 0xFFFFFFFF)
        assert from_crc32[:4] != SPEC_CRC
        assert from_crc32[-4:] != SPEC_CRC

    def test_crc32_would_not_even_fit_the_field(self):
        # ID 63 is defined with a fixed length of four characters. CRC-32 needs
        # eight. A payload carrying one is not a payload with a wrong checksum,
        # it is a payload that cannot be parsed.
        assert len("%08X" % (zlib.crc32(b"x") & 0xFFFFFFFF)) == 8
        assert len(SPEC_CRC) == 4

    def test_other_common_variants_are_also_wrong(self):
        # CRC-16/XMODEM is the other polynomial-0x1021 variant, differing only in
        # the initial value. Choosing the wrong one is silent: both produce four
        # plausible-looking hexadecimal characters.
        def crc16_xmodem(data: bytes) -> int:
            register = 0x0000
            for byte in data:
                register ^= byte << 8
                for _ in range(8):
                    register = ((register << 1) ^ 0x1021) & 0xFFFF if register & 0x8000 else (register << 1) & 0xFFFF
            return register

        assert "%04X" % crc16_xmodem(SPEC_BODY.encode("utf-8")) != SPEC_CRC


class TestEncoding:
    @pytest.mark.parametrize(
        "data,expected",
        [
            (b"123456789", "29B1"),
            (b"", "FFFF"),
        ],
    )
    def test_hex_rendering(self, data, expected):
        assert crc16_hex(data) == expected

    def test_bytes_are_what_matters_not_characters(self):
        # The specification counts lengths in characters but the checksum covers
        # the transmitted bytes. For any non-ASCII merchant name the two differ.
        text = "\u4f73\u8fd0"
        assert len(text) == 2
        assert len(text.encode("utf-8")) == 6
        assert crc16_hex(text.encode("utf-8")) != crc16_hex(text.encode("latin-1", errors="replace"))
