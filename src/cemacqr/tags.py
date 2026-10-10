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
    "LANGUAGE_TEMPLATE",
    "MERCHANT_ACCOUNT_INFO",
    "ROOT",
    "TEMPLATE_ADDITIONAL_DATA",
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


def resolve(parent: Optional[str], tag: str) -> Optional[TagSpec]:
    """Look up ``tag`` in the context of ``parent``.

    ``parent=None`` means the root. Returns ``None`` when the ID is not defined
    in that context — which is a fact about the payload, not an error, and the
    caller decides what to do with it.
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

    table = {
        TEMPLATE_ADDITIONAL_DATA: ADDITIONAL_DATA_FIELD,
        TEMPLATE_LANGUAGE: LANGUAGE_TEMPLATE,
    }.get(parent)

    if table is not None:
        return table.get(tag)

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
