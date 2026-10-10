"""The CORENOFI norm's own worked example.

Every other vector in this suite is either EMVCo's or one I constructed. This one
is the CEMAC's: Annex 4 of the CORENOFI norm *Spécifications du QR code pour
l'acceptation des paiements interopérables dans la CEMAC*, v2.1, March 2025,
page 59, which ends with the clear-text value of a merchant-presented QR code and
its checksum.

It matters for two reasons. First, it is the only test that can catch a misreading
of the *CEMAC* overlay rather than of EMVCo. Second, it settles the checksum
question against a primary source: the norm states ISO/IEC 13239, polynomial
0x1021, initial value 0xFFFF, and its published checksum is reproduced by exactly
that algorithm. Several published descriptions of this QR code announce a CRC-32;
the CEMAC's own example says otherwise.
"""

from __future__ import annotations

import pytest

from cemacqr import EMVCO, crc16_hex, parse_payload, validate
from cemacqr.profile import CEMAC

#: Annex 4, page 59, "Valeur représentative du QR Code (Valeur en clair)".
CORENOFI_EXAMPLE = (
    "00020101021202360012A1560000000001161245825993000001520454625303952540507550"
    "5802CG5921BOULANGERIE PAIN D OR6011BRAZZAVILLE62970308116502840708176540015069"
    "0014A00000065610100105310030208107900010326https://paindor.cg/pmt/t01"
    "63043FD3"
)

#: Everything the checksum covers: all of it but its own value.
CORENOFI_PREFIX = CORENOFI_EXAMPLE[:-4]

#: The value the norm publishes for the checksum.
CORENOFI_CRC = "3FD3"


class TestTheChecksum:
    def test_the_published_checksum_is_reproduced(self):
        assert crc16_hex(CORENOFI_PREFIX.encode("utf-8")) == CORENOFI_CRC

    def test_it_is_not_crc32(self):
        """The norm says ISO/IEC 13239; the press says CRC-32. The norm is right."""
        import zlib

        assert "%08X" % (zlib.crc32(CORENOFI_PREFIX.encode("utf-8")) & 0xFFFFFFFF) != CORENOFI_CRC

    def test_the_payload_reports_a_good_checksum(self):
        assert parse_payload(CORENOFI_EXAMPLE).crc_ok is True


class TestTheFields:
    @pytest.fixture
    def payload(self):
        return parse_payload(CORENOFI_EXAMPLE)

    def test_dynamic_code(self, payload):
        assert payload.point_of_initiation == "12"
        assert payload.is_static is False

    def test_the_bakery(self, payload):
        assert payload.merchant_name == "BOULANGERIE PAIN D OR"
        assert payload.merchant_city == "BRAZZAVILLE"
        assert payload.merchant_category_code == "5462"
        assert payload.country_code == "CG"

    def test_the_amount_has_no_decimal_separator(self, payload):
        from decimal import Decimal

        assert payload.amount == "07550"
        assert payload.amount_decimal == Decimal("7550")
        assert payload.currency == "952"

    def test_the_merchant_account_template(self, payload):
        accounts = payload.merchant_accounts
        assert list(accounts) == ["02"]
        assert accounts["02"]["00"] == "A15600000000"
        assert accounts["02"]["01"] == "1245825993000001"

    def test_the_cemac_data_object(self, payload):
        """ID 50 inside template 62, which is mandatory in the CEMAC profile."""
        children = payload.template("62")
        assert "50" in children
        inner = children["50"]
        assert "A0000006561010" in inner
        assert "31003" in inner
        assert "10790001" in inner
        assert "https://paindor.cg/pmt/t01" in inner


class TestTheNormDisagreesWithItself:
    """The tables and the example string do not match, so neither is enforced.

    Tableau 5 annotates the merchant account template as ``ID=51 (CEMAC)`` and
    Tableau 17 shows the global unique identifier as ``0014 A0000006561010``.
    The example string carries ``0236`` and ``0012 A15600000000``. Since only the
    string reproduces the published checksum, the string is what the norm means
    and the tables drifted. The profile therefore enforces neither, and says so
    in ``CEMAC.undefined``.
    """

    def test_the_example_uses_template_02_not_51(self):
        assert parse_payload(CORENOFI_EXAMPLE).merchant_accounts.keys() == {"02"}

    def test_the_profile_declares_the_ambiguity(self):
        assert any("Globally Unique Identifier" in item for item in CEMAC.undefined)


class TestValidation:
    def test_the_example_is_valid_under_bare_emvco(self):
        report = validate(parse_payload(CORENOFI_EXAMPLE), EMVCO)
        assert report.ok, str(report)

    def test_the_example_trips_the_cemac_currency_rule(self):
        """The norm's example contradicts the norm's own normative table.

        Table 3 (Transaction Currency) states: *"La valeur applicable doit
        toujours être 950 (Valeur numérique à 3 chiffres du FCFA en Afrique
        Centrale -XAF-)"*. Annex 4 encodes ``5303 952`` and its prose says
        *"Devise : XAF (FCFA)"*. But 952 is XOF, the West African franc of the
        UEMOA; the Central African franc is 950. So the example names XAF and
        encodes the other currency.

        A validator that accepted this would be a validator that accepts a
        payment denominated in the wrong money. The profile enforces the table,
        not the example, and the disagreement is recorded here rather than
        smoothed over.
        """
        report = validate(parse_payload(CORENOFI_EXAMPLE), CEMAC)
        assert not report.ok
        codes = [v.code for v in report.violations]
        assert codes == ["PROFILE_CURRENCY"], codes
        assert "952" in report.violations[0].message

    def test_the_rule_and_the_example_disagree_on_the_currency(self):
        payload = parse_payload(CORENOFI_EXAMPLE)
        assert payload.currency == "952"
        assert CEMAC.currencies == ("950",)
