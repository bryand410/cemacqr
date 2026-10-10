"""The validation rules, one class per rule family."""

from __future__ import annotations

import pytest

from cemacqr import CEMAC, EMVCO, QrValidationError, build, parse_payload, validate
from cemacqr.errors import ProfileIncomplete
from cemacqr.profile import get_profile
from cemacqr.tlv import Tlv

from .conftest import SPEC_PAYLOAD


def minimal(**overrides):
    """A smallest-possible valid payload, with selected objects replaced.

    Keys map to data object IDs; a value of ``None`` omits the object.
    """
    objects = {
        "00": "01",
        "26": "0017com.example.cemac",
        "52": "5411",
        "53": "950",
        "58": "CM",
        "59": "MERCHANT",
        "60": "DOUALA",
        # Template 62 carrying the CEMAC payment system data object (ID 50).
        # Since the CORENOFI norm makes 6250 mandatory, a CEMAC payload without
        # it is not a CEMAC payload.
        "62": "50070303T01",
    }
    objects.update(overrides)
    return build([Tlv(tag, value) for tag, value in objects.items() if value is not None])


class TestBaseline:
    def test_a_minimal_payload_is_valid(self):
        report = validate(minimal(), EMVCO)
        assert report.ok is True, str(report)

    def test_status_reads_clearly(self):
        assert validate(minimal(), EMVCO).status == "VALID"

    def test_an_empty_payload_is_reported_not_crashed(self):
        from cemacqr.payload import EmvQr

        report = validate(EmvQr(raw="", objects=[]), EMVCO)
        assert report.ok is False
        assert [item.code for item in report.violations] == ["EMPTY"]


class TestChecksum:
    def test_a_mismatch_is_reported(self):
        report = validate(parse_payload(SPEC_PAYLOAD[:-4] + "1234"), EMVCO)
        assert "CRC_MISMATCH" in [item.code for item in report.violations]

    def test_a_short_crc_is_reported(self):
        # Built by hand: "63 02 00" is a CRC object whose value is two characters
        # instead of four. build() would never produce this.
        report = validate(parse_payload("000201630200"), EMVCO)
        assert "CRC_LENGTH" in [item.code for item in report.violations]

    def test_an_absent_crc_is_reported(self):
        report = validate(parse_payload(SPEC_PAYLOAD[:-8]), EMVCO)
        assert "CRC_MISSING" in [item.code for item in report.violations]


class TestOrdering:
    def test_a_payload_not_starting_with_the_format_indicator(self):
        qr = build([Tlv("53", "950"), Tlv("00", "01")])
        assert "PFI_NOT_FIRST" in [item.code for item in validate(qr, EMVCO).violations]

    def test_the_crc_must_be_last(self):
        # "000201" | 63 04 0000 | 53 03 950 — a CRC that is present but not final.
        report = validate(parse_payload("000201630400005303950"), EMVCO)
        assert "CRC_NOT_LAST" in [item.code for item in report.violations]

    def test_a_wrong_payload_format_indicator_value(self):
        report = validate(minimal(**{"00": "02"}), EMVCO)
        assert "PFI_VALUE" in [item.code for item in report.violations]


class TestMandatoryObjects:
    @pytest.mark.parametrize("tag", ["52", "53", "58", "59", "60"])
    def test_each_mandatory_object(self, tag):
        report = validate(minimal(**{tag: None}), EMVCO)
        assert "MANDATORY_MISSING" in [item.code for item in report.violations]

    def test_at_least_one_merchant_account(self):
        report = validate(minimal(**{"26": None}), EMVCO)
        assert "NO_MERCHANT_ACCOUNT" in [item.code for item in report.violations]

    def test_a_primitive_visa_account_counts(self):
        # IDs 02 to 25 are primitive: the network is implied by the ID, and the
        # template carries no Globally Unique Identifier.
        report = validate(minimal(**{"26": None, "02": "4111111111111111"}), EMVCO)
        assert "NO_MERCHANT_ACCOUNT" not in [item.code for item in report.violations]


class TestFormats:
    def test_mcc_must_be_four_digits(self):
        assert "MCC_FORMAT" in [item.code for item in validate(minimal(**{"52": "54"}), EMVCO).violations]

    def test_mcc_must_be_numeric(self):
        assert "MCC_FORMAT" in [item.code for item in validate(minimal(**{"52": "ABCD"}), EMVCO).violations]

    def test_currency_must_be_three_digits(self):
        assert "CURRENCY_FORMAT" in [item.code for item in validate(minimal(**{"53": "XAF"}), EMVCO).violations]

    def test_country_must_be_two_letters(self):
        assert "COUNTRY_FORMAT" in [item.code for item in validate(minimal(**{"58": "CMR"}), EMVCO).violations]

    def test_a_value_longer_than_its_field(self):
        report = validate(minimal(**{"59": "X" * 26}), EMVCO)
        assert "TOO_LONG" in [item.code for item in report.violations]


class TestAmount:
    @pytest.mark.parametrize("value", ["98", "98.", "98.73", "0.01", "1000000"])
    def test_the_permitted_forms(self, value):
        assert validate(minimal(**{"54": value}), EMVCO).ok is True

    @pytest.mark.parametrize("value", ["98,73", "3 705", "-5", "abc", ""])
    def test_the_forbidden_forms(self, value):
        codes = [item.code for item in validate(minimal(**{"54": value}), EMVCO).violations]
        assert "AMOUNT_FORMAT" in codes

    @pytest.mark.parametrize("value", ["0", "0.", "0.00", "000"])
    def test_zero_is_forbidden(self, value):
        codes = [item.code for item in validate(minimal(**{"54": value}), EMVCO).violations]
        assert "AMOUNT_ZERO" in codes


class TestTipAndFees:
    def test_a_prompt_indicator_needs_nothing_else(self):
        assert validate(minimal(**{"55": "01"}), EMVCO).ok is True

    def test_a_bad_indicator_value(self):
        assert "TIP_INDICATOR" in [item.code for item in validate(minimal(**{"55": "04"}), EMVCO).violations]

    def test_a_fixed_fee_requires_its_object(self):
        codes = [item.code for item in validate(minimal(**{"55": "02"}), EMVCO).violations]
        assert "TIP_FEE_MISSING" in codes

    def test_a_fixed_fee_that_is_present_and_positive(self):
        assert validate(minimal(**{"55": "02", "56": "1.50"}), EMVCO).ok is True

    def test_a_fixed_fee_of_zero(self):
        codes = [item.code for item in validate(minimal(**{"55": "02", "56": "0"}), EMVCO).violations]
        assert "TIP_FEE_ZERO" in codes

    def test_a_fixed_fee_without_its_indicator(self):
        codes = [item.code for item in validate(minimal(**{"56": "1.50"}), EMVCO).violations]
        assert "TIP_FEE_UNEXPECTED" in codes

    def test_a_percentage_fee_requires_its_object(self):
        codes = [item.code for item in validate(minimal(**{"55": "03"}), EMVCO).violations]
        assert "TIP_PERCENT_MISSING" in codes

    def test_a_percentage_fee_in_range(self):
        assert validate(minimal(**{"55": "03", "57": "02.50"}), EMVCO).ok is True

    @pytest.mark.parametrize("value", ["2.5", "0.00", "100.00", "2.50%"])
    def test_a_percentage_fee_out_of_range_or_malformed(self, value):
        codes = [item.code for item in validate(minimal(**{"55": "03", "57": value}), EMVCO).violations]
        assert "TIP_PERCENT_RANGE" in codes

    def test_a_percentage_without_its_indicator(self):
        codes = [item.code for item in validate(minimal(**{"57": "02.50"}), EMVCO).violations]
        assert "TIP_PERCENT_UNEXPECTED" in codes


class TestDuplicatesAndReserved:
    def test_a_duplicate_root_object(self):
        qr = build([Tlv("00", "01"), Tlv("53", "950"), Tlv("53", "950"), Tlv("63", "0000")])
        assert "DUPLICATE_TAG" in [item.code for item in validate(qr, EMVCO).violations]

    def test_an_rfu_object_shall_not_be_present(self):
        # Section 4.5.4.1: IDs 65 to 79 are reserved and must not appear.
        report = validate(minimal(**{"70": "anything"}), EMVCO)
        assert "RFU_PRESENT" in [item.code for item in report.violations]

    def test_an_unreserved_template_is_permitted(self):
        assert validate(minimal(**{"91": "0017com.example.cemac"}), EMVCO).ok is True


class TestNestedTemplates:
    def test_an_unknown_consumer_data_character(self):
        report = validate(minimal(**{"62": "0903AXM"}), EMVCO)
        assert "CONSUMER_DATA_CHARS" in [item.code for item in report.violations]

    def test_a_repeated_consumer_data_character(self):
        report = validate(minimal(**{"62": "0903AAA"}), EMVCO)
        assert "CONSUMER_DATA_DUPLICATE" in [item.code for item in report.violations]

    def test_a_well_formed_consumer_data_request(self):
        assert validate(minimal(**{"62": "0903AME"}), EMVCO).ok is True

    def test_a_merchant_channel_of_the_wrong_length(self):
        report = validate(minimal(**{"62": "1102AB"}), EMVCO)
        assert "MERCHANT_CHANNEL_LENGTH" in [item.code for item in report.violations]

    def test_a_language_template_without_its_preference(self):
        report = validate(minimal(**{"64": "0104NAME"}), EMVCO)
        assert "LANGUAGE_PREFERENCE_MISSING" in [item.code for item in report.violations]

    def test_a_language_template_without_its_alternate_name(self):
        report = validate(minimal(**{"64": "0002FR"}), EMVCO)
        assert "LANGUAGE_NAME_MISSING" in [item.code for item in report.violations]

    def test_a_well_formed_language_template(self):
        assert validate(minimal(**{"64": "0002FR0103NOM"}), EMVCO).ok is True


class TestReport:
    def test_every_violation_is_collected_not_just_the_first(self):
        report = validate(minimal(**{"52": None, "53": None, "58": None}), EMVCO)
        assert len(report.violations) >= 3

    def test_raise_if_invalid(self):
        with pytest.raises(QrValidationError):
            validate(minimal(**{"53": "XAF"}), EMVCO).raise_if_invalid()

    def test_raise_if_invalid_is_silent_when_valid(self):
        validate(minimal(), EMVCO).raise_if_invalid()

    def test_the_exception_carries_every_violation(self):
        report = validate(minimal(**{"52": None, "58": None}), EMVCO)
        with pytest.raises(QrValidationError) as caught:
            report.raise_if_invalid()
        assert len(caught.value.violations) == len(report.violations)

    def test_a_violation_str_names_its_code_and_object(self):
        violation = validate(minimal(**{"53": "XAF"}), EMVCO).violations[0]
        assert "CURRENCY_FORMAT" in str(violation)
        assert "53" in str(violation)


class TestProfiles:
    def test_the_cemac_profile_rejects_a_foreign_currency(self):
        codes = [item.code for item in validate(minimal(**{"53": "156"}), CEMAC).violations]
        assert "PROFILE_CURRENCY" in codes

    def test_the_cemac_profile_accepts_the_franc(self):
        report = validate(minimal(**{"53": "950", "58": "CM"}), CEMAC)
        assert "PROFILE_CURRENCY" not in [item.code for item in report.violations]

    @pytest.mark.parametrize("country", ["CM", "CF", "CG", "GA", "GQ", "TD"])
    def test_every_member_state_is_accepted(self, country):
        report = validate(minimal(**{"58": country}), CEMAC)
        assert "PROFILE_COUNTRY" not in [item.code for item in report.violations]

    @pytest.mark.parametrize("country", ["NG", "FR", "CN", "AO"])
    def test_a_non_member_state_is_rejected(self, country):
        codes = [item.code for item in validate(minimal(**{"58": country}), CEMAC).violations]
        assert "PROFILE_COUNTRY" in codes

    def test_the_cemac_profile_declares_what_it_cannot_check(self):
        # This is the design decision that matters: an outside implementation
        # cannot resolve the CEMAC GUI, because the norm states two different
        # ones, so the profile must say so rather than return a bare pass.
        report = validate(minimal(), CEMAC)
        assert report.ok is True
        assert report.fully_checked is False
        assert len(report.unchecked) >= 1

    def test_the_cemac_profile_requires_the_cemac_data_object(self):
        report = validate(minimal(**{"62": None}), CEMAC)
        assert "CEMAC_DATA_MISSING" in [item.code for item in report.violations]

    def test_the_cemac_data_object_must_be_a_template(self):
        # ID 50 carries a Tag-Length-Value structure, not a flat string.
        report = validate(minimal(**{"62": "5004nope"}), CEMAC)
        assert "CEMAC_DATA_MALFORMED" in [item.code for item in report.violations]

    def test_an_undefined_object_inside_the_cemac_data_object_is_reported(self):
        # Tableau 18-B defines IDs 00 to 03; ID 09 is not one of them. The inner
        # value "0901X" parses cleanly as one object, so this is an unknown
        # object rather than a malformed one.
        report = validate(minimal(**{"62": "50050901X"}), CEMAC)
        assert "CEMAC_DATA_UNKNOWN_OBJECT" in [item.code for item in report.violations]

    def test_the_status_never_overstates_a_partial_check(self):
        assert validate(minimal(), CEMAC).status == "VALID, SUBJECT TO UNCHECKED RULES"

    def test_require_complete_raises_for_cemac(self):
        with pytest.raises(ProfileIncomplete):
            validate(minimal(), CEMAC).require_complete()

    def test_require_complete_is_silent_for_emvco(self):
        validate(minimal(), EMVCO).require_complete()

    def test_an_unknown_profile_name_is_refused(self):
        from cemacqr.errors import UnsupportedProfile

        with pytest.raises(UnsupportedProfile):
            get_profile("cmac")  # typo, and it must not fall back to anything

    def test_the_emvco_profile_restricts_nothing(self):
        assert get_profile("emvco").currencies == ()
        assert get_profile("emvco").countries == ()

    def test_the_cemac_profile_names_its_legal_basis(self):
        assert "02/26" in (get_profile("cemac").legal_basis or "")
