"""The command line interface, including its exit codes."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from cemacqr.__main__ import main

from .conftest import SPEC_PAYLOAD, SPEC_PAYLOAD_BAD_CRC


class TestCrcCommand:
    def test_a_matching_checksum_exits_zero(self, capsys):
        assert main(["crc", SPEC_PAYLOAD]) == 0
        assert "match" in capsys.readouterr().out

    def test_a_mismatch_exits_one(self, capsys):
        assert main(["crc", SPEC_PAYLOAD_BAD_CRC]) == 1
        assert "MISMATCH" in capsys.readouterr().out

    def test_a_mismatch_explains_the_crc_trap(self, capsys):
        main(["crc", SPEC_PAYLOAD_BAD_CRC])
        out = capsys.readouterr().out
        assert "0x1021" in out
        assert "not CRC-32" in out

    def test_a_payload_without_a_crc_exits_one(self, capsys):
        assert main(["crc", SPEC_PAYLOAD[:-8]]) == 1
        assert "no CRC object" in capsys.readouterr().out


class TestCheckCommand:
    def test_the_specification_example_passes(self, capsys):
        assert main(["check", SPEC_PAYLOAD]) == 0
        assert "VALID" in capsys.readouterr().out

    def test_a_broken_checksum_fails(self, capsys):
        assert main(["check", SPEC_PAYLOAD_BAD_CRC]) == 1
        assert "CRC_MISMATCH" in capsys.readouterr().out

    def test_json_output(self, capsys):
        main(["check", SPEC_PAYLOAD, "--json"])
        document = json.loads(capsys.readouterr().out)
        assert document["ok"] is True
        assert document["profile"] == "emvco"

    def test_the_cemac_profile_reports_unchecked_rules(self, capsys):
        assert main(["check", SPEC_PAYLOAD, "--profile", "cemac"]) == 1
        out = capsys.readouterr().out
        assert "PROFILE_COUNTRY" in out
        assert "NOT CHECKED" in out

    def test_an_unknown_profile_exits_one(self, capsys):
        assert main(["check", SPEC_PAYLOAD, "--profile", "nope"]) == 1
        assert "unknown profile" in capsys.readouterr().err


class TestParseCommand:
    def test_it_prints_the_objects(self, capsys):
        assert main(["parse", SPEC_PAYLOAD]) == 0
        out = capsys.readouterr().out
        assert "BEST TRANSPORT" in out
        assert "Merchant Name" in out

    def test_expand_decodes_templates(self, capsys):
        main(["parse", SPEC_PAYLOAD, "--expand"])
        assert "A6008667" in capsys.readouterr().out

    def test_json_output_is_machine_readable(self, capsys):
        main(["parse", SPEC_PAYLOAD, "--json"])
        document = json.loads(capsys.readouterr().out)
        assert document["crc_ok"] is True
        assert document["crc_computed"] == "A13A"
        assert len(document["objects"]) == 15

    def test_json_preserves_non_ascii(self, capsys):
        main(["parse", SPEC_PAYLOAD, "--json"])
        assert "\u6700\u4f73\u8fd0\u8f93" in capsys.readouterr().out


class TestBuildCommand:
    def test_it_produces_a_valid_payload(self, capsys):
        code = main(
            [
                "build",
                "--name",
                "BOULANGERIE AKWA",
                "--city",
                "Douala",
                "--country",
                "CM",
                "--mcc",
                "5462",
                "--gui",
                "com.example.cemac",
            ]
        )
        assert code == 0
        payload = capsys.readouterr().out.strip().splitlines()[0]
        assert main(["check", payload]) == 0

    def test_the_placeholder_gui_is_flagged_on_stderr(self, capsys):
        main(
            [
                "build",
                "--name",
                "X",
                "--city",
                "Douala",
                "--country",
                "CM",
                "--mcc",
                "5411",
                "--gui",
                "com.example.cemac",
            ]
        )
        assert "placeholder" in capsys.readouterr().err

    def test_the_default_currency_is_the_franc(self, capsys):
        main(
            [
                "build",
                "--name",
                "X",
                "--city",
                "Douala",
                "--country",
                "CM",
                "--mcc",
                "5411",
                "--gui",
                "com.example.cemac",
                "--json",
            ]
        )
        document = json.loads(capsys.readouterr().out)
        assert "5303950" in document["payload"]


class TestDiscoveryCommands:
    def test_profiles_lists_the_cemac_gaps(self, capsys):
        assert main(["profiles"]) == 0
        out = capsys.readouterr().out
        assert "cemac" in out
        assert "NOT DEFINED" in out

    def test_tags_lists_the_registry(self, capsys):
        assert main(["tags"]) == 0
        out = capsys.readouterr().out
        assert "Merchant Category Code" in out
        assert "Bill Number" in out


class TestInvocation:
    def test_no_command_prints_help_and_exits_two(self, capsys):
        assert main([]) == 2
        assert "usage" in capsys.readouterr().out.lower()

    def test_a_malformed_payload_exits_one(self, capsys):
        assert main(["parse", "000201zz"]) == 1
        assert "error" in capsys.readouterr().err

    def test_an_unreadable_file_exits_two(self, capsys):
        assert main(["parse", "--file", "/nonexistent/path/qr.txt"]) == 2
        assert "error" in capsys.readouterr().err

    def test_reading_from_a_file(self, tmp_path, capsys):
        path = tmp_path / "qr.txt"
        path.write_text(SPEC_PAYLOAD, encoding="utf-8")
        assert main(["check", "--file", str(path)]) == 0

    def test_version(self):
        with pytest.raises(SystemExit) as caught:
            main(["--version"])
        assert caught.value.code == 0


class TestAsAModule:
    def test_python_dash_m_works(self, tmp_path):
        # The console script is generated by the packaging metadata; this checks
        # the module entry point independently of it, with the package reachable
        # only through PYTHONPATH — so a missing __main__ is the failure, not a
        # stray installation.
        import os

        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
        result = subprocess.run(
            [sys.executable, "-m", "cemacqr", "crc", SPEC_PAYLOAD],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        assert "match" in result.stdout
