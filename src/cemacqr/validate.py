"""Validation of a merchant-presented payload.

The rules are the ones EMVCo states, plus whatever the selected profile adds.
Two design choices are worth stating, because both are departures from what a
naive validator does.

**A report, not an exception, and not a boolean.** Callers need to know *which*
rule broke — a merchant onboarding form that says "invalid QR" is useless to the
person holding the code. Every violation is collected, not just the first.

**"Valid" and "fully checked" are different answers.** When a profile declares
elements it cannot state, the report says so. A validator that returns a bare
``True`` for a payload it only partially examined is the failure mode this whole
module is built to avoid — and for CEMAC today, that partial state is the honest
description of what any outside implementation can know.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from . import tags as _tags
from . import tlv as _tlv
from .errors import ProfileIncomplete
from .payload import PAYLOAD_FORMAT_VERSION, EmvQr
from .profile import EMVCO, Profile

__all__ = ["ValidationReport", "Violation", "validate"]

_AMOUNT_RE = re.compile(r"^[0-9]+\.?[0-9]*$")
_PERCENTAGE_RE = re.compile(r"^[0-9]{2}\.[0-9]{2}$")
_ALPHA2_RE = re.compile(r"^[A-Za-z]{2}$")

_TIP_PROMPT = "01"
_TIP_FIXED = "02"
_TIP_PERCENTAGE = "03"

#: The three characters permitted in Additional Consumer Data Request (ID "09" under "62").
_CONSUMER_DATA_CHARS = ("A", "M", "E")

#: Value that asks the mobile application to prompt the consumer, for IDs "01" to "08" under "62".
PROMPT_SENTINEL = "***"


@dataclass(frozen=True)
class Violation:
    """One broken rule."""

    code: str
    message: str
    tag: Optional[str] = None

    def __str__(self) -> str:
        if self.tag is None:
            return "[%s] %s" % (self.code, self.message)
        return "[%s] ID %s: %s" % (self.code, self.tag, self.message)


@dataclass
class ValidationReport:
    """The outcome of validating one payload."""

    violations: List[Violation]
    unchecked: List[str]
    profile: Profile

    @property
    def ok(self) -> bool:
        """No rule was broken."""
        return not self.violations

    @property
    def fully_checked(self) -> bool:
        """Every rule the profile defines was actually applied."""
        return not self.unchecked

    @property
    def status(self) -> str:
        """A one-line summary that never overstates the result."""
        if self.violations:
            return "INVALID"
        if self.unchecked:
            return "VALID, SUBJECT TO UNCHECKED RULES"
        return "VALID"

    def raise_if_invalid(self) -> None:
        """Raise :class:`~cemacqr.errors.QrValidationError` if any rule broke."""
        if self.violations:
            from .errors import QrValidationError

            raise QrValidationError([str(item) for item in self.violations])

    def require_complete(self) -> None:
        """Raise :class:`~cemacqr.errors.ProfileIncomplete` if rules went unchecked."""
        if self.unchecked:
            raise ProfileIncomplete(self.profile.name, self.unchecked)

    def __str__(self) -> str:
        lines = ["%s (%s)" % (self.status, self.profile.name)]
        for item in self.violations:
            lines.append("  %s" % item)
        for item in self.unchecked:
            lines.append("  [NOT CHECKED] %s" % item)
        return "\n".join(lines)


def _length_violation(spec: _tags.TagSpec, value: str) -> Optional[Violation]:
    if len(value) > spec.max_length:
        return Violation(
            "TOO_LONG",
            "%s is %d characters; the maximum is %d" % (spec.name, len(value), spec.max_length),
            spec.tag,
        )
    return None


def _check_amount(value: str) -> Optional[Violation]:
    if not _AMOUNT_RE.match(value):
        return Violation(
            "AMOUNT_FORMAT",
            "Transaction Amount %r is not a valid EMVCo amount: digits and at most one "
            "'.' as the decimal mark, and no thousands separator" % value,
            "54",
        )
    if not value.replace(".", "").strip("0"):
        return Violation("AMOUNT_ZERO", "Transaction Amount shall be different from zero", "54")
    return None


def _check_tip(payload: EmvQr) -> List[Violation]:
    """Section 4.7.6 to 4.7.8: the tip indicator and the fee objects must agree."""
    found: List[Violation] = []
    indicator = payload.tip_indicator
    fixed = payload.get("56")
    percentage = payload.get("57")

    if indicator is not None and indicator not in (_TIP_PROMPT, _TIP_FIXED, _TIP_PERCENTAGE):
        found.append(
            Violation(
                "TIP_INDICATOR",
                "Tip or Convenience Indicator shall be '01', '02' or '03', found %r" % indicator,
                "55",
            )
        )

    if indicator == _TIP_FIXED:
        if fixed is None:
            found.append(
                Violation(
                    "TIP_FEE_MISSING",
                    "Tip indicator is '02', so Value of Convenience Fee Fixed (ID 56) shall be present",
                    "56",
                )
            )
        else:
            if not _AMOUNT_RE.match(fixed):
                found.append(
                    Violation("TIP_FEE_FORMAT", "Value of Convenience Fee Fixed %r is malformed" % fixed, "56")
                )
            elif not fixed.replace(".", "").strip("0"):
                found.append(
                    Violation("TIP_FEE_ZERO", "Value of Convenience Fee Fixed shall be different from zero", "56")
                )
    elif fixed is not None:
        found.append(
            Violation(
                "TIP_FEE_UNEXPECTED",
                "Value of Convenience Fee Fixed is present but the tip indicator is not '02'",
                "56",
            )
        )

    if indicator == _TIP_PERCENTAGE:
        if percentage is None:
            found.append(
                Violation(
                    "TIP_PERCENT_MISSING",
                    "Tip indicator is '03', so Value of Convenience Fee Percentage (ID 57) shall be present",
                    "57",
                )
            )
        elif not _PERCENTAGE_RE.match(percentage) or not ("00.01" <= percentage <= "99.99"):
            found.append(
                Violation(
                    "TIP_PERCENT_RANGE",
                    "Value of Convenience Fee Percentage %r shall be between '00.01' and '99.99', "
                    "with no '%%' character" % percentage,
                    "57",
                )
            )
    elif percentage is not None:
        found.append(
            Violation(
                "TIP_PERCENT_UNEXPECTED",
                "Value of Convenience Fee Percentage is present but the tip indicator is not '03'",
                "57",
            )
        )

    return found


def _check_additional_data(payload: EmvQr, profile: Profile) -> List[Violation]:
    """Table 3.7 constraints inside template 62, plus the profile's overlay."""
    found: List[Violation] = []
    children = payload.template(_tags.TEMPLATE_ADDITIONAL_DATA)
    scheme = profile.name

    request = children.get("09")
    if request is not None:
        if not request:
            found.append(Violation("CONSUMER_DATA_EMPTY", "Additional Consumer Data Request is empty", "09"))
        else:
            unknown = [c for c in request if c not in _CONSUMER_DATA_CHARS]
            if unknown:
                found.append(
                    Violation(
                        "CONSUMER_DATA_CHARS",
                        "Additional Consumer Data Request contains %r; only 'A', 'M' and 'E' are defined"
                        % "".join(sorted(set(unknown))),
                        "09",
                    )
                )
            duplicates = sorted({c for c in request if request.count(c) > 1})
            if duplicates:
                found.append(
                    Violation(
                        "CONSUMER_DATA_DUPLICATE",
                        "Additional Consumer Data Request repeats %r; each character shall appear once"
                        % "".join(duplicates),
                        "09",
                    )
                )

    channel = children.get("11")
    if channel is not None and len(channel) != 3:
        found.append(Violation("MERCHANT_CHANNEL_LENGTH", "Merchant Channel shall be exactly 3 characters", "11"))

    # -- CEMAC overlay ---------------------------------------------------
    if scheme == "cemac":
        # The CORENOFI norm, Tableau 15, marks ID 50 as M: a payload without it
        # is not CEMAC-conforming, however well-formed it is as EMVCo.
        if _tags.TEMPLATE_CEMAC_DATA not in children:
            found.append(
                Violation(
                    "CEMAC_DATA_MISSING",
                    "the CEMAC profile requires the CEMAC payment system data object (ID 50) "
                    "inside the Additional Data Field Template (ID 62); it is absent",
                    _tags.TEMPLATE_CEMAC_DATA,
                )
            )
        else:
            found.extend(_check_cemac_data(children[_tags.TEMPLATE_CEMAC_DATA]))

    for tag, value in children.items():
        spec = _tags.resolve(_tags.TEMPLATE_ADDITIONAL_DATA, tag, scheme)
        if spec is not None:
            issue = _length_violation(spec, value)
            if issue is not None:
                found.append(issue)

    return found


def _check_cemac_data(value: str) -> List[Violation]:
    """Tableau 18-B constraints inside ID 50, which is a template of its own."""
    found: List[Violation] = []
    try:
        children = _tlv.parse(value)
    except Exception:
        found.append(
            Violation(
                "CEMAC_DATA_MALFORMED",
                "the CEMAC payment system data object (ID 50) is a template and its value does "
                "not parse as Tag-Length-Value data",
                _tags.TEMPLATE_CEMAC_DATA,
            )
        )
        return found

    for child in children:
        spec = _tags.resolve(_tags.TEMPLATE_CEMAC_DATA, child.tag)
        if spec is None:
            found.append(
                Violation(
                    "CEMAC_DATA_UNKNOWN_OBJECT",
                    "ID %s is not defined inside the CEMAC payment system data object; "
                    "Tableau 18-B defines IDs 00 to 03" % (child.tag,),
                    _tags.TEMPLATE_CEMAC_DATA,
                )
            )
            continue
        issue = _length_violation(spec, child.value)
        if issue is not None:
            found.append(issue)

    return found


def _check_language_template(payload: EmvQr) -> List[Violation]:
    """Table 3.8 constraints inside template 64."""
    found: List[Violation] = []
    for item in payload.objects:
        if item.tag != _tags.TEMPLATE_LANGUAGE:
            continue
        children = {child.tag: child.value for child in item.children()}
        preference = children.get("00")
        if preference is None:
            found.append(
                Violation(
                    "LANGUAGE_PREFERENCE_MISSING",
                    "Merchant Information—Language Template is present but Language Preference (ID 00) is absent",
                    "64",
                )
            )
        elif not _ALPHA2_RE.match(preference):
            found.append(
                Violation(
                    "LANGUAGE_PREFERENCE_FORMAT",
                    "Language Preference %r shall be two alphabetical characters (ISO 639)" % preference,
                    "00",
                )
            )
        if "01" not in children:
            found.append(
                Violation(
                    "LANGUAGE_NAME_MISSING",
                    "Merchant Information—Language Template is present but Merchant Name—Alternate Language "
                    "(ID 01) is absent",
                    "64",
                )
            )
    return found


def validate(payload: EmvQr, profile: Profile = EMVCO) -> ValidationReport:
    """Apply the EMVCo rules and the profile's constraints to ``payload``.

    Returns a report. Never raises for a payload that is merely invalid — use
    :meth:`ValidationReport.raise_if_invalid` when an exception is wanted.
    """
    violations: List[Violation] = []

    if not payload.objects:
        violations.append(Violation("EMPTY", "payload contains no data objects"))
        return ValidationReport(violations, list(profile.undefined), profile)

    # -- ordering and the checksum ---------------------------------------
    first, last = payload.objects[0], payload.objects[-1]

    if first.tag != "00":
        violations.append(
            Violation(
                "PFI_NOT_FIRST",
                "Payload Format Indicator (ID 00) shall be the first data object; found ID %s" % first.tag,
                "00",
            )
        )
    if last.tag != _tags.TEMPLATE_CRC:
        violations.append(
            Violation(
                "CRC_NOT_LAST",
                "CRC (ID 63) shall be the last data object; found ID %s" % last.tag,
                "63",
            )
        )

    pfi = payload.payload_format_indicator
    if pfi is None:
        violations.append(Violation("PFI_MISSING", "Payload Format Indicator (ID 00) is absent", "00"))
    elif pfi != PAYLOAD_FORMAT_VERSION:
        violations.append(
            Violation(
                "PFI_VALUE",
                "Payload Format Indicator shall be %r, found %r" % (PAYLOAD_FORMAT_VERSION, pfi),
                "00",
            )
        )

    stated = payload.stated_crc
    if stated is None:
        violations.append(Violation("CRC_MISSING", "CRC (ID 63) is absent", "63"))
    elif len(stated) != 4:
        violations.append(Violation("CRC_LENGTH", "CRC shall be 4 characters, found %d" % len(stated), "63"))
    elif payload.computed_crc is not None and stated.upper() != payload.computed_crc:
        violations.append(
            Violation(
                "CRC_MISMATCH",
                "CRC is %s but the payload computes to %s — note that EMVCo specifies a 16-bit "
                "checksum (polynomial 0x1021, initial value 0xFFFF), not CRC-32"
                % (stated.upper(), payload.computed_crc),
                "63",
            )
        )

    # -- duplicates ------------------------------------------------------
    seen: List[str] = []
    for item in payload.objects:
        if item.tag in seen:
            violations.append(
                Violation("DUPLICATE_TAG", "ID %s appears more than once under the root" % item.tag, item.tag)
            )
        seen.append(item.tag)

    # -- reserved for future use -----------------------------------------
    for item in payload.objects:
        if item.tag.isdigit() and 65 <= int(item.tag) <= 79:
            violations.append(
                Violation(
                    "RFU_PRESENT",
                    "ID %s is Reserved for Future Use and shall not be included (section 4.5.4.1)" % item.tag,
                    item.tag,
                )
            )

    # -- mandatory root objects ------------------------------------------
    for tag in ("52", "53", "58", "59", "60"):
        spec = _tags.root(tag)
        if payload.get(tag) is None:
            violations.append(
                Violation("MANDATORY_MISSING", "%s (ID %s) is mandatory and absent" % (spec.name, tag), tag)
            )

    if not payload.merchant_accounts:
        violations.append(
            Violation(
                "NO_MERCHANT_ACCOUNT",
                "at least one Merchant Account Information object (IDs 02 to 51) shall be present",
            )
        )

    # -- per-object format and length ------------------------------------
    for item in payload.objects:
        spec = _tags.root(item.tag)
        if spec is None:
            continue
        issue = _length_violation(spec, item.value)
        if issue is not None:
            violations.append(issue)

    mcc = payload.merchant_category_code
    if mcc is not None and not (mcc.isdigit() and len(mcc) == 4):
        violations.append(Violation("MCC_FORMAT", "Merchant Category Code shall be 4 digits, found %r" % mcc, "52"))

    currency = payload.currency
    if currency is not None and not (currency.isdigit() and len(currency) == 3):
        violations.append(
            Violation(
                "CURRENCY_FORMAT",
                "Transaction Currency shall be the 3-digit ISO 4217 numeric code, found %r" % currency,
                "53",
            )
        )

    country = payload.country_code
    if country is not None and not _ALPHA2_RE.match(country):
        violations.append(
            Violation(
                "COUNTRY_FORMAT",
                "Country Code shall be two characters (ISO 3166-1 alpha-2), found %r" % country,
                "58",
            )
        )

    amount = payload.amount
    if amount is not None:
        issue = _check_amount(amount)
        if issue is not None:
            violations.append(issue)

    violations.extend(_check_tip(payload))
    violations.extend(_check_additional_data(payload, profile))
    violations.extend(_check_language_template(payload))

    # -- profile constraints ---------------------------------------------
    if profile.currencies and currency is not None and currency not in profile.currencies:
        violations.append(
            Violation(
                "PROFILE_CURRENCY",
                "%s permits only currency %s; found %r" % (profile.name, "/".join(profile.currencies), currency),
                "53",
            )
        )

    if profile.countries and country is not None and country.upper() not in profile.countries:
        violations.append(
            Violation(
                "PROFILE_COUNTRY",
                "%s permits only country codes %s; found %r" % (profile.name, ", ".join(profile.countries), country),
                "58",
            )
        )

    return ValidationReport(violations, list(profile.undefined), profile)


def prompt_requested(payload: EmvQr, tag: str) -> bool:
    """Whether the merchant asked the consumer to supply ``tag`` under template 62.

    EMVCo section 4.8: the merchant includes the ID with length ``"03"`` and the
    value ``"***"`` to ask the mobile application to prompt. A reader that treats
    ``"***"`` as data will display three asterisks to a customer as their bill
    number.
    """
    return payload.get_in(_tags.TEMPLATE_ADDITIONAL_DATA, tag) == PROMPT_SENTINEL
