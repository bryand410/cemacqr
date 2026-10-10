"""Shared fixtures.

The payload in :data:`SPEC_PAYLOAD` is transcribed from EMV QRCPS v1.1,
Annex B.7 — the specification's own worked example, checksum included. It is the
only test vector in this suite that is not something I constructed, which makes
it the one that can catch a misreading of the specification rather than a
mismatch with my own assumptions.
"""

from __future__ import annotations

import pytest

from cemacqr import MerchantQr

#: EMV QRCPS v1.1 Annex B.7, verbatim, 244 characters.
SPEC_PAYLOAD = (
    "00020101021229300012D156000000000510A93FO3230Q31280012D15600000001030812345678"
    "520441115802CN5914BEST TRANSPORT6007BEIJING64200002ZH0104\u6700\u4f73\u8fd0\u8f93"
    "0202\u5317\u4eac540523.7253031565502016233030412340603***0708A60086670902ME"
    "91320016A0112233449988770708123456786304A13A"
)

#: The same payload with the checksum replaced by one that does not match.
SPEC_PAYLOAD_BAD_CRC = SPEC_PAYLOAD[:-4] + "0000"


@pytest.fixture
def spec_payload() -> str:
    return SPEC_PAYLOAD


@pytest.fixture
def cemac_qr() -> MerchantQr:
    """A plausible CEMAC merchant: Douala bakery, CFA franc, reusable code.

    It carries the CEMAC payment system data object (ID 50), because the
    CORENOFI norm makes it mandatory — a payload without it is well-formed
    EMVCo and not a CEMAC QR code.
    """
    return (
        MerchantQr()
        .merchant(name="BOULANGERIE AKWA", city="Douala", country="CM")
        .category("5462")
        .currency("950")
        .reusable(True)
        .account("26", gui="com.example.cemac", merchant_pan="2376000000001")
        .cemac_data(member="31003", account_alias="10790001", notify="https://akwa.cm/pmt/t01")
    )
