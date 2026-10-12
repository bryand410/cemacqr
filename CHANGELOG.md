# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] — 2026-10-12

Packaging metadata only. No API change.

### Fixed

- The licence is now declared as the SPDX expression `Apache-2.0` (PEP 639)
  instead of `license = { file = "LICENSE" }`. The old form copied the entire
  Apache text into the `License` metadata field, so PyPI rendered that wall of
  text on the project page rather than naming the licence. The metadata now
  carries `License-Expression: Apache-2.0`, and `license-files` still ships the
  full text inside the distribution.
- The now-redundant `License :: OSI Approved :: Apache Software License`
  classifier was removed, since PEP 639 treats it as a second, weaker statement
  of the same fact.

## [0.1.1] — 2026-10-10

The CEMAC layer, after reading the CORENOFI norm.

### Added

- `cemacqr.tags.ADDITIONAL_DATA_FIELD_CEMAC` and
  `cemacqr.tags.CEMAC_PAYMENT_SYSTEM_DATA` — the CEMAC overlay on the Additional
  Data Field Template, transcribed from the CORENOFI norm v2.1, Tableau 15 and
  Tableau 18-B. ID `50` is mandatory and is itself a template; IDs `51`–`80` are
  reserved for the CEMAC regional scheme; IDs `6251` and `6252`, present in the
  pre-homologation draft, were deleted.
- `tags.resolve(parent, tag, scheme=…)` — the overlay is now a parameter rather
  than a second registry, because the two differ only inside template `62`.
- `MerchantQr.cemac_data(...)` — builds the nested ID `50`, which
  `.additional()` could not express because it takes a flat string.
- `scripts/check_corenofi_example.py` — recomputes the checksum published with the
  norm's own worked example.
- `tests/test_corenofi_example.py` — 13 tests pinning that example: its fields,
  its checksum, and the fact that it fails the norm's own currency rule.

### Changed

- `validate(payload, CEMAC)` now requires the CEMAC payment system data object
  (ID `50`) inside template `62`, and reports `CEMAC_DATA_MISSING` without it.
  A payload built by `MerchantQr` without `.cemac_data(...)` is therefore valid
  EMVCo and **not** a valid CEMAC QR code — which is the correct answer, and a
  behaviour change.
- New violations inside ID `50`: `CEMAC_DATA_MALFORMED` and
  `CEMAC_DATA_UNKNOWN_OBJECT`.
- `CEMAC.undefined` reduced from four elements to two. The four previously
  unknown items are settled: the mandatory subset is ID `50`; the checksum is
  EMVCo's, restated and not extended; and the merchant identifier scheme is the
  participant alias defined in Annex 3. What remains is the Globally Unique
  Identifier, because the norm states two different values for it, and whether
  the homologated text differs from v2.1.
- `CEMAC.legal_basis` now cites the norm as well as the regulation.

### Verified

The checksum published in the CORENOFI norm's Annex 4 (`3FD3`) is reproduced by
`crc16_hex`. This is a primary-source confirmation of the library's central claim
and, incidentally, of the fact that the CRC-32 announced in several published
descriptions of this QR code is wrong.

## [0.1.0] — 2026-10-10

First release.

### Added

- `crc16` / `crc16_hex` — the EMV QRCPS checksum: polynomial `0x1021`, initial
  value `0xFFFF`, rendered as four uppercase hexadecimal characters. Verified
  against the specification's Annex B.7 example (`A13A`), with a test asserting
  that CRC-32 gives a different value, because several published descriptions of
  the CEMAC QR code announce a CRC-32.
- `tlv` — strict Tag-Length-Value parsing and encoding, counting **characters**
  rather than bytes, with the offset of any malformation reported.
- `EmvQr` — parsing, field access, template access, checksum verification and
  byte-for-byte round-tripping of a merchant-presented payload.
- `MerchantQr` — a builder that refuses a currency given as `"XAF"`, an amount
  with a comma, a zero amount, a country code that is not two letters, and any
  payload missing a mandatory object, each at the point of the call.
- `validate` — the EMVCo rules plus profile constraints, returning every
  violation rather than the first, and distinguishing "valid" from "fully
  checked".
- `Profile` / `EMVCO` / `CEMAC` — national profiles as data. The CEMAC profile
  enforces the currency (`950`) and the six member state codes, and declares the
  four elements it cannot state because the regulation's technical annex is not
  public.
- CLI: `crc`, `check`, `parse`, `build`, `profiles`, `tags`, with documented exit
  codes.
- 255 tests, zero runtime dependencies, CI on Python 3.9–3.13.

[0.1.0]: https://github.com/bryand410/cemacqr/releases/tag/v0.1.0
