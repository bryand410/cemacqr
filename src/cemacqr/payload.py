"""The Merchant-Presented payload: parsing, inspection, construction.

The object keeps the original string and the decoded objects side by side, so
that a caller can always round-trip a payload byte for byte. That matters more
than it sounds: the checksum covers every character of the payload, so any
"helpful" normalisation during a parse — reordering objects, trimming a value,
re-encoding a template — produces a payload whose checksum no longer matches.
:meth:`EmvQr.to_string` therefore re-emits what it read unless you ask it to
rebuild.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as _dc_field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

from . import tags as _tags
from .crc import crc16_hex
from .errors import QrSyntaxError
from .tlv import Tlv, parse

__all__ = ["PAYLOAD_FORMAT_VERSION", "EmvQr", "build", "parse_payload"]

#: The only value of the Payload Format Indicator defined by v1.1.
PAYLOAD_FORMAT_VERSION = "01"

_STATIC = "11"
_DYNAMIC = "12"


@dataclass
class EmvQr:
    """A parsed EMVCo merchant-presented payload."""

    raw: str
    objects: List[Tlv] = _dc_field(default_factory=list)

    # -- construction ----------------------------------------------------

    @classmethod
    def parse(cls, text: str) -> EmvQr:
        """Parse a payload string.

        Raises :class:`~cemacqr.errors.QrSyntaxError` if the string is not
        well-formed TLV. This method does **not** check the checksum: use
        :attr:`crc_ok` or :func:`cemacqr.validate` for that, so that a caller
        can inspect a payload that is known to be damaged.
        """
        if not isinstance(text, str):
            raise QrSyntaxError("payload must be a string, got %s" % type(text).__name__)
        stripped = text.strip()
        if not stripped:
            raise QrSyntaxError("payload is empty")
        return cls(raw=stripped, objects=parse(stripped))

    # -- access ----------------------------------------------------------

    def get(self, tag: str) -> Optional[str]:
        """Value of ``tag`` under the root, or ``None``."""
        for item in self.objects:
            if item.tag == tag:
                return item.value
        return None

    def get_in(self, parent: str, tag: str) -> Optional[str]:
        """Value of ``tag`` inside template ``parent``, or ``None``."""
        for item in self.objects:
            if item.tag == parent:
                for child in item.children():
                    if child.tag == tag:
                        return child.value
        return None

    def template(self, parent: str) -> Dict[str, str]:
        """All children of ``parent`` as a ``{tag: value}`` mapping."""
        for item in self.objects:
            if item.tag == parent:
                return {child.tag: child.value for child in item.children()}
        return {}

    @property
    def tags(self) -> List[str]:
        """IDs present under the root, in order."""
        return [item.tag for item in self.objects]

    @property
    def merchant_accounts(self) -> Dict[str, Dict[str, str]]:
        """Every Merchant Account Information template, keyed by its ID.

        There is normally more than one — a single QR code is expected to carry
        an account for each network the merchant accepts, which is the whole
        point of the format.
        """
        found: Dict[str, Dict[str, str]] = {}
        for item in self.objects:
            if item.tag.isdigit() and 2 <= int(item.tag) <= 51:
                found[item.tag] = {child.tag: child.value for child in item.children()}
        return found

    # -- fields ----------------------------------------------------------

    @property
    def payload_format_indicator(self) -> Optional[str]:
        return self.get("00")

    @property
    def point_of_initiation(self) -> Optional[str]:
        """``"11"`` for a reusable code, ``"12"`` for a single-use one."""
        return self.get("01")

    @property
    def is_static(self) -> Optional[bool]:
        """``True`` when the same code is shown for more than one transaction.

        ``None`` when the payload does not say — which is legal, the object is
        optional, and a reader must not assume either way.
        """
        value = self.point_of_initiation
        if value is None:
            return None
        if value == _STATIC:
            return True
        if value == _DYNAMIC:
            return False
        return None

    @property
    def merchant_category_code(self) -> Optional[str]:
        return self.get("52")

    @property
    def currency(self) -> Optional[str]:
        """ISO 4217 **numeric** code. For the Central African franc that is ``"950"``."""
        return self.get("53")

    @property
    def amount(self) -> Optional[str]:
        """Transaction amount exactly as encoded, or ``None`` if the consumer enters it.

        Kept as a string on purpose. The specification permits ``"98."`` and
        ``"98"`` as well as ``"98.73"``, and coercing to a float would turn a
        legitimate representation into a rounding decision this library has no
        business making.
        """
        return self.get("54")

    @property
    def amount_decimal(self) -> Optional[Decimal]:
        """The amount as a :class:`~decimal.Decimal`, or ``None``.

        ``"98."`` is accepted, because the specification accepts it.
        """
        text = self.amount
        if text is None:
            return None
        try:
            return Decimal(text.rstrip(".") or "0")
        except InvalidOperation:
            return None

    @property
    def country_code(self) -> Optional[str]:
        """ISO 3166-1 alpha-2 code of the merchant acceptance device."""
        return self.get("58")

    @property
    def merchant_name(self) -> Optional[str]:
        return self.get("59")

    @property
    def merchant_city(self) -> Optional[str]:
        return self.get("60")

    @property
    def postal_code(self) -> Optional[str]:
        return self.get("61")

    @property
    def tip_indicator(self) -> Optional[str]:
        """``"01"`` prompt, ``"02"`` fixed fee, ``"03"`` percentage fee."""
        return self.get("55")

    # -- checksum --------------------------------------------------------

    @property
    def stated_crc(self) -> Optional[str]:
        """The checksum carried in the payload, if present."""
        return self.get("63")

    @property
    def computed_crc(self) -> Optional[str]:
        """The checksum this payload should carry, or ``None`` if uncomputable.

        Computed over every character up to and including the ``6304`` that
        introduces the checksum — see :mod:`cemacqr.crc`.
        """
        marker = self._crc_marker()
        if marker is None:
            return None
        return crc16_hex(self.raw[:marker].encode("utf-8"))

    def _crc_marker(self) -> Optional[int]:
        """Offset of the end of the CRC's ID and Length, i.e. where its value begins."""
        for item in self.objects:
            if item.tag == _tags.TEMPLATE_CRC:
                # Re-encode everything before it, so that a payload with the CRC
                # in the wrong position still yields a computable value.
                return len(self.raw) - len(item.value)
        return None

    @property
    def crc_ok(self) -> bool:
        """Whether the carried checksum matches the computed one."""
        stated, computed = self.stated_crc, self.computed_crc
        if stated is None or computed is None:
            return False
        return stated.upper() == computed.upper()

    def with_crc(self) -> str:
        """Return the payload with a freshly computed checksum.

        Use this after modifying a payload. The returned string is not stored:
        this object stays a faithful representation of what was read.
        """
        return _append_crc(self.without_crc())

    def without_crc(self) -> str:
        """Return the payload with the CRC object removed entirely."""
        kept = [item for item in self.objects if item.tag != _tags.TEMPLATE_CRC]
        return "".join(item.as_text() for item in kept)

    def to_string(self) -> str:
        """The payload exactly as it was read."""
        return self.raw

    def __str__(self) -> str:
        return self.raw

    def __repr__(self) -> str:
        return "EmvQr(%s, %d object%s, crc=%s)" % (
            "valid" if self.crc_ok else "CRC MISMATCH",
            len(self.objects),
            "" if len(self.objects) == 1 else "s",
            self.stated_crc or "absent",
        )


def _append_crc(payload_without_crc: str) -> str:
    """Append ``63 04 XXXX``, computing the checksum over the result so far.

    The ``04`` is written literally rather than through :func:`~cemacqr.tlv.encode`:
    the checksum's own ID and Length are part of the data it covers, so the value
    is empty at the moment the length would be computed. Encoding an empty value
    would emit ``6300``, and the four hexadecimal characters that follow would
    then be read as a new data object with a non-numeric ID.
    """
    body = "%s6304" % payload_without_crc
    return "%s%s" % (body, crc16_hex(body.encode("utf-8")))


def build(objects: List[Tlv]) -> EmvQr:
    """Assemble a payload from data objects, appending a correct checksum.

    The objects are emitted in the order given, minus any CRC you passed in —
    a supplied checksum is always discarded, because the only correct one is the
    one computed over the finished payload.
    """
    body = "".join(item.as_text() for item in objects if item.tag != _tags.TEMPLATE_CRC)
    text = _append_crc(body)
    return EmvQr.parse(text)


def parse_payload(text: str) -> EmvQr:
    """Parse a payload string.

    Module-level form of :meth:`EmvQr.parse`, so that ``cemacqr.parse_payload``
    and ``cemacqr.parse_tlv`` are symmetric and neither shadows the other.
    """
    return EmvQr.parse(text)
