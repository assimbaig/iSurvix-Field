# Customer-server package: independent component security review

31 October 2026. Independent Agency Application Security Engineer review of the
frozen customer-package component in `.local/b6`, branch
`feat/customer-server-readiness-20261031`, parent `e832def`. Owner task requires
local/free PDF and OCR work that is still being integrated separately. This is
**not a final security review of that entire integration**.

**Two Medium findings confirmed: CP1 and CP2. Both remain unfixed and require
explicit owner approval before repair. Customer release approval is withheld.**
No real Docker command, account creation, native/paid inference, external network
request or operational data modification occurred during this review.

## Scope and method

Read repository rules, latest handoff and the installed Agency
`security/security-appsec-engineer.md` profile. The lead requested this separate
review after component implementation tests and independent QA, while actual
disposable Docker CI was still pending. The reviewer inspected the installer,
manifest, runtime preparation, Compose private-file mounts, no-overwrite checks
and private-key handling, and authored only private review tests and this report.

Three component source SHA256 values were captured before/after review:
`deploy/customer/customer.py`, `deploy/customer/compose.yaml`, and
`scripts/build_customer_package.py`. No component source was edited. The owner's
rule is explicit: "Do not fix that security review's findings until the owner
approves those fixes." No previous security hold was interpreted as approved.

## CP1 — Medium: interactive owner provisioning skips the local Docker boundary

**Locations:** `deploy/customer/customer.py:109` defines `_docker`, which rejects
a non-Unix `DOCKER_HOST` and inspects the selected context before running ordinary
Docker operations. In contrast, `run_action`'s `create-owner` branch at line 397
calls `subprocess.run` directly at line 402 without that context preflight.

**Independent RED evidence:** two private tests supplied a valid synthetic
prepared runtime/database sentinel, then intercepted every subprocess call:

1. With `DOCKER_HOST=tcp://unrelated-daemon.example.test:2375`, the helper invoked
   the interactive `docker compose ... createsuperuser` command instead of refusing.
2. With no `DOCKER_HOST` but a selected-context probe returning an SSH daemon,
   the helper did not invoke context inspection and proceeded to the interactive
   command instead of refusing.

Both assertions requiring a preflight `ValueError` failed. Independent QA's
earlier `context-boundary-observation.json` records the same bypass. All subprocesses
were replaced by synthetic capture functions; **no daemon was contacted and zero
accounts were created**.

**Impact and prerequisites:** an authorised operator using an inherited remote
Docker environment/context can accidentally run owner provisioning against an
unrelated reachable daemon. If its runtime bind paths resolve there, the action
can create an administrator in an unintended installation. This requires the
operator's Docker access and a valid prepared local package/runtime; it is not an
anonymous web exploit or a demonstrated remote account creation.

**Recommendation:** extract one shared local-Unix-context validator and invoke it
before both captured Docker operations and the interactive owner-creation command.
Reject nonlocal `DOCKER_HOST`/selected contexts before the action. Preserve terminal
inheritance for Django's password prompt; do not capture, log, generate or pass
passwords as command arguments. Add failing-then-passing tests for both environment
and selected-context paths, including a supported local interactive path.

**Disposition:** confirmed, unremediated, pending explicit owner approval.

## CP2 — Medium: tracked private-key files can enter a customer distributable

**Location:** `deploy/customer/customer.py:218` rejects tracked `.local`/`private`
paths, database suffixes, the exact `.env` basename and legacy media. It does not
reject other private-key names/content such as `deployment-signing.key`.

**Independent RED evidence:** a clean disposable Git repository contained the
required installer sources plus `deployment-signing.key`, with a clearly labelled
synthetic `BEGIN PRIVATE KEY` fixture (not a real key). Controlled Docker image
inspection/export responses were supplied. `build_package` returned a complete
`draft-for-review` candidate, exported the synthetic key into its `release/` tree
and inventoried it successfully. The exported bytes exactly matched the tracked
source. The assertion requiring rejection failed.

Private `CP2-observation.json` records `builder_returned_complete_candidate`,
`synthetic_private_key_exported` and `exported_bytes_equal_source` as true, with
`real_private_key_used` and `docker_executed` false.

**Impact and prerequisites:** an accidentally tracked secret under an unblocked
filename can be redistributed to customers even though the builder claims to
exclude private/runtime files. This review establishes a packaging-control gap,
**not an actual project secret leak**. It requires such material to be present in
the clean source selected by an authorised package builder.

**Recommendation:** extend the pre-export/distribution gate to cover private-key
artifacts and credential configuration variants, with a reviewed content-aware
secret scan and explicit handling for legitimate public certificates/synthetic
fixtures. Keep source, Docker and package logs free of secret contents. Retain
reviewed exception evidence rather than claiming a filename denylist proves that
all credentials are absent. Test that a tracked synthetic private key cannot
produce a complete distributable, while approved public assets still package.

**Disposition:** confirmed, unremediated, pending explicit owner approval.

## Executed results

Using process-local `PYTHONPATH=.local/customer-server-20261031/security`:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py customer_security --verbosity 2
```

**7 tests run in 1.749 seconds: 4 passed, 3 failed, 0 errors, 0 skips.** The three
failures are the intentionally failing security-boundary tests establishing CP1
(two cases) and CP2 (one case). They were not skipped, weakened or fixed.

The four passing controls verified:

- Ordinary `_docker` operations reject an explicitly remote host before subprocess.
- Corrupt package inventory prevents owner provisioning and preserves DB sentinel.
- Supplied external TLS/private secret bytes are not copied into package/runtime.
- An existing runtime database cannot be reinitialized or overwritten.

A focused repeat of the CP2 case captured the exact exported-file observation:
**1 test, 1 expected failure in 1.359 seconds**. This is the same test, not another
unique test or a passing gate. Both runs recorded zero external network attempts
and zero fixture HTTP connections. The only actual subprocesses in the CP2 fixture
were bounded Git commands in its disposable synthetic repository; Docker remained
controlled throughout.

Private evidence directory: `.local/customer-server-20261031/security/`:
`customer_security.py`, `boundary-red.log`, `CP2-evidence-red.log`,
`CP2-observation.json`, `receipt.json`, and before/after source inventories.

## Limits and release disposition

- Actual Linux image build, clean install, permissions, Docker networking,
  second-device LAN/browser acceptance and target-server recovery are not proved
  by this review. The separate disposable CI and owner target gates must be
  evaluated against their actual results.
- The runtime preserves supplied key bytes outside the distribution and rejects
  missing/replaced manifest/configuration files in tested paths. Real certificate
  validity, Linux key ownership and readable mounts were not verified on this PC.
- Manifest SHA256 supports integrity checking against an independently trusted
  digest, not authenticity if an attacker can replace both the package and digest.
  Only trusted reviewed package code should execute.
- The local/free PDF/OCR integration, dependency licensing and final assembled
  release require their own completed verification and subsequent security review.
- Earlier A12/BR1/D1/D2/L1/CS1/CS2/AI1 holds remain unchanged. CP1/CP2 add to the
  approval queue; neither is implicitly approved by unrelated implementation work.

No merge, production/customer deployment, security repair or service change was
performed by this reviewer. A full release cannot be declared secure or complete
on the basis of these component tests.
