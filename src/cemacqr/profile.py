"""National profiles layered on top of EMVCo.

A profile is data, not code. It says which currencies and country codes a
national scheme permits, and — the part that matters — **which of its own rules
it cannot yet state**. A profile that silently omits an undefined rule produces
a validator that reports success for a payload it never actually checked, which
is worse than no validator at all.

The CEMAC profile here is the honest version of that idea. The QR code was
homologated by *Règlement n° 02/26/CEMAC/UMAC/CORENOFI du 8 avril 2026* and
launched in Douala on 29 July 2026. The regulation's technical annex is not
public. So this profile enforces exactly the constraints that are verifiable
from the EMVCo specification and the published CEMAC facts, and raises
:class:`~cemacqr.errors.ProfileIncomplete` for the rest rather than guessing.

If you work for GIMAC, the BEAC, or a participant institution and can supply the
annex, the gap closes in one edit: the missing elements are listed in
:attr:`Profile.undefined`.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as _dc_field
from typing import Dict, Optional, Tuple

from .errors import UnsupportedProfile

__all__ = ["CEMAC", "EMVCO", "PROFILES", "Profile", "get_profile"]

#: ISO 3166-1 alpha-2 codes of the six CEMAC member states.
CEMAC_COUNTRIES: Tuple[str, ...] = ("CM", "CF", "CG", "GA", "GQ", "TD")

#: ISO 4217 *numeric* code of the Central African CFA franc.
#:
#: Note that this is ``"950"``, not ``"XAF"`` and not ``"FCFA"``. EMVCo section
#: 4.7.5.1 requires the three-digit numeric form. The franc of the UEMOA is a
#: different currency with a different numeric code, and the two are not
#: interchangeable despite both being called "franc CFA" in everyday speech.
CEMAC_CURRENCY = "950"


@dataclass(frozen=True)
class Profile:
    """Constraints a national scheme imposes on an EMVCo payload."""

    name: str
    title: str
    currencies: Tuple[str, ...]
    countries: Tuple[str, ...]
    legal_basis: Optional[str] = None
    notes: str = ""
    #: Elements the profile knows exist but cannot state. Non-empty means the
    #: validator will raise rather than report compliance.
    undefined: Tuple[str, ...] = ()
    #: Extra rules expressed as ``(tag, predicate_description)`` for reporting.
    extra_rules: Tuple[str, ...] = _dc_field(default=())

    @property
    def complete(self) -> bool:
        """Whether this profile is fully specified."""
        return not self.undefined


EMVCO = Profile(
    name="emvco",
    title="EMVCo Merchant-Presented Mode v1.1 — no national overlay",
    currencies=(),
    countries=(),
    notes=(
        "Checks only the requirements the EMVCo specification states. An empty "
        "currencies or countries tuple means the scheme does not restrict that "
        "field, not that the field is unconstrained."
    ),
)

CEMAC = Profile(
    name="cemac",
    title="QR Code communautaire CEMAC",
    currencies=(CEMAC_CURRENCY,),
    countries=CEMAC_COUNTRIES,
    legal_basis="Règlement n° 02/26/CEMAC/UMAC/CORENOFI du 8 avril 2026",
    notes=(
        "Homologated 8 April 2026, launched 29 July 2026 in Douala. Built on "
        "EMV QRCPS v1.1 and ISO/IEC 18004, TLV-encoded. Interbank routing and "
        "clearing are performed by GIMAC. Applies to banks, microfinance "
        "institutions, payment institutions and electronic-money issuers in "
        "Cameroun, the Central African Republic, Congo, Gabon, Equatorial "
        "Guinea and Chad."
    ),
    undefined=(
        "the Globally Unique Identifier allocated to CEMAC participants in the "
        "Merchant Account Information template (IDs 26-51)",
        "the merchant identifier scheme, if the regulation defines one beyond the EMVCo Merchant PAN",
        "the subset of optional EMVCo data objects the regulation makes mandatory for CEMAC acceptance",
        "whether CEMAC adds a checksum beyond the EMVCo CRC, or merely restates it",
    ),
)

PROFILES: Dict[str, Profile] = {EMVCO.name: EMVCO, CEMAC.name: CEMAC}


def get_profile(name: str) -> Profile:
    """Return a registered profile by name.

    Raises :class:`~cemacqr.errors.UnsupportedProfile` for an unknown name —
    never falls back to the default, because a typo silently selecting a weaker
    profile is exactly the failure a validator exists to prevent.
    """
    try:
        return PROFILES[name]
    except KeyError:
        raise UnsupportedProfile(
            "unknown profile %r; registered profiles are: %s" % (name, ", ".join(sorted(PROFILES)))
        ) from None
