"""Exceptions raised by :mod:`cemacqr`.

The hierarchy separates three outcomes that are easy to conflate and expensive
to confuse:

* :class:`CemacQrError` — base class, so ``except CemacQrError`` catches all.
* :class:`QrSyntaxError` — the payload is not a well-formed TLV string. Nothing
  can be concluded about the payment; the bytes are simply not a QR payload.
* :class:`QrValidationError` — the payload parses, but a rule is broken. This is
  a *conclusive* negative: the QR code is invalid and a reader must reject it.
* :class:`ProfileIncomplete` — the payload may be fine, but the profile this
  library holds does not describe enough to say so.

The third one exists on purpose and is the reason this library refuses to print
a green "compliant" badge it cannot justify. See :mod:`cemacqr.profile`.
"""

from __future__ import annotations

from typing import Optional

__all__ = [
    "CemacQrError",
    "ProfileIncomplete",
    "QrSyntaxError",
    "QrValidationError",
    "UnsupportedProfile",
]


class CemacQrError(Exception):
    """Base class for every error raised by this package."""


class QrSyntaxError(CemacQrError):
    """The string is not a well-formed TLV payload.

    Raised with the character offset of the failure, because a TLV parser that
    only says "malformed" forces the integrator to bisect the payload by hand.
    """

    def __init__(self, message: str, *, offset: Optional[int] = None) -> None:
        super().__init__(message if offset is None else "%s (at character %d)" % (message, offset))
        self.offset = offset


class QrValidationError(CemacQrError):
    """The payload is well formed but breaks a rule.

    Carries every rule violation found, not just the first, so that a caller
    fixing a merchant onboarding form sees the whole list in one pass.
    """

    def __init__(self, violations: list[str]) -> None:
        self.violations = list(violations)
        super().__init__(
            "%d validation violation%s: %s"
            % (
                len(self.violations),
                "" if len(self.violations) == 1 else "s",
                "; ".join(self.violations),
            )
        )


class ProfileIncomplete(CemacQrError):
    """The profile does not define enough to judge compliance.

    This is deliberately *not* a subclass of :class:`QrValidationError`. A
    profile that is silent is not a payload that is wrong, and an implementation
    that treats "I don't know" as "invalid" will reject valid payments.
    """

    def __init__(self, profile: str, missing: list[str]) -> None:
        self.profile = profile
        self.missing = list(missing)
        super().__init__(
            "profile %r cannot be enforced: %d element%s undefined (%s)"
            % (profile, len(self.missing), "" if len(self.missing) == 1 else "s", ", ".join(self.missing))
        )


class UnsupportedProfile(CemacQrError):
    """The named profile is not registered."""
