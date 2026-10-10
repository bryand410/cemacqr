"""Tag-Length-Value parsing and serialisation, as EMV QRCPS defines it.

Three properties of the format matter and are easy to get wrong.

**Lengths count characters, not bytes.** The specification is written in terms
of Alphanumeric Special characters, and its own worked example (Annex B.7) is
256 UTF-8 bytes but 244 characters. A parser that counts bytes will reject every
payload carrying a merchant name in a non-Latin script — which, in a region
where merchant names appear in French, English, Arabic and Fang, is most of the
interesting ones. This module counts characters, and the test suite pins the
distinction against the specification's example.

**Every template is parsed with the same rule.** There is no separate grammar for
nested templates: ID ``62`` (Additional Data Field Template) contains TLV, and
so does ``64``. The parser is therefore uniform, and the *meaning* of an inner ID
depends entirely on its parent — ID ``01`` under the root is the Point of
Initiation Method, ID ``01`` under ``62`` is a Bill Number. Anything that
resolves tags by ID alone will silently mislabel half the payload.

**Nothing is guessed.** A truncated value, a non-numeric tag, a stray character
— each raises :class:`~cemacqr.errors.QrSyntaxError` with the offset. A parser
that repairs malformed input is a parser that turns a corrupt QR code into a
payment.
"""

from __future__ import annotations

from typing import Iterator, List, NamedTuple

from .errors import QrSyntaxError

__all__ = ["Tlv", "encode", "encode_all", "iter_parse", "parse", "parse_tlv"]

#: Width, in characters, of an EMVCo data object ID.
TAG_WIDTH = 2

#: Width, in characters, of the Length field.
LENGTH_WIDTH = 2


class Tlv(NamedTuple):
    """One decoded data object."""

    tag: str
    value: str

    def as_text(self) -> str:
        """Re-encode to the wire form ``ID || Length || Value``."""
        return "%s%02d%s" % (self.tag, len(self.value), self.value)

    def children(self) -> List[Tlv]:
        """Parse the value as a nested template, or return an empty list.

        Returning empty rather than raising is deliberate: a caller inspecting a
        payload does not know in advance which objects are templates, and
        "this value is not TLV" is an answer, not an error.
        """
        try:
            return parse(self.value)
        except QrSyntaxError:
            return []


def _require_digits(text: str, offset: int, what: str) -> None:
    if not text.isdigit():
        raise QrSyntaxError("%s must be two decimal digits, found %r" % (what, text), offset=offset)


def parse(data: str) -> List[Tlv]:
    """Decode a TLV string into its data objects, in the order they appear.

    Order is preserved and meaningful: the Payload Format Indicator must come
    first, the CRC last, and everything between is at the emitter's discretion.
    Re-encoding a payload through :func:`encode_all` therefore reproduces the
    original bytes, which is what lets a caller round-trip a QR code without
    invalidating its checksum.

    Raises :class:`~cemacqr.errors.QrSyntaxError` on any malformed input.
    """
    return list(iter_parse(data))


def iter_parse(data: str) -> Iterator[Tlv]:
    """Streaming form of :func:`parse`.

    The iterator yields as it goes, so a caller can inspect the Payload Format
    Indicator before the rest of the payload has been decoded.
    """
    cursor = 0
    total = len(data)
    while cursor < total:
        if total - cursor < TAG_WIDTH + LENGTH_WIDTH:
            raise QrSyntaxError(
                "truncated data object: %d character%s left, need at least %d for ID and Length"
                % (total - cursor, "" if total - cursor == 1 else "s", TAG_WIDTH + LENGTH_WIDTH),
                offset=cursor,
            )

        tag = data[cursor : cursor + TAG_WIDTH]
        _require_digits(tag, cursor, "data object ID")

        length_text = data[cursor + TAG_WIDTH : cursor + TAG_WIDTH + LENGTH_WIDTH]
        _require_digits(length_text, cursor + TAG_WIDTH, "Length")

        length = int(length_text)
        start = cursor + TAG_WIDTH + LENGTH_WIDTH
        end = start + length

        if end > total:
            raise QrSyntaxError(
                "data object %s declares %d character%s but only %d remain"
                % (tag, length, "" if length == 1 else "s", total - start),
                offset=start,
            )

        yield Tlv(tag, data[start:end])
        cursor = end


def encode(tag: str, value: str) -> str:
    """Encode one data object.

    Raises :class:`ValueError` for a tag or value that cannot be represented —
    a caller building a payload wants to hear about that at construction time,
    not when the QR code fails to scan.
    """
    if len(tag) != TAG_WIDTH or not tag.isdigit():
        raise ValueError("data object ID must be two decimal digits, got %r" % (tag,))
    if len(value) > 99:
        raise ValueError("value is %d characters; the Length field is two digits, so 99 is the maximum" % len(value))
    return "%s%02d%s" % (tag, len(value), value)


def encode_all(objects: List[Tlv]) -> str:
    """Encode a sequence of data objects back into a payload string."""
    return "".join(item.as_text() for item in objects)


#: Alias, so that ``cemacqr.parse_tlv`` reads unambiguously next to
#: ``cemacqr.parse_payload``.
parse_tlv = parse
