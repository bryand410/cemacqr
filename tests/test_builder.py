"""The builder, and the mistakes it exists to make impossible."""

from __future__ import annotations

import pytest

from cemacqr import CEMAC, CEMAC_CURRENCY, EMVCO, MerchantQr, parse_payload, validate


def base() -> MerchantQr:
    return (
        MerchantQr()
        .merchant(name="BOULANGERIE AKWA", city="Douala", country="CM")
        .category("5462")
        .currency(CEMAC_CURRENCY)
        .account("26", gui="com.example.cemac", merchant_pan="2376000000001")
    )


class TestCurrency:
    def test_the_franc_constant_is_the_numeric_code(self):
        # ISO 4217 numeric for the Central African franc. Not "XAF", not "FCFA".
        assert CEMAC_CURRENCY == "950"

    def test_the_numeric_code_is_accepted(self):
        assert parse_payload(str(base().build())).currency == "950"

    def test_the_alphabetic_code_is_refused(self):
        with pytest.raises(ValueError) as caught:
            base().currency("XAF")
        assert "950" in str(caught.value)

    def test_a_symbol_is_refused(self):
        with pytest.raises(ValueError):
            base().currency("FCFA")

    def test_a_payload_built_with_the_wrong_currency_would_have_validated(self):
        # The point of refusing at build time: "156" is a perfectly valid
        # currency, so nothing downstream would have caught it. Only the profile
        # knows it is wrong for CEMAC, and only if the profile is complete.
        report = validate(parse_payload(str(base().currency("156").build())), EMVCO)
        assert report.ok is True
        assert "PROFILE_CURRENCY" in [
            item.code for item in validate(parse_payload(str(base().currency("156").build())), CEMAC).violations
        ]


class TestMandatoryFields:
    def test_a_payload_without_a_name_is_refused(self):
        with pytest.raises(ValueError):
            MerchantQr().merchant(name="", city="Douala", country="CM")

    def test_a_payload_without_a_city_is_refused(self):
        with pytest.raises(ValueError):
            MerchantQr().merchant(name="X", city="", country="CM")

    def test_a_bad_country_code_is_refused(self):
        with pytest.raises(ValueError):
            MerchantQr().merchant(name="X", city="Y", country="CMR")

    def test_a_lowercase_country_code_is_uppercased(self):
        qr = (
            MerchantQr()
            .merchant(name="X", city="Y", country="cm")
            .category("5411")
            .currency("950")
            .account("26", gui="com.example.cemac")
        )
        assert qr.build().country_code == "CM"

    def test_a_bad_mcc_is_refused(self):
        with pytest.raises(ValueError):
            base().category("54")

    def test_building_without_a_category_names_the_missing_field(self):
        with pytest.raises(ValueError) as caught:
            MerchantQr().merchant(name="X", city="Y", country="CM").currency("950").account("26", gui="a").build()
        assert "Merchant Category Code" in str(caught.value)

    def test_building_without_an_account_is_refused(self):
        with pytest.raises(ValueError) as caught:
            MerchantQr().merchant(name="X", city="Y", country="CM").category("5411").currency("950").build()
        assert "Merchant Account" in str(caught.value)


class TestAmount:
    def test_omitting_the_amount_produces_a_reusable_code(self):
        # Presence of ID 54 *is* the static/dynamic distinction; there is no flag.
        qr = base().build()
        assert qr.amount is None

    def test_a_present_amount(self):
        assert base().amount("1500").build().amount == "1500"

    def test_a_decimal_amount(self):
        assert base().amount("1500.50").build().amount == "1500.50"

    def test_a_comma_is_refused(self):
        with pytest.raises(ValueError):
            base().amount("1500,50")

    def test_zero_is_refused(self):
        with pytest.raises(ValueError):
            base().amount("0")

    def test_a_thousands_separator_is_refused(self):
        with pytest.raises(ValueError):
            base().amount("1 500")


class TestTips:
    def test_a_prompt(self):
        assert base().tip_prompt().build().tip_indicator == "01"

    def test_a_fixed_fee(self):
        qr = base().convenience_fee_fixed("100").build()
        assert qr.tip_indicator == "02"
        assert qr.get("56") == "100"

    def test_a_percentage_fee(self):
        qr = base().convenience_fee_percentage("02.50").build()
        assert qr.tip_indicator == "03"
        assert qr.get("57") == "02.50"

    def test_a_zero_fixed_fee_is_refused(self):
        with pytest.raises(ValueError):
            base().convenience_fee_fixed("0")

    @pytest.mark.parametrize("value", ["2.5", "0.00", "100.00"])
    def test_a_percentage_out_of_range_is_refused(self, value):
        with pytest.raises(ValueError):
            base().convenience_fee_percentage(value)


class TestAccounts:
    def test_the_gui_is_written_to_id_00(self):
        accounts = base().build().merchant_accounts
        assert accounts["26"]["00"] == "com.example.cemac"

    def test_the_merchant_pan_is_written_to_id_01(self):
        assert base().build().merchant_accounts["26"]["01"] == "2376000000001"

    def test_extra_context_specific_fields(self):
        qr = base().account("31", gui="com.example.other", **{"05": "REF"}).build()
        assert qr.merchant_accounts["31"]["05"] == "REF"

    def test_several_accounts(self):
        qr = base().account("31", gui="com.example.second", merchant_pan="999").build()
        assert sorted(qr.merchant_accounts) == ["26", "31"]

    @pytest.mark.parametrize("template_id", ["25", "52", "02", "abc"])
    def test_a_template_id_outside_the_open_range_is_refused(self, template_id):
        with pytest.raises(ValueError):
            base().account(template_id, gui="com.example.cemac")

    def test_an_overlong_gui_is_refused(self):
        with pytest.raises(ValueError):
            base().account("26", gui="x" * 33)

    def test_an_empty_gui_is_refused(self):
        with pytest.raises(ValueError):
            base().account("26", gui="")


class TestAdditionalData:
    def test_a_bill_number(self):
        assert base().bill_number("F-2026-0001").build().get_in("62", "01") == "F-2026-0001"

    def test_a_reference_label(self):
        assert base().reference("INV42").build().get_in("62", "05") == "INV42"

    def test_a_terminal_label(self):
        assert base().terminal("C001").build().get_in("62", "07") == "C001"

    def test_an_undefined_id_is_refused(self):
        with pytest.raises(ValueError):
            base().additional("99", "x")

    def test_prompting_the_consumer_uses_the_sentinel(self):
        from cemacqr import prompt_requested

        qr = base().prompt_consumer_for("01", "02").build()
        assert qr.get_in("62", "01") == "***"
        assert prompt_requested(qr, "01") is True

    def test_prompting_an_id_outside_the_promptable_range_is_refused(self):
        with pytest.raises(ValueError):
            base().prompt_consumer_for("09")


class TestLanguageTemplate:
    def test_the_template_is_built(self):
        qr = base().alternate_language(language="FR", merchant_name="BOULANGERIE AKWA").build()
        assert qr.template("64") == {"00": "FR", "01": "BOULANGERIE AKWA"}

    def test_with_an_alternate_city(self):
        qr = base().alternate_language(language="FR", merchant_name="A", merchant_city="Douala").build()
        assert qr.template("64")["02"] == "Douala"

    def test_a_bad_language_code_is_refused(self):
        with pytest.raises(ValueError):
            base().alternate_language(language="FRA", merchant_name="A")


class TestOutput:
    def test_the_payload_is_valid_under_emvco(self):
        report = validate(base().build(), EMVCO)
        assert report.ok is True, str(report)

    def test_it_satisfies_the_cemac_profile_rules_that_are_checkable(self):
        report = validate(base().build(), CEMAC)
        assert report.ok is True, str(report)
        assert report.fully_checked is False

    def test_the_checksum_is_correct(self):
        assert base().build().crc_ok is True

    def test_building_is_deterministic(self):
        assert str(base().build()) == str(base().build())

    def test_the_payload_starts_and_ends_correctly(self):
        payload = str(base().build())
        assert payload.startswith("000201")
        assert payload[-8:-4] == "6304"

    def test_the_builder_is_reusable(self):
        builder = base()
        assert str(builder.build()) == str(builder.build())
