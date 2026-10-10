"""TLV parsing: the format, its strictness, and the character/byte distinction."""

from __future__ import annotations

import pytest

from cemacqr import QrSyntaxError, Tlv, encode, parse_tlv
from cemacqr.tlv import encode_all, iter_parse


class TestParsing:
    def test_a_single_object(self):
        assert parse_tlv("000201") == [Tlv("00", "01")]

    def test_several_objects(self):
        assert parse_tlv("000201010212") == [Tlv("00", "01"), Tlv("01", "12")]

    def test_order_is_preserved(self):
        assert [item.tag for item in parse_tlv("5802CM5914BEST TRANSPORT")] == ["58", "59"]

    def test_a_nested_template_is_returned_whole(self):
        parsed = parse_tlv("62100101A0201B")
        assert len(parsed) == 1
        assert parsed[0].tag == "62"
        assert parsed[0].children() == [Tlv("01", "A"), Tlv("02", "B")]

    def test_empty_payload(self):
        assert parse_tlv("") == []

    def test_an_empty_value_is_legal(self):
        assert parse_tlv("6300") == [Tlv("63", "")]

    def test_a_length_without_its_value_is_not(self):
        with pytest.raises(QrSyntaxError):
            parse_tlv("6304")


class TestLengthsAreCharactersNotBytes:
    """EMV QRCPS counts characters. A byte-counting parser breaks on any
    payload carrying a merchant name outside the Latin alphabet — which, in
    CEMAC, is a routine case rather than an edge case."""

    def test_a_multibyte_value_is_read_by_character_count(self):
        # ID 59, length 04 characters, value is four CJK characters = 12 UTF-8 bytes.
        text = "5912\u6700\u4f73\u8fd0\u8f93"  # deliberately the *byte* count, which is wrong
        with pytest.raises(QrSyntaxError):
            parse_tlv(text)
        assert parse_tlv("5904\u6700\u4f73\u8fd0\u8f93") == [Tlv("59", "\u6700\u4f73\u8fd0\u8f93")]

    def test_the_specification_example_parses(self):
        body = (
            "00020101021229300012D156000000000510A93FO3230Q31280012D15600000001030812345678"
            "520441115802CN5914BEST TRANSPORT6007BEIJING64200002ZH0104\u6700\u4f73\u8fd0\u8f93"
            "0202\u5317\u4eac540523.7253031565502016233030412340603***0708A60086670902ME"
            "91320016A0112233449988770708123456786304A13A"
        )
        parsed = parse_tlv(body)
        assert len(parsed) == 15
        assert len(body) == 248
        assert len(body.encode("utf-8")) == 260


class TestStrictness:
    def test_a_truncated_value_raises_with_an_offset(self):
        with pytest.raises(QrSyntaxError) as caught:
            parse_tlv("5914BEST")
        assert caught.value.offset is not None
        assert "14" in str(caught.value)

    def test_a_non_numeric_tag_raises(self):
        with pytest.raises(QrSyntaxError):
            parse_tlv("5A0201")

    def test_a_non_numeric_length_raises(self):
        with pytest.raises(QrSyntaxError):
            parse_tlv("59XXBEST")

    def test_a_trailing_fragment_raises(self):
        with pytest.raises(QrSyntaxError):
            parse_tlv("0002010")

    def test_a_bare_two_character_string_raises(self):
        with pytest.raises(QrSyntaxError):
            parse_tlv("00")

    def test_nothing_is_silently_repaired(self):
        # A parser that skips what it cannot read turns a corrupt QR code into a
        # payment. Every malformed input must be an error, not a shorter list.
        for bad in ("0", "0002", "00ZZ", "0002010", "5914BES", "6", "6304X"):
            with pytest.raises(QrSyntaxError):
                parse_tlv(bad)


class TestEncoding:
    def test_encode_pads_the_length_to_two_digits(self):
        assert encode("59", "A") == "5901A"
        assert encode("59", "BEST TRANSPORT") == "5914BEST TRANSPORT"

    def test_round_trip(self):
        text = "0002015802CM5914BEST TRANSPORT6304A13A"
        assert encode_all(parse_tlv(text)) == text

    def test_round_trip_of_the_specification_example(self):
        body = (
            "00020101021229300012D156000000000510A93FO3230Q31280012D15600000001030812345678"
            "520441115802CN5914BEST TRANSPORT6007BEIJING64200002ZH0104\u6700\u4f73\u8fd0\u8f93"
            "0202\u5317\u4eac540523.7253031565502016233030412340603***0708A60086670902ME"
            "91320016A0112233449988770708123456786304A13A"
        )
        assert encode_all(parse_tlv(body)) == body

    def test_a_bad_tag_is_refused(self):
        for bad in ("5", "5AA", "abc"):
            with pytest.raises(ValueError):
                encode(bad, "x")

    def test_a_value_too_long_for_the_length_field_is_refused(self):
        with pytest.raises(ValueError):
            encode("59", "x" * 100)

    def test_ninety_nine_characters_is_accepted(self):
        assert encode("59", "x" * 99).startswith("5999")


class TestStreaming:
    def test_iter_parse_yields_lazily(self):
        stream = iter_parse("000201010212")
        assert next(stream) == Tlv("00", "01")
        assert next(stream) == Tlv("01", "12")

    def test_iter_parse_raises_on_consumption_not_construction(self):
        stream = iter_parse("00")
        with pytest.raises(QrSyntaxError):
            list(stream)


class TestTlvHelpers:
    def test_as_text(self):
        assert Tlv("59", "A").as_text() == "5901A"

    def test_children_of_a_non_template_is_empty_not_an_error(self):
        # A caller inspecting an unknown payload does not know in advance which
        # values are templates. "not TLV" is an answer.
        assert Tlv("59", "BEST TRANSPORT").children() == []

    def test_tlv_is_hashable(self):
        assert len({Tlv("00", "01"), Tlv("00", "01")}) == 1
