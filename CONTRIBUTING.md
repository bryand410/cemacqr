# Contributing

Thanks for looking. This is a small library with a narrow purpose, so the bar for
"is this in scope" is high and the bar for correctness is higher.

## Setting up

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest
```

## Before opening a pull request

```bash
ruff check .
ruff format --check .
python -m pytest
python -m build && python scripts/check_wheel.py dist
```

All four must pass. `ruff` is pinned to a minor series in `pyproject.toml` on
purpose: an unpinned formatter behind a `format --check` gate turns that gate
into a coin flip the moment a release changes its style.

## What is welcome

- **Corrections to the EMVCo rules.** If a rule in `validate.py` does not match
  the specification, that is a bug. Please cite the section number.
- **The CEMAC profile.** If you can supply *Règlement n° 02/26/CEMAC/UMAC/CORENOFI*
  or its technical annex, the four `undefined` elements in `cemacqr.CEMAC` can be
  filled in. This is the single most valuable contribution available.
- **The Consumer-Presented Mode specification.** `cemacqr` implements MPM only.
  CPM is the other half and nobody has written it for this region.
- **Test vectors.** Real payloads from a live deployment, with anything
  identifying a merchant removed, are worth more than anything I can construct.

## What is not

- New runtime dependencies. The zero-dependency property is a security argument,
  not a preference, and the CI job that proves it will reject the change.
- Making the validator lenient. A parser that repairs malformed input turns a
  corrupt QR code into a payment. If something fails to validate and you believe
  it should pass, the bug is in the rule, not in the strictness.
- Returning a bare `True` from validation when a profile has undefined elements.
  The `fully_checked` distinction exists for a reason.

## House style

- Every public function and class has a docstring that says **why**, not what.
  If the reason is "because the specification says so in section X", cite it.
- Tests are named as sentences about behaviour, and the interesting ones carry a
  comment explaining what would break without them.
- No `%`-formatting changes, please — see the note in `pyproject.toml`.

## Commit messages

Imperative, and explain the decision rather than the diff. "Add a rule" is less
useful than "Reject a zero amount, because the specification requires a
non-zero one and a zero renders fine".

## Licence

Contributions are accepted under Apache-2.0.
