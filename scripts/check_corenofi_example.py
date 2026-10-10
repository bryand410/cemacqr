"""Verify the library against the worked example of the CORENOFI norm.

Source
------
*Spécifications du QR code pour l'acceptation des paiements interopérables dans
la Communauté économique et monétaire des États de l'Afrique centrale (CEMAC)*,
CORENOFI, version 2.1, March 2025, Annex 4 ("Exemple de QR code de la CEMAC
(MPM)"), page 59. The norm carries the mention "NORME A VALIDER PAR LE COMITE DU
CORENOFI" and is the text later homologated by Règlement n°
02/26/CEMAC/UMAC/CORENOFI of 8 April 2026.

What this proves
----------------
The example ends with the clear-text value of a merchant-presented QR code,
checksum included. Recomputing that checksum with :func:`cemacqr.crc16_hex`
reproduces the published value, so the library agrees with the CEMAC's own
reference document -- not merely with EMVCo.

It also settles a disagreement in the norm itself. Tableau 5 annotates the
merchant account template as ``ID=51 (CEMAC) Longueur totale=36``, and Tableau 17
shows the global unique identifier as ``0014 A0000006561010``. The example string
actually carries ``0236`` and ``0012 A15600000000``. The published checksum
decides between them: only the string reproduces it, so the tables are the ones
that drifted.

Run it with the package on the path::

    PYTHONPATH=src python scripts/check_corenofi_example.py
"""

from __future__ import annotations

import sys

from cemacqr import crc16_hex, parse_payload

# Reproduced without the line-break artefacts of the PDF text layer. The
# checksum's own id and length ("6304") are covered by it, so they are part of
# this prefix.
PREFIX = (
    "000201"
    "010212"
    "0236"
    "0012A15600000000"
    "01161245825993000001"
    "52045462"
    "5303952"
    "540507550"
    "5802CG"
    "5921BOULANGERIE PAIN D OR"
    "6011BRAZZAVILLE"
    "6297"
    "030811650284"
    "070817654001"
    "5069"
    "0014A0000006561010"
    "010531003"
    "020810790001"
    "0326https://paindor.cg/pmt/t01"
    "6304"
)

STATED_CRC = "3FD3"
EXPECTED = PREFIX + STATED_CRC


def main() -> int:
    computed = crc16_hex(PREFIX.encode("utf-8"))
    print(f"prefix        : {len(PREFIX)} characters, {len(PREFIX.encode('utf-8'))} bytes")
    print(f"computed CRC  : {computed}")
    print(f"published CRC : {STATED_CRC}")
    if computed != STATED_CRC:
        print("RESULT        : MISMATCH")
        return 1
    print("RESULT        : the published checksum is reproduced")

    payload = parse_payload(EXPECTED)
    print(f"crc_ok        : {payload.crc_ok}")
    print(f"point of init : {payload.point_of_initiation} (12 = dynamic)")
    print(f"merchant      : {payload.merchant_name!r}, {payload.merchant_city!r}")
    print(f"country       : {payload.country_code}")
    print(f"currency      : {payload.currency}")
    print(f"amount        : {payload.amount_decimal}")
    print(f"category      : {payload.merchant_category_code} (5462 = bakeries)")
    for tag, children in payload.merchant_accounts.items():
        print(f"account {tag}     : {children}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
