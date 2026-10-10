#!/usr/bin/env python3
"""Inspect a built distribution and fail on anything that should not ship.

Run after ``python -m build``::

    python scripts/check_wheel.py dist

The checks are the ones a human would otherwise have to remember, and each one
guards a mistake that has actually been made in a payments library somewhere:

* the EMVCo specifications must not be redistributed — EMVCo permits
  reproduction only under its own agreement, so a copy inside the wheel is a
  licence problem, not just a size problem;
* the package must import with no third-party code available;
* the console script must be declared, or ``pip install cemacqr`` gives you a
  library and no command.
"""

from __future__ import annotations

import glob
import os
import subprocess
import sys
import tarfile
import zipfile

FORBIDDEN = (
    "docs/reference",
    "EMVCo-",
    "emvco-mpm",
)

REQUIRED_IN_WHEEL = (
    "cemacqr/__init__.py",
    "cemacqr/crc.py",
    "cemacqr/payload.py",
    "cemacqr/validate.py",
)


def fail(message: str) -> None:
    print("FAIL  %s" % message)
    sys.exit(1)


def ok(message: str) -> None:
    print("ok    %s" % message)


def check_wheel(path: str) -> None:
    print("wheel %s" % os.path.basename(path))
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()

        for bad in FORBIDDEN:
            if any(bad in name for name in names):
                fail("the wheel contains %r, which must not be redistributed" % bad)
        ok("no EMVCo specification inside the wheel")

        for required in REQUIRED_IN_WHEEL:
            if not any(name.endswith(required) for name in names):
                fail("the wheel is missing %s" % required)
        ok("every module is present")

        metadata_name = [n for n in names if n.endswith("METADATA")]
        if not metadata_name:
            fail("the wheel has no METADATA")
        metadata = archive.read(metadata_name[0]).decode("utf-8")

        requires = [line for line in metadata.splitlines() if line.startswith("Requires-Dist")]
        runtime = [line for line in requires if "extra ==" not in line]
        if runtime:
            fail("runtime dependencies declared: %s" % runtime)
        ok("no runtime dependencies (%d optional extras)" % len(requires))

        entry_points = [n for n in names if n.endswith("entry_points.txt")]
        if not entry_points:
            fail("no entry_points.txt, so no console script")
        if "cemacqr" not in archive.read(entry_points[0]).decode("utf-8"):
            fail("the entry point does not declare the cemacqr console script")
        ok("the console script is declared")

        if not any(n.endswith("py.typed") for n in names):
            print("warn  no py.typed marker, so the type hints are not exported")

    # A wheel that cannot be imported is not a wheel.
    import tempfile

    with tempfile.TemporaryDirectory() as workspace:
        with zipfile.ZipFile(path) as archive:
            archive.extractall(workspace)
        result = subprocess.run(
            [sys.executable, "-S", "-c", "import cemacqr; print(cemacqr.__version__)"],
            capture_output=True,
            text=True,
            cwd=workspace,
            env={**os.environ, "PYTHONPATH": workspace},
        )
        if result.returncode != 0:
            fail("the extracted wheel does not import with -S: %s" % result.stderr.strip())
        ok("imports with site-packages removed, version %s" % result.stdout.strip())


def check_sdist(path: str) -> None:
    print("sdist %s" % os.path.basename(path))
    with tarfile.open(path) as archive:
        names = archive.getnames()

    for bad in FORBIDDEN:
        if any(bad in name for name in names):
            fail("the sdist contains %r, which must not be redistributed" % bad)
    ok("no EMVCo specification inside the sdist")

    if not any(name.endswith("tests/test_crc.py") for name in names):
        fail("the sdist has no tests")
    ok("the tests are included")


def main(argv: list) -> int:
    directory = argv[1] if len(argv) > 1 else "dist"
    wheels = glob.glob(os.path.join(directory, "*.whl"))
    sdists = glob.glob(os.path.join(directory, "*.tar.gz"))

    if not wheels or not sdists:
        fail("expected both a wheel and an sdist in %r, found %d and %d" % (directory, len(wheels), len(sdists)))

    for wheel in wheels:
        check_wheel(wheel)
    for sdist in sdists:
        check_sdist(sdist)

    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
