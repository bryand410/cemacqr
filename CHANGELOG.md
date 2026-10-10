# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
