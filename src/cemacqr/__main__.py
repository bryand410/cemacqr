"""Command line interface: ``python -m cemacqr`` or ``cemacqr``.

Exit codes are part of the contract, because the useful way to run this is in a
build pipeline or a merchant onboarding script:

==== ==========================================================
0    the payload is valid
1    the payload is invalid, or the checksum does not match
2    the invocation was wrong (bad option, unreadable file)
==== ==========================================================
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import __version__
from .crc import crc16_hex
from .errors import CemacQrError
from .payload import parse_payload
from .profile import PROFILES, get_profile
from .tags import ROOT, merchant_account_info_owner
from .tlv import parse as parse_tlv
from .validate import validate

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_USAGE = 2


def _read_payload(args: argparse.Namespace) -> str:
    """Payload from the argument, from ``--file``, or from standard input."""
    if getattr(args, "payload", None):
        return args.payload
    if getattr(args, "file", None):
        with open(args.file, encoding="utf-8") as handle:
            return handle.read().strip()
    data = sys.stdin.read().strip()
    if not data:
        raise SystemExit("error: no payload given (pass it as an argument, with --file, or on stdin)")
    return data


# -- commands -------------------------------------------------------------


def cmd_parse(args: argparse.Namespace) -> int:
    payload = _read_payload(args)
    qr = parse_payload(payload)

    if args.json:
        print(
            json.dumps(
                {
                    "payload": qr.to_string(),
                    "objects": [{"id": item.tag, "value": item.value} for item in qr.objects],
                    "crc_stated": qr.stated_crc,
                    "crc_computed": qr.computed_crc,
                    "crc_ok": qr.crc_ok,
                    "merchant_accounts": qr.merchant_accounts,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return EXIT_OK

    print("payload        %s" % qr.to_string())
    print("objects        %d" % len(qr.objects))
    print()
    for item in qr.objects:
        spec = ROOT.get(item.tag)
        if spec is not None:
            label = spec.name
        elif item.tag.isdigit() and 2 <= int(item.tag) <= 51:
            owner = merchant_account_info_owner(item.tag)
            label = "Merchant Account Information (%s)" % owner
        else:
            label = "unknown"
        print("  ID %s  %-46s %s" % (item.tag, label, item.value))
        if args.expand:
            for child in item.children():
                print("        └ ID %s  %s" % (child.tag, child.value))

    print()
    for name, value in (
        ("Payload Format Indicator", qr.payload_format_indicator),
        ("Point of Initiation", "static (reusable)" if qr.is_static else "dynamic (single use)")
        if qr.is_static is not None
        else None,
        ("Merchant Category Code", qr.merchant_category_code),
        ("Transaction Currency", qr.currency),
        ("Transaction Amount", qr.amount),
        ("Country Code", qr.country_code),
        ("Merchant Name", qr.merchant_name),
        ("Merchant City", qr.merchant_city),
    ):
        if value is not None:
            print("  %-24s %s" % (name, value))
    return EXIT_OK


def cmd_crc(args: argparse.Namespace) -> int:
    """The headline command: recompute the checksum and compare."""
    payload = _read_payload(args)

    marker = None
    for item in parse_tlv(payload):
        if item.tag == "63":
            marker = len(payload) - len(item.value)
    if marker is None:
        print("no CRC object (ID 63) in the payload")
        return EXIT_INVALID

    computed = crc16_hex(payload[:marker].encode("utf-8"))
    stated = payload[marker : marker + 4]

    print("checksum covered %d characters (%d bytes)" % (marker, len(payload[:marker].encode("utf-8"))))
    print("stated   %s" % stated)
    print("computed %s" % computed)
    if stated.upper() == computed:
        print("match")
        return EXIT_OK

    print()
    print("MISMATCH.")
    print("EMV QRCPS v1.1 section 4.7.3.1 requires a 16-bit checksum: polynomial 0x1021,")
    print("initial value 0xFFFF, four hexadecimal characters. It is not CRC-32, and the")
    print("two produce unrelated values.")
    return EXIT_INVALID


def cmd_check(args: argparse.Namespace) -> int:
    payload = _read_payload(args)
    qr = parse_payload(payload)
    profile = get_profile(args.profile)
    report = validate(qr, profile)

    if args.json:
        print(
            json.dumps(
                {
                    "status": report.status,
                    "ok": report.ok,
                    "fully_checked": report.fully_checked,
                    "profile": profile.name,
                    "violations": [
                        {"code": item.code, "tag": item.tag, "message": item.message} for item in report.violations
                    ],
                    "unchecked": report.unchecked,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(report)

    return EXIT_OK if report.ok else EXIT_INVALID


def cmd_profiles(args: argparse.Namespace) -> int:
    for name, profile in sorted(PROFILES.items()):
        print("%s — %s" % (name, profile.title))
        if profile.legal_basis:
            print("  legal basis: %s" % profile.legal_basis)
        if profile.currencies:
            print("  currencies : %s" % ", ".join(profile.currencies))
        if profile.countries:
            print("  countries  : %s" % ", ".join(profile.countries))
        if profile.undefined:
            print("  NOT DEFINED IN THIS PROFILE (%d):" % len(profile.undefined))
            for item in profile.undefined:
                print("    - %s" % item)
        print()
    return EXIT_OK


def cmd_tags(args: argparse.Namespace) -> int:
    from . import tags as registry

    groups = [
        ("root (EMV QRCPS v1.1, Table 3.3)", registry.ROOT),
        ("Additional Data Field Template, ID 62 (Table 3.7)", registry.ADDITIONAL_DATA_FIELD),
        ("Merchant Information—Language Template, ID 64 (Table 3.8)", registry.LANGUAGE_TEMPLATE),
        ("Merchant Account Information template, IDs 26-51 (Table 4.2)", registry.MERCHANT_ACCOUNT_INFO),
    ]
    for title, table in groups:
        print(title)
        for tag, spec in sorted(table.items()):
            print("  %s  %-46s %-4s max %-3d %s" % (tag, spec.name, spec.format, spec.max_length, spec.presence))
        print()
    return EXIT_OK


def cmd_build(args: argparse.Namespace) -> int:
    from .builder import MerchantQr

    builder = (
        MerchantQr()
        .merchant(name=args.name, city=args.city, country=args.country, postal_code=args.postal_code)
        .category(args.mcc)
        .currency(args.currency)
    )
    if args.amount is not None:
        builder.amount(args.amount)
    if args.reusable:
        builder.reusable(True)
    if args.bill:
        builder.bill_number(args.bill)
    if args.reference:
        builder.reference(args.reference)
    if args.alternate_language:
        builder.alternate_language(language=args.alternate_language, merchant_name=args.name)

    builder.account(args.account_id, gui=args.gui, merchant_pan=args.merchant_pan)

    qr = builder.build()
    if args.json:
        print(json.dumps({"payload": qr.to_string(), "crc": qr.stated_crc}, ensure_ascii=False))
    else:
        print(qr.to_string())
        if args.gui.startswith("com.example"):
            print()
            print("note: the GUI is a placeholder. CEMAC has not published the identifier it", file=sys.stderr)
            print("      allocates to participants, so this payload is valid EMVCo and will not", file=sys.stderr)
            print("      be accepted by a participant institution until that value is known.", file=sys.stderr)
    return EXIT_OK


# -- parser ---------------------------------------------------------------


def _add_payload_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("payload", nargs="?", help="the payload string")
    parser.add_argument("--file", help="read the payload from a file instead")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cemacqr",
        description="Build, read and check the CEMAC common QR code (EMV QRCPS v1.1).",
    )
    parser.add_argument("--version", action="version", version="cemacqr %s" % __version__)
    sub = parser.add_subparsers(dest="command")

    p_parse = sub.add_parser("parse", help="decode a payload into its data objects")
    _add_payload_source(p_parse)
    p_parse.add_argument("--expand", action="store_true", help="also decode nested templates")
    p_parse.add_argument("--json", action="store_true", help="emit JSON")
    p_parse.set_defaults(func=cmd_parse)

    p_crc = sub.add_parser("crc", help="recompute the checksum and compare it")
    _add_payload_source(p_crc)
    p_crc.set_defaults(func=cmd_crc)

    p_check = sub.add_parser("check", help="validate a payload")
    _add_payload_source(p_check)
    p_check.add_argument("--profile", default="emvco", help="profile to validate against (default: emvco)")
    p_check.add_argument("--json", action="store_true", help="emit JSON")
    p_check.set_defaults(func=cmd_check)

    sub.add_parser("profiles", help="list the known profiles and what they cannot check").set_defaults(
        func=cmd_profiles
    )

    sub.add_parser("tags", help="list the EMVCo data object registry").set_defaults(func=cmd_tags)

    p_build = sub.add_parser("build", help="assemble a payload")
    p_build.add_argument("--name", required=True, help="Merchant Name (59)")
    p_build.add_argument("--city", required=True, help="Merchant City (60)")
    p_build.add_argument("--country", required=True, help="Country Code (58), ISO 3166-1 alpha-2")
    p_build.add_argument("--postal-code", help="Postal Code (61)")
    p_build.add_argument("--mcc", required=True, help="Merchant Category Code (52)")
    p_build.add_argument("--currency", default="950", help="ISO 4217 numeric code (default: 950, the CFA franc)")
    p_build.add_argument("--amount", help="Transaction Amount (54); omit for a reusable code")
    p_build.add_argument("--reusable", action="store_true", help="mark the code reusable (01 = 11)")
    p_build.add_argument("--bill", help="Bill Number (ID 01 under 62)")
    p_build.add_argument("--reference", help="Reference Label (ID 05 under 62)")
    p_build.add_argument("--alternate-language", help="add template 64 with this ISO 639 language")
    p_build.add_argument("--account-id", default="26", help="Merchant Account Information ID (26-51)")
    p_build.add_argument("--gui", required=True, help="Globally Unique Identifier")
    p_build.add_argument("--merchant-pan", help="Merchant PAN (ID 01 in the account template)")
    p_build.add_argument("--json", action="store_true", help="emit JSON")
    p_build.set_defaults(func=cmd_build)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        return args.func(args)
    except CemacQrError as error:
        print("error: %s" % error, file=sys.stderr)
        return EXIT_INVALID
    except (OSError, ValueError) as error:
        print("error: %s" % error, file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
