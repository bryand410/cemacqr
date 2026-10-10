"""The EMVCo Merchant-Presented Mode data object registry.

Everything here is transcribed from *EMV QR Code Specification for Payment
Systems — Merchant-Presented Mode*, v1.1, Tables 3.3, 3.7, 3.8, 4.1 and 4.2.
Nothing is inferred.

The registry is deliberately a plain data structure rather than code: it is the
part of this library most likely to be extended for a national profile (CEMAC
defines its own rules on top of EMVCo), and adding a row should not require
reading a function.

**Context is not optional.** EMVCo reuses IDs across templates — ID ``01`` is the
Point of Initiation Method under the root and the Bill Number under ``62``. The
lookup functions therefore take the parent, and :func:`resolve` refuses to answer
without one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

__all__ = [
    "ADDITIONAL_DATA_FIELD",
    "ADDITIONAL_DATA_FIELD_CEMAC",
    "CEMAC_PAYMENT_SYSTEM_DATA",
    "LANGUAGE_TEMPLATE",
    "MERCHANT_ACCOUNT_INFO",
    "ROOT",
    "TEMPLATE_ADDITIONAL_DATA",
    "TEMPLATE_CEMAC_DATA",
    "TEMPLATE_CRC",
    "TEMPLATE_LANGUAGE",
    "TagSpec",
    "merchant_account_info_owner",
    "resolve",
    "root",
]

# Template IDs, named so that call sites read as prose.
TEMPLATE_ADDITIONAL_DATA = "62"
TEMPLATE_CRC = "63"
TEMPLATE_LANGUAGE = "64"
TEMPLATE_CEMAC_DATA = "50"

_FORMAT_NUMERIC = "N"
_FORMAT_ALNUM_SPECIAL = "ans"
_FORMAT_STRING = "S"

_PRESENCE_MANDATORY = "M"
_PRESENCE_CONDITIONAL = "C"
_PRESENCE_OPTIONAL = "O"


@dataclass(frozen=True)
class TagSpec:
    """One row of an EMVCo data object table."""

    tag: str
    name: str
    format: str
    max_length: int
    presence: str
    is_template: bool = False

    @property
    def mandatory(self) -> bool:
        return self.presence == _PRESENCE_MANDATORY


def _spec(tag, name, fmt, max_length, presence, is_template=False) -> TagSpec:
    return TagSpec(tag, name, fmt, max_length, presence, is_template)


#: Table 3.3 — the data objects that appear under the root of the payload.
ROOT: Dict[str, TagSpec] = {
    "00": _spec("00", "Payload Format Indicator", _FORMAT_NUMERIC, 2, _PRESENCE_MANDATORY),
    "01": _spec("01", "Point of Initiation Method", _FORMAT_NUMERIC, 2, _PRESENCE_OPTIONAL),
    "52": _spec("52", "Merchant Category Code", _FORMAT_NUMERIC, 4, _PRESENCE_MANDATORY),
    "53": _spec("53", "Transaction Currency", _FORMAT_NUMERIC, 3, _PRESENCE_MANDATORY),
    "54": _spec("54", "Transaction Amount", _FORMAT_ALNUM_SPECIAL, 13, _PRESENCE_CONDITIONAL),
    "55": _spec("55", "Tip or Convenience Indicator", _FORMAT_NUMERIC, 2, _PRESENCE_OPTIONAL),
    "56": _spec("56", "Value of Convenience Fee Fixed", _FORMAT_ALNUM_SPECIAL, 13, _PRESENCE_CONDITIONAL),
    "57": _spec("57", "Value of Convenience Fee Percentage", _FORMAT_ALNUM_SPECIAL, 5, _PRESENCE_CONDITIONAL),
    "58": _spec("58", "Country Code", _FORMAT_ALNUM_SPECIAL, 2, _PRESENCE_MANDATORY),
    "59": _spec("59", "Merchant Name", _FORMAT_ALNUM_SPECIAL, 25, _PRESENCE_MANDATORY),
    "60": _spec("60", "Merchant City", _FORMAT_ALNUM_SPECIAL, 15, _PRESENCE_MANDATORY),
    "61": _spec("61", "Postal Code", _FORMAT_ALNUM_SPECIAL, 10, _PRESENCE_OPTIONAL),
    "62": _spec("62", "Additional Data Field Template", _FORMAT_STRING, 99, _PRESENCE_OPTIONAL, True),
    "63": _spec("63", "CRC", _FORMAT_ALNUM_SPECIAL, 4, _PRESENCE_MANDATORY),
    "64": _spec("64", "Merchant Information—Language Template", _FORMAT_STRING, 99, _PRESENCE_OPTIONAL, True),
}

#: Table 3.7 — data objects valid inside the Additional Data Field Template (ID "62").
ADDITIONAL_DATA_FIELD: Dict[str, TagSpec] = {
    "01": _spec("01", "Bill Number", _FORMAT_ALNUM_SPECIAL, 25, _PRESENCE_OPTIONAL),
    "02": _spec("02", "Mobile Number", _FORMAT_ALNUM_SPECIAL, 25, _PRESENCE_OPTIONAL),
    "03": _spec("03", "Store Label", _FORMAT_ALNUM_SPECIAL, 25, _PRESENCE_OPTIONAL),
    "04": _spec("04", "Loyalty Number", _FORMAT_ALNUM_SPECIAL, 25, _PRESENCE_OPTIONAL),
    "05": _spec("05", "Reference Label", _FORMAT_ALNUM_SPECIAL, 25, _PRESENCE_OPTIONAL),
    "06": _spec("06", "Customer Label", _FORMAT_ALNUM_SPECIAL, 25, _PRESENCE_OPTIONAL),
    "07": _spec("07", "Terminal Label", _FORMAT_ALNUM_SPECIAL, 25, _PRESENCE_OPTIONAL),
    "08": _spec("08", "Purpose of Transaction", _FORMAT_ALNUM_SPECIAL, 25, _PRESENCE_OPTIONAL),
    "09": _spec("09", "Additional Consumer Data Request", _FORMAT_ALNUM_SPECIAL, 3, _PRESENCE_OPTIONAL),
    "10": _spec("10", "Merchant Tax ID", _FORMAT_ALNUM_SPECIAL, 20, _PRESENCE_OPTIONAL),
    "11": _spec("11", "Merchant Channel", _FORMAT_ALNUM_SPECIAL, 3, _PRESENCE_OPTIONAL),
}

#: The CEMAC overlay on Table 3.7, transcribed from the CORENOFI norm
#: *Spécifications du QR code pour l'acceptation des paiements interopérables
#: dans la CEMAC*, v2.1 (March 2025), Tableau 15.
#:
#: Three differences from EMVCo matter, and none of them is guessable:
#:
#: * ID ``50`` is **mandatory** and is itself a template. EMVCo leaves the range
#:   50-99 reserved; CEMAC allocates 50 to *données spécifiques aux systèmes de
#:   paiement CEMAC*, and the norm's own example carries it.
#: * IDs ``51`` to ``80`` are reserved for the CEMAC regional scheme, so a
#:   conforming payload may not put arbitrary content there.
#: * IDs ``12`` to ``49`` remain reserved for EMVCo, as in EMVCo.
#:
#: The norm's revision table also records that IDs ``6251`` and ``6252``, present
#: in the earlier draft, were **deleted** in v2.1 in favour of ID 50. Payloads
#: carrying them are pre-homologation.
ADDITIONAL_DATA_FIELD_CEMAC: Dict[str, TagSpec] = dict(ADDITIONAL_DATA_FIELD)
ADDITIONAL_DATA_FIELD_CEMAC[TEMPLATE_CEMAC_DATA] = _spec(
    TEMPLATE_CEMAC_DATA,
    "Données spécifiques aux systèmes de paiement CEMAC",
    _FORMAT_STRING,
    99,
    _PRESENCE_MANDATORY,
    True,
)

#: Tableau 18-B — data objects valid inside ID ``50``, which is a template in its
#: own right. ID ``03`` is the *système à notifier*: an acquirer system URL, or a
#: reference to one, called when the funds reach the merchant's account. It is the
#: object that lets a terminal close a payment without polling.
CEMAC_PAYMENT_SYSTEM_DATA: Dict[str, TagSpec] = {
    "00": _spec("00", "PN-UID — identifiant du système de paiement", _FORMAT_ALNUM_SPECIAL, 26, _PRESENCE_OPTIONAL),
    "01": _spec("01", "Identifiant de l'entité membre participante", _FORMAT_ALNUM_SPECIAL, 6, _PRESENCE_OPTIONAL),
    "02": _spec("02", "Alias du compte du commerçant", _FORMAT_ALNUM_SPECIAL, 26, _PRESENCE_OPTIONAL),
    "03": _spec("03", "Système à notifier", _FORMAT_ALNUM_SPECIAL, 99, _PRESENCE_OPTIONAL),
}

#: Table 3.8 — data objects valid inside the Merchant Information—Language Template (ID "64").
LANGUAGE_TEMPLATE: Dict[str, TagSpec] = {
    "00": _spec("00", "Language Preference", _FORMAT_ALNUM_SPECIAL, 2, _PRESENCE_MANDATORY),
    "01": _spec("01", "Merchant Name—Alternate Language", _FORMAT_STRING, 25, _PRESENCE_MANDATORY),
    "02": _spec("02", "Merchant City—Alternate Language", _FORMAT_STRING, 15, _PRESENCE_OPTIONAL),
}

#: Table 4.2 — data objects valid inside a Merchant Account Information template (IDs "26" to "51").
MERCHANT_ACCOUNT_INFO: Dict[str, TagSpec] = {
    "00": _spec("00", "Globally Unique Identifier", _FORMAT_ALNUM_SPECIAL, 32, _PRESENCE_MANDATORY),
}

#: Table 4.1 — which network owns which Merchant Account Information ID.
_MAI_ALLOCATION: Tuple[Tuple[int, int, str], ...] = (
    (2, 3, "Visa"),
    (4, 5, "Mastercard"),
    (6, 8, "EMVCo"),
    (9, 10, "Discover"),
    (11, 12, "American Express"),
    (13, 14, "JCB"),
    (15, 16, "UnionPay"),
    (17, 25, "EMVCo"),
    (26, 51, "open — any payment network meeting section 4.7.11"),
)


def resolve(parent: Optional[str], tag: str, scheme: str = "emvco") -> Optional[TagSpec]:
    """Look up ``tag`` in the context of ``parent``.

    ``parent=None`` means the root. Returns ``None`` when the ID is not defined
    in that context — which is a fact about the payload, not an error, and the
    caller decides what to do with it.

    ``scheme`` selects the overlay. ``"emvco"`` is the bare specification;
    ``"cemac"`` additionally defines ID 50 inside template 62, and reads IDs 51
    to 80 of that template as reserved for the CEMAC regional scheme rather than
    for other players. The two differ only inside template 62, which is why this
    is a parameter and not a second registry.
    """
    if parent is None:
        if tag in ROOT:
            return ROOT[tag]
        if tag.isdigit() and 2 <= int(tag) <= 51:
            return TagSpec(
                tag=tag,
                name="Merchant Account Information",
                format=_FORMAT_STRING,
                max_length=99,
                presence=_PRESENCE_MANDATORY,
                is_template=True,
            )
        if tag.isdigit() and 65 <= int(tag) <= 79:
            return TagSpec(tag, "RFU for EMVCo", _FORMAT_STRING, 99, _PRESENCE_OPTIONAL, True)
        if tag.isdigit() and 80 <= int(tag) <= 99:
            return TagSpec(tag, "Unreserved Template", _FORMAT_STRING, 99, _PRESENCE_OPTIONAL, True)
        return None

    if parent == TEMPLATE_ADDITIONAL_DATA:
        if scheme == "cemac":
            return ADDITIONAL_DATA_FIELD_CEMAC.get(tag)
        return ADDITIONAL_DATA_FIELD.get(tag)

    if parent == TEMPLATE_CEMAC_DATA:
        return CEMAC_PAYMENT_SYSTEM_DATA.get(tag)

    if parent == TEMPLATE_LANGUAGE:
        return LANGUAGE_TEMPLATE.get(tag)

    if parent.isdigit() and 26 <= int(parent) <= 51:
        return MERCHANT_ACCOUNT_INFO.get(tag)

    if parent.isdigit() and 80 <= int(parent) <= 99:
        # Unreserved Templates: ID "00" is the Globally Unique Identifier and
        # every other ID is allocated by whoever owns the template.
        return MERCHANT_ACCOUNT_INFO.get(tag)

    return None


def root(tag: str) -> Optional[TagSpec]:
    """Convenience wrapper for :func:`resolve` at the root."""
    return resolve(None, tag)


def merchant_account_info_owner(tag: str) -> Optional[str]:
    """Return the network an ID in the range "02" to "51" is reserved for.

    Useful when reading a payload you did not produce: it tells you which
    network's specification to consult for the contents of the template.
    """
    if not (tag.isdigit() and len(tag) == 2):
        return None
    value = int(tag)
    for low, high, owner in _MAI_ALLOCATION:
        if low <= value <= high:
            return owner
    return None
