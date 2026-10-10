"""cemacqr — build, read and check the CEMAC common QR code.

The QR Code communautaire de la CEMAC was homologated by *Règlement
n° 02/26/CEMAC/UMAC/CORENOFI du 8 avril 2026* and launched in Douala on
29 July 2026. It is built on **EMV QRCPS v1.1** and **ISO/IEC 18004**, encoded as
TLV, and routed by GIMAC across the six member states. The BEAC's stated target
is 120,000 codes deployed by 2027, and every bank, microfinance institution,
payment institution and electronic-money issuer in the union must be able to
generate and read them.

This library implements the public half of that stack. No dependency, no
registration, no permission to ask for.

Quick start
-----------

>>> from cemacqr import parse_payload
>>> qr = parse_payload(
...     "00020101021229300012D156000000000510A93FO3230Q31280012D15600000001030812"
...     "345678520441115802CN5914BEST TRANSPORT6007BEIJING64200002ZH0104\u6700\u4f73\u8fd0\u8f93"
...     "0202\u5317\u4eac540523.7253031565502016233030412340603***0708A60086670902ME"
...     "91320016A0112233449988770708123456786304A13A"
... )
>>> qr.merchant_name
'BEST TRANSPORT'
>>> qr.crc_ok
True

The one thing to know before anything else
------------------------------------------

The checksum is a **16-bit** CRC — polynomial ``0x1021``, initial value
``0xFFFF`` — rendered as four hexadecimal characters. It is not CRC-32. Several
published descriptions of the CEMAC QR code say CRC-32, and an implementation
built from those descriptions will produce codes that no reader accepts. See
:mod:`cemacqr.crc`.
"""

from __future__ import annotations

from .builder import MerchantQr
from .crc import CRC_INITIAL, CRC_POLYNOMIAL, crc16, crc16_hex
from .errors import (
    CemacQrError,
    ProfileIncomplete,
    QrSyntaxError,
    QrValidationError,
    UnsupportedProfile,
)
from .payload import EmvQr, build, parse_payload
from .profile import CEMAC, CEMAC_COUNTRIES, CEMAC_CURRENCY, EMVCO, Profile, get_profile
from .tags import TagSpec, resolve
from .tlv import Tlv, encode, parse_tlv
from .validate import ValidationReport, Violation, prompt_requested, validate

__version__ = "0.1.1"

__all__ = [
    "__version__",
    # payload
    "EmvQr",
    "parse_payload",
    "build",
    # builder
    "MerchantQr",
    # checksum
    "crc16",
    "crc16_hex",
    "CRC_POLYNOMIAL",
    "CRC_INITIAL",
    # tlv
    "Tlv",
    "encode",
    "parse_tlv",
    # tags
    "TagSpec",
    "resolve",
    # profiles
    "Profile",
    "EMVCO",
    "CEMAC",
    "CEMAC_CURRENCY",
    "CEMAC_COUNTRIES",
    "get_profile",
    # validation
    "validate",
    "ValidationReport",
    "Violation",
    "prompt_requested",
    # errors
    "CemacQrError",
    "QrSyntaxError",
    "QrValidationError",
    "ProfileIncomplete",
    "UnsupportedProfile",
]
