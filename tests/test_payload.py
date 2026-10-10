"""Payload parsing, field access and round-tripping."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cemacqr import QrSyntaxError, build, parse_payload
from cemacqr.payload import EmvQr
from cemacqr.tlv import Tlv

from .conftest import SPEC_PAYLOAD


class TestParsing:
    def test_whitespace_is_trimmed(self):
        assert parse_payload("  %s\n" % SPEC_PAYLOAD).raw == SPEC_PAYLOAD

    def test_an_empty_string_is_refused(self):
        with pytest.raises(QrSyntaxError):
            parse_payload("")

    def test_whitespace_only_is_refused(self):
        with pytest.raises(QrSyntaxError):
            parse_payload("   ")

    def test_a_non_string_is_refused(self):
        with pytest.raises(QrSyntaxError):
            parse_payload(b"000201")

    def test_a_malformed_payload_raises_rather_than_returning_nothing(self):
        with pytest.raises(QrSyntaxError):
            parse_payload("000201zz")


class TestAccess:
    def test_get_returns_none_for_an_absent_object(self):
        assert parse_payload(SPEC_PAYLOAD).get("99") is None

    def test_get_in_returns_none_for_an_absent_template(self):
        assert parse_payload(SPEC_PAYLOAD).get_in("62", "99") is None

    def test_get_in_is_context_sensitive(self):
        # ID "01" under the root is the Point of Initiation Method; ID "01" under
        # template 62 is a Bill Number. Anything resolving by ID alone confuses
        # these two, and the specification's own example contains both.
        qr = parse_payload(SPEC_PAYLOAD)
        assert qr.get("01") == "12"
        assert qr.get_in("62", "01") is None
        assert qr.get_in("64", "01") == "\u6700\u4f73\u8fd0\u8f93"

    def test_tags_are_in_order(self):
        assert parse_payload(SPEC_PAYLOAD).tags[:3] == ["00", "01", "29"]
        assert parse_payload(SPEC_PAYLOAD).tags[-1] == "63"

    def test_template_of_an_absent_parent_is_empty(self):
        assert parse_payload(SPEC_PAYLOAD).template("77") == {}


class TestChecksum:
    def test_stated_and_computed_agree_on_the_example(self):
        qr = parse_payload(SPEC_PAYLOAD)
        assert qr.stated_crc == qr.computed_crc == "A13A"

    def test_crc_ok_is_case_insensitive(self):
        qr = parse_payload(SPEC_PAYLOAD[:-4] + "a13a")
        assert qr.crc_ok is True

    def test_a_payload_without_a_crc_reports_false_not_an_exception(self):
        # Drop the whole trailing "63 04 XXXX" object.
        qr = parse_payload(SPEC_PAYLOAD[:-8])
        assert qr.stated_crc is None
        assert qr.computed_crc is None
        assert qr.crc_ok is False

    def test_with_crc_repairs_a_payload(self):
        broken = parse_payload(SPEC_PAYLOAD[:-4] + "0000")
        assert broken.crc_ok is False
        assert broken.with_crc() == SPEC_PAYLOAD

    def test_with_crc_is_idempotent(self):
        qr = parse_payload(SPEC_PAYLOAD)
        assert qr.with_crc() == qr.with_crc() == SPEC_PAYLOAD

    def test_without_crc_removes_the_object_entirely(self):
        stripped = parse_payload(SPEC_PAYLOAD).without_crc()
        assert stripped.endswith("12345678")
        assert "6304" not in stripped

    def test_to_string_is_the_input(self):
        assert parse_payload(SPEC_PAYLOAD).to_string() == SPEC_PAYLOAD
        assert str(parse_payload(SPEC_PAYLOAD)) == SPEC_PAYLOAD


class TestAmounts:
    @pytest.mark.parametrize("text,expected", [("98", "98"), ("98.", "98"), ("98.73", "98.73"), ("0.01", "0.01")])
    def test_the_forms_the_specification_permits(self, text, expected):
        qr = build([Tlv("00", "01"), Tlv("53", "950"), Tlv("54", text)])
        assert qr.amount == text
        assert qr.amount_decimal == Decimal(expected)

    def test_an_absent_amount_is_none(self):
        assert parse_payload(SPEC_PAYLOAD).get("54") is not None
        assert build([Tlv("00", "01"), Tlv("53", "950")]).amount is None

    def test_a_malformed_amount_yields_none_rather_than_raising(self):
        # Reading a damaged payload is a diagnostic activity; the accessor should
        # not be the thing that explodes. validate() is where it becomes an error.
        qr = build([Tlv("00", "01"), Tlv("53", "950"), Tlv("54", "98,73")])
        assert qr.amount_decimal is None


class TestPointOfInitiation:
    def test_eleven_is_static(self):
        assert build([Tlv("00", "01"), Tlv("01", "11")]).is_static is True

    def test_twelve_is_dynamic(self):
        assert build([Tlv("00", "01"), Tlv("01", "12")]).is_static is False

    def test_absent_is_unknown_not_static(self):
        # The object is optional. A reader that assumes a default here will treat
        # a single-use code as reusable, or the reverse.
        assert build([Tlv("00", "01")]).is_static is None

    def test_an_rfu_value_is_unknown(self):
        assert build([Tlv("00", "01"), Tlv("01", "99")]).is_static is None


class TestBuild:
    def test_build_appends_a_correct_checksum(self):
        qr = build([Tlv("00", "01"), Tlv("53", "950"), Tlv("58", "CM")])
        assert qr.crc_ok is True
        assert qr.get("63") == qr.computed_crc

    def test_build_discards_a_supplied_checksum(self):
        # The only correct checksum is the one computed over the finished payload.
        qr = build([Tlv("00", "01"), Tlv("53", "950"), Tlv("63", "0000")])
        assert qr.get("63") != "0000"
        assert qr.crc_ok is True

    def test_build_is_deterministic(self):
        objects = [Tlv("00", "01"), Tlv("53", "950"), Tlv("58", "CM"), Tlv("59", "A"), Tlv("60", "B")]
        assert build(objects).to_string() == build(objects).to_string()

    def test_repr_is_informative(self):
        text = repr(parse_payload(SPEC_PAYLOAD))
        assert "valid" in text
        assert "A13A" in text

    def test_repr_flags_a_bad_checksum(self):
        assert "MISMATCH" in repr(parse_payload(SPEC_PAYLOAD[:-4] + "0000"))

    def test_parse_is_available_as_a_classmethod(self):
        assert EmvQr.parse(SPEC_PAYLOAD).merchant_name == "BEST TRANSPORT"
