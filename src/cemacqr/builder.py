"""Building a merchant-presented payload.

The builder exists so that the three things most likely to produce a rejected
QR code are impossible to get wrong by accident:

1. **The currency must be the ISO 4217 numeric code.** A builder that accepts
   ``"XAF"`` and stores it produces a payload that fails at the reader, hours
   after the merchant printed the sticker. :meth:`MerchantQr.currency` validates
   at call time.
2. **The checksum must be computed last, over the finished payload.** No API here
   lets you supply one.
3. **The Payload Format Indicator and the CRC must sit first and last.** They are
   added by :meth:`MerchantQr.build`, not by the caller.

Example
-------

>>> from cemacqr import MerchantQr
>>> qr = (MerchantQr()
...       .merchant(name="BOULANGERIE AKWA", city="Douala", country="CM")
...       .category("5411")
...       .currency("950")
...       .account("26", gui="com.example.cemac", merchant_pan="1234567890")
...       .build())
>>> qr.crc_ok
True
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from . import tags as _tags
from .payload import EmvQr, build
from .profile import CEMAC_CURRENCY
from .tlv import Tlv

__all__ = ["MerchantQr"]

_ALPHA2 = re.compile(r"^[A-Za-z]{2}$")
_MCC = re.compile(r"^[0-9]{4}$")
_NUMERIC3 = re.compile(r"^[0-9]{3}$")

_TAG_PFI = "00"
_TAG_POI = "01"
_TAG_AMOUNT = "54"
_TAG_TIP = "55"
_TAG_FEE_FIXED = "56"
_TAG_FEE_PERCENTAGE = "57"
_TAG_MCC = "52"
_TAG_CURRENCY = "53"
_TAG_COUNTRY = "58"
_TAG_NAME = "59"
_TAG_CITY = "60"
_TAG_POSTAL = "61"
_TAG_ADDITIONAL = "62"
_TAG_LANGUAGE = "64"

_STATIC = "11"
_DYNAMIC = "12"


class MerchantQr:
    """Assembles a merchant-presented payload.

    Every setter returns ``self`` so that a build reads as one expression, and
    every setter raises :class:`ValueError` immediately on a value that cannot
    be represented — a QR code that fails to build is far cheaper than one that
    builds and then fails to scan.
    """

    def __init__(self) -> None:
        self._root: Dict[str, str] = {}
        self._accounts: List[Tlv] = []
        self._additional: Dict[str, str] = {}
        self._language: Dict[str, str] = {}

    # -- merchant identity ------------------------------------------------

    def merchant(self, *, name: str, city: str, country: str, postal_code: Optional[str] = None) -> MerchantQr:
        """Merchant Name (59), Merchant City (60), Country Code (58) and optionally Postal Code (61)."""
        if not name:
            raise ValueError("Merchant Name is mandatory")
        if not city:
            raise ValueError("Merchant City is mandatory")
        if not _ALPHA2.match(country):
            raise ValueError(
                "Country Code must be an ISO 3166-1 alpha-2 code such as 'CM' or 'GA', got %r" % (country,)
            )
        self._root[_TAG_NAME] = name
        self._root[_TAG_CITY] = city
        self._root[_TAG_COUNTRY] = country.upper()
        if postal_code is not None:
            self._root[_TAG_POSTAL] = postal_code
        return self

    def category(self, mcc: str) -> MerchantQr:
        """Merchant Category Code (52) — four digits, ISO 18245."""
        if not _MCC.match(mcc):
            raise ValueError("Merchant Category Code must be four digits, got %r" % (mcc,))
        self._root[_TAG_MCC] = mcc
        return self

    # -- money ------------------------------------------------------------

    def currency(self, code: str) -> MerchantQr:
        """Transaction Currency (53) — the ISO 4217 **numeric** code.

        For the Central African franc that is ``"950"``. The alphabetic code
        ``"XAF"`` is not accepted: the specification requires three digits, and
        a reader in the region will reject anything else. Use the module constant
        :data:`cemacqr.CEMAC_CURRENCY` rather than typing it.
        """
        if not _NUMERIC3.match(code):
            raise ValueError(
                "Transaction Currency must be the 3-digit ISO 4217 numeric code "
                "(the Central African franc is %r), got %r" % (CEMAC_CURRENCY, code)
            )
        self._root[_TAG_CURRENCY] = code
        return self

    def amount(self, value: str) -> MerchantQr:
        """Transaction Amount (54).

        Omit it entirely to produce a reusable code where the consumer enters the
        amount — that is the difference between a static and a dynamic code, and
        it is expressed by the presence of this object, not by a flag.
        """
        text = str(value)
        if not re.match(r"^[0-9]+\.?[0-9]*$", text):
            raise ValueError("Transaction Amount may contain digits and at most one '.' decimal mark, got %r" % (text,))
        if not text.replace(".", "").strip("0"):
            raise ValueError("Transaction Amount shall be different from zero")
        self._root[_TAG_AMOUNT] = text
        return self

    def reusable(self, value: bool = True) -> MerchantQr:
        """Point of Initiation Method (01): ``"11"`` reusable, ``"12"`` single use."""
        self._root[_TAG_POI] = _STATIC if value else _DYNAMIC
        return self

    def tip_prompt(self) -> MerchantQr:
        """Ask the mobile application to prompt the consumer for a tip (55 = ``"01"``)."""
        self._root[_TAG_TIP] = "01"
        return self

    def convenience_fee_fixed(self, value: str) -> MerchantQr:
        """A fixed convenience fee (55 = ``"02"``, 56 = ``value``)."""
        if not value.replace(".", "").strip("0"):
            raise ValueError("Value of Convenience Fee Fixed shall be different from zero")
        self._root[_TAG_TIP] = "02"
        self._root[_TAG_FEE_FIXED] = str(value)
        return self

    def convenience_fee_percentage(self, value: str) -> MerchantQr:
        """A percentage convenience fee (55 = ``"03"``, 57 = ``value``)."""
        if not re.match(r"^[0-9]{2}\.[0-9]{2}$", str(value)) or not ("00.01" <= str(value) <= "99.99"):
            raise ValueError(
                "Value of Convenience Fee Percentage must be between '00.01' and '99.99', got %r" % (value,)
            )
        self._root[_TAG_TIP] = "03"
        self._root[_TAG_FEE_PERCENTAGE] = str(value)
        return self

    # -- accounts ---------------------------------------------------------

    def account(self, template_id: str, *, gui: str, merchant_pan: Optional[str] = None, **extra: str) -> MerchantQr:
        """Add a Merchant Account Information template (IDs ``"26"`` to ``"51"``).

        ``gui`` is the Globally Unique Identifier that tells the reader whose
        account this is: an Application Identifier, a UUID without hyphens, or a
        reverse domain name. Everything after it is context-specific, which is
        why the remaining fields are keyword arguments rather than a fixed set.

        ``merchant_pan`` is written to ID ``"01"``. **For CEMAC the correct GUI
        is not published** — see :mod:`cemacqr.profile` — so a payload built with
        a placeholder will validate against EMVCo and will not be accepted by a
        participant institution until the value is known.
        """
        if not (template_id.isdigit() and 26 <= int(template_id) <= 51):
            raise ValueError(
                "template ID must be between '26' and '51' to carry an explicit Globally Unique "
                "Identifier, got %r" % (template_id,)
            )
        if not gui or len(gui) > 32:
            raise ValueError("Globally Unique Identifier must be 1 to 32 characters")

        children = [Tlv("00", gui)]
        if merchant_pan is not None:
            children.append(Tlv("01", merchant_pan))
        for key, value in extra.items():
            children.append(Tlv(key, value))

        self._accounts.append(Tlv(template_id, "".join(child.as_text() for child in children)))
        return self

    # -- additional data --------------------------------------------------

    def bill_number(self, value: str) -> MerchantQr:
        self._additional["01"] = value
        return self

    def reference(self, value: str) -> MerchantQr:
        """Reference Label (ID ``"05"`` under 62) — free-form, merchant-defined."""
        self._additional["05"] = value
        return self

    def terminal(self, value: str) -> MerchantQr:
        self._additional["07"] = value
        return self

    def additional(self, tag: str, value: str) -> MerchantQr:
        """Set any data object inside the Additional Data Field Template (62)."""
        if _tags.resolve(_tags.TEMPLATE_ADDITIONAL_DATA, tag) is None:
            raise ValueError("ID %r is not defined in the Additional Data Field Template; see cemacqr.tags" % (tag,))
        self._additional[tag] = value
        return self

    def prompt_consumer_for(self, *tags: str) -> MerchantQr:
        """Ask the mobile application to prompt for these IDs (``"01"`` to ``"08"`` under 62).

        Implements the EMVCo convention of section 4.8: length ``"03"`` and value
        ``"***"``.
        """
        for tag in tags:
            if tag not in ("01", "02", "03", "04", "05", "06", "07", "08"):
                raise ValueError("only IDs '01' to '08' under template 62 can prompt the consumer, got %r" % (tag,))
            self._additional[tag] = "***"
        return self

    def alternate_language(
        self, *, language: str, merchant_name: str, merchant_city: Optional[str] = None
    ) -> MerchantQr:
        """Add the Merchant Information—Language Template (64).

        This is what lets one QR code read as "BOULANGERIE AKWA" in a French
        wallet and as the same name in another script in another. In a region
        with six member states and several scripts it is the difference between
        a code that is usable and one that is legible.
        """
        if not _ALPHA2.match(language):
            raise ValueError("Language Preference must be two alphabetical characters (ISO 639), got %r" % (language,))
        self._language = {"00": language.upper(), "01": merchant_name}
        if merchant_city is not None:
            self._language["02"] = merchant_city
        return self

    # -- assembly ---------------------------------------------------------

    def objects(self) -> List[Tlv]:
        """The data objects in the order they will be emitted."""
        result: List[Tlv] = [Tlv(_TAG_PFI, "01")]

        if _TAG_POI in self._root:
            result.append(Tlv(_TAG_POI, self._root[_TAG_POI]))

        result.extend(self._accounts)

        for tag in (
            _TAG_MCC,
            _TAG_CURRENCY,
            _TAG_AMOUNT,
            _TAG_TIP,
            _TAG_FEE_FIXED,
            _TAG_FEE_PERCENTAGE,
            _TAG_COUNTRY,
            _TAG_NAME,
            _TAG_CITY,
            _TAG_POSTAL,
        ):
            if tag in self._root:
                result.append(Tlv(tag, self._root[tag]))

        if self._additional:
            inner = "".join(Tlv(tag, value).as_text() for tag, value in sorted(self._additional.items()))
            result.append(Tlv(_TAG_ADDITIONAL, inner))

        if self._language:
            inner = "".join(Tlv(tag, value).as_text() for tag, value in sorted(self._language.items()))
            result.append(Tlv(_TAG_LANGUAGE, inner))

        return result

    def build(self) -> EmvQr:
        """Produce the payload, with a correct checksum appended.

        Raises :class:`ValueError` if a mandatory object is missing, so that the
        failure names the missing field rather than surfacing later as a
        validation violation.
        """
        missing = [
            name
            for name, present in (
                ("Merchant Category Code", _TAG_MCC in self._root),
                ("Transaction Currency", _TAG_CURRENCY in self._root),
                ("Country Code", _TAG_COUNTRY in self._root),
                ("Merchant Name", _TAG_NAME in self._root),
                ("Merchant City", _TAG_CITY in self._root),
            )
            if not present
        ]
        if missing:
            raise ValueError("cannot build a payload without: %s" % ", ".join(missing))
        if not self._accounts:
            raise ValueError("cannot build a payload without at least one Merchant Account Information object")

        return build(self.objects())

    def __str__(self) -> str:
        return str(self.build())
