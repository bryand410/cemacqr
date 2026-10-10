# Development references — not redistributed

This directory holds the specification material used to write the library. It is
a **development reference only** and is excluded from both the wheel and the
sdist by `pyproject.toml`.

## Why it is excluded

EMVCo's notice on the specifications reads:

> Reproduction, distribution and other use of this document is permitted only
> pursuant to the applicable agreement between the user and EMVCo found at
> www.emvco.com.

So the documents stay here as a reference for anyone working on the code, and
they do not travel with the package. `scripts/check_wheel.py` fails the build if
one of them ever ends up inside an artefact.

## What is here

| File | What it is |
|---|---|
| `EMVCo-Merchant-Presented-QR-Specification-v1.1.pdf` | EMV QRCPS v1.1, Merchant-Presented Mode |
| `EMVCo-Consumer-Presented-QR-Specification-v1.1.pdf` | EMV QRCPS v1.1, Consumer-Presented Mode |
| `emvco-mpm-annex-b7-payload.txt` | The Annex B.7 worked example, decoded from the hex dump in the specification |
| `*.txt` | Plain-text extractions, for grepping |

## How to get them

Both specifications are **public access** at
<https://www.emvco.com/emv-technologies/qr-codes/> (published 27 November 2020),
together with specification bulletins `SB n° 254` and `SB n° 270`. Only the
self-evaluation test cases require a subscription.

## The one that matters most

`emvco-mpm-annex-b7-payload.txt` is the anchor of the test suite. It is 248
characters and 260 UTF-8 bytes, it carries the checksum `A13A`, and it is the
only test vector in this project that I did not construct myself — which makes it
the one that can catch a misreading of the specification rather than a mismatch
with my own assumptions.

It was decoded from the hexadecimal representation the specification prints
alongside the printable payload, precisely so that no transcription error of mine
could enter the test suite.
