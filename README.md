# cemacqr

**Build, read and check the CEMAC common QR code.** Zero dependencies, no
registration, no permission to ask for.

[![CI](https://github.com/bryand410/cemacqr/actions/workflows/ci.yml/badge.svg)](https://github.com/bryand410/cemacqr/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cemacqr.svg)](https://pypi.org/project/cemacqr/)
[![Python](https://img.shields.io/pypi/pyversions/cemacqr.svg)](https://pypi.org/project/cemacqr/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

```bash
pip install cemacqr
```

---

## The one thing to know first

**The checksum is a 16-bit CRC, not CRC-32.**

EMV QRCPS v1.1, section 4.7.3.1, says it exactly:

> The checksum shall be calculated according to [ISO/IEC 13239] using the
> polynomial `'1021'` (hex) and initial value `'FFFF'` (hex).

Polynomial `0x1021`, initial value `0xFFFF`, four hexadecimal characters. That is
the variant catalogued as **CRC-16/CCITT-FALSE**.

Several published descriptions of the CEMAC common QR code announce a "CRC-32".
Building from those descriptions produces a payload whose checksum no reader in
the region will accept — and CRC-32 over the same bytes gives `7F7AE5AA` where
the specification's own worked example requires `A13A`. Eight characters where
four are permitted, and not even a truncation of the right value.

The test suite pins the difference against the specification's Annex B.7
example. See [docs/2026-10-emvco-crc.md](docs/2026-10-emvco-crc.md).

---

## Quick start

```python
>>> from cemacqr import parse_payload, validate, CEMAC

>>> qr = parse_payload(
...     "00020101021229300012D156000000000510A93FO3230Q31280012D15600000001030812"
...     "345678520441115802CN5914BEST TRANSPORT6007BEIJING64200002ZH0104最佳运输"
...     "0202北京540523.7253031565502016233030412340603***0708A60086670902ME"
...     "91320016A0112233449988770708123456786304A13A"
... )
>>> qr.merchant_name
'BEST TRANSPORT'
>>> qr.crc_ok
True
>>> qr.amount_decimal
Decimal('23.72')

>>> print(validate(qr, CEMAC))
INVALID (cemac)
  [PROFILE_CURRENCY] ID 53: cemac permits only currency 950; found '156'
  [PROFILE_COUNTRY] ID 58: cemac permits only country codes CM, CF, CG, GA, GQ, TD; found 'CN'
  [NOT CHECKED] the Globally Unique Identifier allocated to CEMAC participants…
```

Building a merchant code:

```python
from cemacqr import MerchantQr, CEMAC_CURRENCY

qr = (
    MerchantQr()
    .merchant(name="BOULANGERIE AKWA", city="Douala", country="CM")
    .category("5462")
    .currency(CEMAC_CURRENCY)  # "950" — the numeric code, never "XAF"
    .reusable(True)  # omit .amount() and the consumer enters it
    .bill_number("F-2026-0001")
    .account("26", gui="…", merchant_pan="2376000000001")
    .build()
)
print(qr)  # the payload string
print(qr.crc_ok)  # True
```

## En français, en dix lignes

`cemacqr` construit, lit et vérifie le **QR Code communautaire de la CEMAC**
(homologué par le Règlement n° 02/26/CEMAC/UMAC/CORENOFI du 8 avril 2026, lancé
le 29 juillet 2026 à Douala). Aucune dépendance, aucune inscription.

```python
from cemacqr import MerchantQr, CEMAC_CURRENCY, validate, CEMAC

qr = (
    MerchantQr()
    .merchant(name="BOULANGERIE AKWA", city="Douala", country="CM")
    .category("5462")
    .currency(CEMAC_CURRENCY)  # « 950 » — le code numérique, jamais « XAF »
    .account("26", gui="…", merchant_pan="2376000000001")
    .build()
)

print(validate(qr, CEMAC))  # ce qui est vérifié, et ce qui ne peut pas l'être
```

⚠️ **Le point à retenir : le contrôle d'intégrité est un CRC 16 bits**
(polynôme `0x1021`, valeur initiale `0xFFFF`), **pas un CRC-32**. Plusieurs
descriptions publiées du QR CEMAC annoncent un « CRC-32 » : un code construit
d'après elles sera rejeté par tous les lecteurs de la zone.

## Command line

```bash
cemacqr crc    "<payload>"          # recompute the checksum and compare  (exit 1 on mismatch)
cemacqr check  "<payload>"          # validate                              (exit 1 if invalid)
cemacqr check  "<payload>" --profile cemac --json
cemacqr parse  "<payload>" --expand # decode every data object, templates included
cemacqr build  --name "…" --city Douala --country CM --mcc 5462 --gui "…"
cemacqr profiles                    # list profiles and what they cannot check
cemacqr tags                        # the EMVCo data object registry
```

Exit codes are part of the contract: `0` valid, `1` invalid, `2` bad invocation.

## What is checked

Against the base EMVCo profile:

- Payload Format Indicator first and equal to `01`; CRC last and matching
- At least one Merchant Account Information object (IDs `02`–`51`)
- The five mandatory root objects: MCC, currency, country, merchant name, city
- Field formats and maximum lengths for every object in the registry
- Amount syntax — `"98"`, `"98."` and `"98.73"` are all legal; `"98,73"` and
  `"3 705"` are not; zero is not
- Tip and convenience-fee consistency: `55=02` requires `56`, `55=03` requires
  `57` in `00.01`–`99.99`, and either without the matching indicator is a violation
- Nested template rules for `62` and `64`, including the `"***"` prompt sentinel
  and the `A`/`M`/`E` characters of the Additional Consumer Data Request
- IDs `65`–`79` are Reserved for Future Use and shall not appear

Against the CEMAC profile, additionally: currency `950` and one of the six member
state codes.

## What is **not** checked, and why that is stated out loud

The CEMAC regulation's technical annex is not public. An outside implementation
therefore cannot know:

- the Globally Unique Identifier allocated to CEMAC participants
- the merchant identifier scheme, if there is one beyond the EMVCo Merchant PAN
- which optional EMVCo objects CEMAC makes mandatory
- whether CEMAC adds a checksum beyond the EMVCo CRC, or merely restates it

So `validate(..., CEMAC)` reports `VALID, SUBJECT TO UNCHECKED RULES` rather than
a bare `True`, and `.fully_checked` is `False`. A validator that returns success
for a payload it only partially examined is worse than no validator.

If you are at GIMAC, the BEAC, or a participant institution and can supply the
annex, the gap closes in one edit — the missing elements are listed in
`cemacqr.CEMAC.undefined`.

## Design notes

**Zero runtime dependencies.** Not minimalism for its own sake. This is code that
sits in front of a payment: it parses attacker-controlled input, and every
dependency is attack surface that the team integrating it did not choose. It uses
`urllib`-free pure standard library and nothing else, verifiable with:

```bash
PYTHONPATH=src python -S -c "import cemacqr; print(cemacqr.__version__)"
```

`-S` removes `site-packages`, so that command can only succeed through
`PYTHONPATH`.

**Lengths count characters, bytes carry the checksum.** The specification counts
Alphanumeric Special characters; its own example is 248 characters but 260 UTF-8
bytes. A byte-counting parser rejects every merchant name outside the Latin
alphabet — which in a six-country union is the ordinary case, not the edge case.

**Nothing is repaired.** A truncated value, a non-numeric ID, a stray character:
each raises with the character offset. A parser that skips what it cannot read
turns a corrupt QR code into a payment.

**Context is not optional.** EMVCo reuses IDs across templates: ID `01` is the
Point of Initiation Method under the root and the Bill Number under `62`. Lookups
take the parent, and there is a test for exactly this.

## Test suite

255 tests, no network, no fixtures on disk. The anchor is the specification's own
Annex B.7 example, transcribed from the hex dump in the document — the only test
vector here that is not something I constructed.

```bash
python -m pytest
```

## Status

Version 0.1.0. The EMVCo layer is complete and tested. The CEMAC-specific layer
is partial by necessity, and says so.

## Sources

- *EMV QR Code Specification for Payment Systems — Merchant-Presented Mode*, v1.1
  (EMVCo, 27 November 2020) — public access at
  <https://www.emvco.com/emv-technologies/qr-codes/>
- *EMV QR Code Specification for Payment Systems — Consumer-Presented Mode*, v1.1
- *Règlement n° 02/26/CEMAC/UMAC/CORENOFI du 8 avril 2026* homologating the norms
  for the QR code, the automated bill of exchange and the direct debit
- BEAC / GIMAC launch of the common QR code, Douala, 29 July 2026

## Licence

Apache-2.0. See [LICENSE](LICENSE).

The EMVCo specifications kept under `docs/reference/` are development references
only. EMVCo permits reproduction "only pursuant to the applicable agreement
between the user and EMVCo", so they are never redistributed — they are excluded
from both the wheel and the sdist.
