"""The specification's own example, end to end.

If the specification is reissued and any of these fail, the library is reading a
different document than the one it claims to implement — and that should be
loud, not silent.
"""

from __future__ import annotations

from decimal import Decimal

from cemacqr import crc16_hex, parse_payload, validate
from cemacqr.profile import EMVCO

from .conftest import SPEC_PAYLOAD


class TestStructure:
    def test_it_parses(self):
        qr = parse_payload(SPEC_PAYLOAD)
        assert len(qr.objects) == 15

    def test_the_checksum_matches(self):
        assert parse_payload(SPEC_PAYLOAD).crc_ok is True

    def test_it_round_trips_character_for_character(self):
        qr = parse_payload(SPEC_PAYLOAD)
        assert qr.without_crc() + "6304" + qr.computed_crc == SPEC_PAYLOAD

    def test_it_is_248_characters_and_260_bytes(self):
        # The distinction the parser has to get right: 248 characters, 260 bytes,
        # because six of them (最佳运输 and 北京) are three bytes each in UTF-8.
        assert len(SPEC_PAYLOAD) == 248
        assert len(SPEC_PAYLOAD.encode("utf-8")) == 260

    def test_the_checksum_covers_the_utf8_bytes(self):
        # Everything up to and including the "6304" that introduces the checksum:
        # 244 characters, 256 bytes.
        body = SPEC_PAYLOAD[:-4]
        assert len(body) == 244
        assert len(body.encode("utf-8")) == 256
        assert crc16_hex(body.encode("utf-8")) == "A13A"


class TestFields:
    def test_payload_format_indicator(self):
        assert parse_payload(SPEC_PAYLOAD).payload_format_indicator == "01"

    def test_point_of_initiation_is_dynamic(self):
        qr = parse_payload(SPEC_PAYLOAD)
        assert qr.point_of_initiation == "12"
        assert qr.is_static is False

    def test_merchant_category_code(self):
        assert parse_payload(SPEC_PAYLOAD).merchant_category_code == "4111"

    def test_currency_is_the_numeric_code(self):
        assert parse_payload(SPEC_PAYLOAD).currency == "156"

    def test_amount(self):
        qr = parse_payload(SPEC_PAYLOAD)
        assert qr.amount == "23.72"
        assert qr.amount_decimal == Decimal("23.72")

    def test_merchant_name(self):
        assert parse_payload(SPEC_PAYLOAD).merchant_name == "BEST TRANSPORT"

    def test_merchant_city(self):
        assert parse_payload(SPEC_PAYLOAD).merchant_city == "BEIJING"

    def test_country(self):
        assert parse_payload(SPEC_PAYLOAD).country_code == "CN"

    def test_tip_indicator(self):
        assert parse_payload(SPEC_PAYLOAD).tip_indicator == "01"


class TestTemplates:
    def test_two_merchant_accounts(self):
        assert sorted(parse_payload(SPEC_PAYLOAD).merchant_accounts) == ["29", "31"]

    def test_the_first_account_carries_its_gui(self):
        accounts = parse_payload(SPEC_PAYLOAD).merchant_accounts
        assert accounts["29"]["00"] == "D15600000000"
        assert accounts["29"]["05"] == "A93FO3230Q"

    def test_the_second_account(self):
        accounts = parse_payload(SPEC_PAYLOAD).merchant_accounts
        assert accounts["31"]["00"] == "D15600000001"
        assert accounts["31"]["03"] == "12345678"

    def test_the_language_template_is_decoded(self):
        assert parse_payload(SPEC_PAYLOAD).template("64") == {
            "00": "ZH",
            "01": "\u6700\u4f73\u8fd0\u8f93",
            "02": "\u5317\u4eac",
        }

    def test_the_additional_data_template_is_decoded(self):
        assert parse_payload(SPEC_PAYLOAD).template("62") == {
            "03": "1234",
            "06": "***",
            "07": "A6008667",
            "09": "ME",
        }

    def test_the_prompt_sentinel_is_recognised(self):
        from cemacqr import prompt_requested

        qr = parse_payload(SPEC_PAYLOAD)
        assert prompt_requested(qr, "06") is True
        assert prompt_requested(qr, "03") is False

    def test_the_unreserved_template_is_decoded(self):
        assert parse_payload(SPEC_PAYLOAD).template("91") == {
            "00": "A011223344998877",
            "07": "12345678",
        }


class TestValidation:
    def test_the_specification_example_is_valid(self):
        report = validate(parse_payload(SPEC_PAYLOAD), EMVCO)
        assert report.ok is True, str(report)
        assert report.violations == []

    def test_it_is_fully_checked_under_the_base_profile(self):
        # The EMVCo profile declares nothing as undefined, so a clean result
        # here is a complete result.
        assert validate(parse_payload(SPEC_PAYLOAD), EMVCO).fully_checked is True

    def test_a_corrupted_checksum_is_caught(self):
        report = validate(parse_payload(SPEC_PAYLOAD[:-4] + "0000"), EMVCO)
        assert report.ok is False
        assert [item.code for item in report.violations] == ["CRC_MISMATCH"]

    def test_the_mismatch_message_names_the_crc_trap(self):
        report = validate(parse_payload(SPEC_PAYLOAD[:-4] + "0000"), EMVCO)
        assert "not CRC-32" in str(report.violations[0])
