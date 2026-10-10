# Security policy

## What this library does with untrusted input

`cemacqr` parses strings that a payment terminal read off a camera. Treat every
payload as attacker-controlled.

The parser is written for that: it is strict, it does not repair, and it reports
the character offset of any malformation rather than guessing. There is no
`eval`, no regular-expression backtracking risk on unbounded input, no
deserialisation, no network access, and no filesystem access outside the CLI's
explicit `--file` option.

## Zero runtime dependencies

Not a stylistic preference. A library that sits in front of a payment and pulls a
dependency tree imports the attack surface of every package in it — and that is
precisely the vector the team integrating it spends its time defending against.
`event-stream`, `ua-parser-js` and `xz-utils` were each compromised in a package
nobody chose directly.

You can verify the claim:

```bash
PYTHONPATH=src python -S -c "import cemacqr; print(cemacqr.__version__)"
```

`-S` removes `site-packages` from the import path, so the command can only
succeed through `PYTHONPATH`. If anything third-party were imported, it fails.

## Reporting a vulnerability

Open a [security advisory](https://github.com/bryand410/cemacqr/security/advisories/new),
or email the maintainer. Please include the payload that triggers the issue and
the expected versus actual behaviour.

**A note on what counts.** Because this library validates QR payloads, a bug that
makes it *accept* an invalid payload is a security issue, not a correctness one —
it means a code reaches a payment rail that should have been stopped. A bug that
makes it *reject* a valid payload is a correctness issue and is handled in the
normal issue tracker.

## Scope

In scope: the parser, the checksum implementation, the validator, the CLI, and
anything that causes a payload to be accepted that should be rejected.

Out of scope: the accuracy of the CEMAC-specific rules, which are incomplete by
necessity — see the README. If you can supply the regulation's technical annex,
that is a contribution rather than a vulnerability report.

## Supported versions

The latest released minor version. This is a 0.x library; there is no backport
policy yet.
