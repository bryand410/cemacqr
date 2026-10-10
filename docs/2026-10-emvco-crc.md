# The CEMAC QR code is not protected by a CRC-32

*What the regulation's published descriptions say, what the specification they
point to actually requires, and why the difference is not detectable by looking
at a working QR code.*

---

The QR Code communautaire de la CEMAC was homologated by *Règlement
n° 02/26/CEMAC/UMAC/CORENOFI du 8 avril 2026* and launched in Douala on
29 July 2026, in front of the Governor of the BEAC, the Secretary General of
COBAC, the Director General of GIMAC and the heads of the regional banks. It
applies to banks, microfinance institutions, payment institutions and
electronic-money issuers across six member states, with a stated target of
**120,000 codes deployed by 2027**.

The regulation's technical choices are described consistently across the
coverage: the QR code is built on **EMV QRCPS v1.1** from EMVCo, with
**ISO/IEC 18004** governing the code itself, **TLV** for the data, and
**CRC-32** for integrity.

Three of those four are exactly right. The fourth is not, and it matters.

## What the specification says

EMV QRCPS v1.1, Merchant-Presented Mode, section 4.7.3.1, in full:

> The checksum shall be calculated according to [ISO/IEC 13239] using the
> polynomial `'1021'` (hex) and initial value `'FFFF'` (hex). The data over which
> the checksum is calculated shall cover all data objects, including their ID,
> Length and Value, to be included in the QR Code, in their respective order, as
> well as the ID and Length of the CRC itself (but excluding its Value).

Polynomial `0x1021`, initial value `0xFFFF`, no input reflection, no output
reflection, no final XOR. That is a **16-bit** checksum — the variant usually
catalogued as **CRC-16/CCITT-FALSE** — and section 4.7.3.2 requires it to be
rendered as **four** hexadecimal characters.

The data object table says the same thing twice more. ID `63`, "CRC", format
`ans`, length `"04"`, presence mandatory.

## Why this is easy to get wrong

"CRC-32" is the checksum a developer reaches for by default. It is in every
standard library, it has a familiar name, and it is what a text search for "crc"
in most languages returns first. Reading a summary that says "CRC-32" and
reaching for `zlib.crc32` is the natural move.

It produces a payload that no reader will accept.

Here is the specification's own worked example — Annex B.7, a Beijing transport
merchant — reduced to its checksum-bearing tail:

```
…0708123456786304A13A
```

`63` is the ID, `04` is the length, `A13A` is the checksum. Now compute both
candidates over everything up to and including `6304`:

| Implementation | Result |
|---|---|
| CRC-16/CCITT-FALSE — polynomial `0x1021`, initial value `0xFFFF` | **`A13A`** ✅ |
| CRC-32 — `zlib.crc32` | `7F7AE5AA` ❌ |

The correct value is four characters. CRC-32 produces eight, and the first four
of them are `7F7A` — not a truncation of the right answer, not a prefix, not
related in any way. There is no bit position at which the two agree.

## Why you cannot catch it by testing

This is the part that makes it dangerous rather than merely wrong.

A QR code carrying a bad checksum **still renders**. It still scans. The camera
still reads it. A decoder that parses the TLV and stops there — which is what a
first implementation does, because the TLV is the interesting part — will read a
perfectly good merchant name, a perfectly good amount, and a perfectly good
merchant account, and complete the transaction.

The failure only appears at the step that actually verifies integrity, and only
if that step is implemented against the specification rather than against the
code that generated the payload. In practice that means: **a wallet built from
the same mistaken description will happily accept the same mistaken codes.** The
error is self-consistent, and self-consistency is what lets it survive
integration testing.

It surfaces later — at the first reader built by someone who read the
specification, or at the first interchange with a system outside the region. By
then the merchant stickers are printed.

## What to do

If you are implementing, use CRC-16/CCITT-FALSE. In Python:

```python
def crc16(data: bytes) -> int:
    register = 0xFFFF
    for byte in data:
        register ^= byte << 8
        for _ in range(8):
            if register & 0x8000:
                register = ((register << 1) ^ 0x1021) & 0xFFFF
            else:
                register = (register << 1) & 0xFFFF
    return register
```

And render it as `"%04X" % crc16(payload.encode("utf-8"))` — uppercase, four
characters, computed over the **UTF-8 bytes** of everything up to and including
the `6304` that introduces the field.

Two further details that follow from the same section and are easy to miss:

**The checksum's own ID and length are covered, its value is not.** The `6304`
is inside the checksum. A library that computes over the payload *without* the
`6304` will produce a value that is wrong by exactly the amount that difference
implies.

**Lengths count characters; the checksum counts bytes.** The specification is
written in terms of Alphanumeric Special characters, and its own example is 248
characters but 260 UTF-8 bytes — six of them, the merchant's alternate name and
city, are three bytes each. A parser that counts bytes rejects every payload
whose merchant name is not in the Latin alphabet. In a union of six member states
where names appear in French, English, Arabic and Fang, that is the ordinary case.

## A note on the sources

I am not in a position to say whether the CEMAC regulation's own annex restates
the EMVCo checksum or adds something of its own. The annex is not public, and
this article is about what the *published* descriptions say and what the
specification they name actually requires. The two are inconsistent, and an
implementer working from the descriptions will build the wrong thing.

The library that came out of this — `cemacqr`, on PyPI — implements the EMVCo
definition, pins it against the Annex B.7 vector, and includes a test that
asserts CRC-32 gives a different answer, so that the distinction cannot be
quietly undone later.

It also refuses to claim more than it can check. The CEMAC-specific elements —
the Globally Unique Identifier, the merchant identifier scheme, which optional
objects the regulation makes mandatory — are declared as unknown, and the
validator reports `VALID, SUBJECT TO UNCHECKED RULES` rather than a bare pass.
A validator that returns success for a payload it only partially examined is
worse than no validator at all.

---

*Ulrich Bryand Tamouffe Teyo — Douala, Cameroun. Security engineering, payment
systems, and the unglamorous parts of infrastructure in Francophone Africa.*

*Sources: EMV QR Code Specification for Payment Systems, Merchant-Presented Mode,
v1.1 (EMVCo, 27 November 2020), sections 4.7.3 and Annex B.7, public access at
emvco.com; Règlement n° 02/26/CEMAC/UMAC/CORENOFI du 8 avril 2026; BEAC/GIMAC
launch of the common QR code, Douala, 29 July 2026.*
