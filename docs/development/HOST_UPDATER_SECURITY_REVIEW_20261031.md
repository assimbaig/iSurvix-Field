# Privileged customer updater: separate post-functional security review

31 October 2026. Independent Agency Application Security Engineer, `.local/b6`,
branch `feat/customer-server-readiness-20261031`. Review began after explicit
functional freeze of the proxy-readiness and pre-ACK cancellation repairs.

**UP1 Low was confirmed, then explicitly approved for repair by the owner. The
final re-review below verifies that repair in the executed boundaries. Original
RED evidence remains preserved.** In the initial review, nine private cases ran:
eight passed and one meaningful security assertion failed.
No real Docker operation, native model, external/paid request or customer record
was used. This is not a public/customer deployment clearance.

## Scope and reviewed source

Read the original tasks19–21 acceptance ledger,
`CUSTOMER_UPDATER_IMPLEMENTATION_20261031.md`, `deploy/customer/UPDATES.md`, the
actual host helper and its installed package/backup/retention/bridge boundaries.
Repository and installed Agency AppSec instructions were followed. Earlier
release-gate and Update Center component reviews are separate evidence.

Frozen implementation hashes at review:

- `deploy/customer/updater.py`: `a2744e625d64799f583269f5c9c6cfe035157bf9c079f56e067e8823c98e9087`
- `backend/core/test_customer_updates.py`: `547ce8fb98fdbbaa8e1ce7c3d24b3bb9264ced285c076f9ff90ab8c2ba4f8d7a`

The reviewer did not implement the helper or alter product/core tests. At the
initial review, the owner had approved CP1/CP2 repairs only. The later explicit
UP1 approval is recorded below; earlier held findings remain unapproved. Actual
Linux/upgrade CI was pending when this review was requested.

## Independent executed cases

With process-local `PYTHONPATH=.local/customer-server-20261031/updater-security`:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py updater_security --verbosity 2
```

**9 tests in 6.313 seconds: 8 passed, 1 failed, 0 errors, 0 skips.** The failure
is the new UP1 countercase below, not a skipped check or mocked success. The
ordinary runner recorded zero external attempts and zero fixture HTTP connections.
Tests use real disposable SQLite/media, backups and host lock/files, with every
Docker command and listener probe explicitly controlled. No operational database
or service was modified.

| Boundary | Actual result |
| --- | --- |
| Expired request and cross-domain HMAC | Rejected before apply authorization |
| Candidate helper content corrupted before package verification | Installed verifier rejects before loading images/stopping writers; candidate helper never executes |
| Owner revoked after potentially slow local image loading | Fresh authorization rejects before writer stop |
| Second operation attempts independent journal lock | Actual lock prevents concurrent acquisition |
| Candidate migration changes retained human data | Activation prevented; exact original database/evidence preserved |
| Interrupted migration then another request | Independent incomplete journal blocks the new request and preserves backup bytes |
| Possible activation writes | No automatic source restart or rollback; explicit recovery refuses uncertain activation |
| Withdrawal before first ACK | Wrong current nonce is rejected; exact cancellation closes only the host journal without stopping/starting services or changing DB/conflict receipt bytes |
| Terminal journal contains another request's completion | **Failed: foreign completion result is returned without revalidating its request binding (UP1)** |

The review also inspected the actual private TLS probe: explicit RFC1918 target,
host/SNI verification with a supplied certificate chain, response-size bound and
exact release readiness. No new native TLS probe was executed by this reviewer;
the earlier independent loopback TLS evidence is separate and is not actual LAN
or target-device acceptance.

## UP1 — Low: terminal journal replay bypasses request/result binding validation

**Locations:** `deploy/customer/updater.py:423`–424 and `:593`–594. The existing-transaction branch
of `apply_update` returns `previous['result']` when phase is terminal after
checking only the operator paths. `recover_update` also returns terminal results
before the later `verify_request` step at line602. The normal nonterminal recovery branch
does verify the stored HMAC/request identity; the terminal branch does not.

**Executed reproduction:** the independent test created an operator-private
synthetic journal under the requested UUID. It held the same operator paths but
contained a valid synthetic signed payload and completion result for **another**
request UUID. Its phase was `completed`. `apply_update` returned that foreign
`completed` result instead of rejecting the inconsistent journal. The target
runtime did not exist; no Docker call or update occurred. Private
`UP1-observation.json` records `result_reports_completed` and
`returned_request_is_foreign` true, with actual upgrade/Docker false.

**Impact and prerequisites:** copied, corrupted or edited terminal metadata in
the independent private operator journal can be presented as a successful replay
for a different requested operation. The CLI's normal completed-result path can
therefore report success without validating the requested transaction's own
completion. This requires write access to the protected host journal or an
operator metadata mistake; it is **not** an anonymous web exploit, privilege
escalation or demonstrated modification of application approvals. The directory
ownership/lock boundary substantially limits exposure, hence Low severity.

**Recommendation:** validate terminal history before the fast idempotent return:
require the journal format, signed request UUID/HMAC and immutable source/target/
artifact bindings, consistent result request/release/status fields and the
appropriate retained receipt/cancellation proof. Share that validation between
apply and recover. Reject a foreign/copied/corrupt terminal record without
re-executing anything or overwriting evidence. Preserve legitimate historical
completed/rolled-back/cancelled replay semantics; a historical completion need
not falsely claim it is still the currently running release after later upgrades.

**Initial disposition:** reported only, **unfixed**, requiring explicit owner
approval. That failing private assertion and observation remain preserved; later
approval, functional repair and independent closure are recorded below.

## Evidence and remaining limits

Private directory `.local/customer-server-20261031/updater-security/` contains
`updater_security.py`, `checks.log`, `UP1-observation.json`, `receipt.json` and
before/after source inventories. Four scoped source hashes were checked before
and after review. Test counts here are independent review cases, not additional
ordinary full-suite totals or real sustained processing benchmarks.

This review does not prove actual Linux Docker context/mount permissions, native
network cutover, final image supply-chain authenticity, external writer detection,
customer devices, off-device recovery, arbitrary hostile-parser memory safety or
all process-kill timings. The updater explicitly relies on the operator to stop
unmanaged writers and to trust the installed verifier, catalog and independently
delivered digests. Real install/upgrade/recovery CI and final exact-version target
acceptance remain separate gates.

CP1/CP2 have their separately approved bounded closure. A12/BR1/D1/D2/L1/CS1/CS2/AI1
remain held; UP1 required a new owner-approval decision at the initial review.
No other new exploitable
defect was established in this bounded host review. No fix, merge, release,
deployment, engineering decision or original evidence change was performed.

## Owner-approved UP1 repair: final separate closure review

The owner subsequently explicitly selected **"Approve UP1 fix"**. The lead
assigned a narrow shared terminal-history validator for both `apply` and
`recover`, then requested this separate review after the implementation agent's
executed failing regressions and functional GREEN. No approval for the older
eight held findings was inferred.

Reviewed final frozen SHA256:

- `deploy/customer/updater.py`: `2ad0d506faf6e6453f493d12e1e0f308a8df8c6b797065e7830e6e2c9cfba2e0`
- `backend/core/test_customer_updates.py`: `0e6393574ebdb7bef2e1e85e206de1555e73229a34f89060fd220e445db6f71c`

The shared terminal validator now checks the stored signed request identity and
input/path/result bindings, immutable signed receipt sequence, retained static
source/target identities and original backup/retention artifacts. A purpose-
separated `host-terminal-v1` HMAC seal binds that historical proof. It does not
re-run an update or require that a historical target's mutable human database,
later uploads or service uptime remain unchanged. Expiry is exempted only for
the authenticated historical replay; new apply authorization retains its TTL.

### Independently executed closure checks

First, the **original UP1 private assertion was rerun unchanged**:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py updater_security.IndependentHostUpdaterSecurityTests.test_UP1_terminal_journal_cannot_replay_another_requests_completion --verbosity 2
```

**1 passed in 0.490 seconds**, zero failures/errors/skips. Its original failing
receipt and `UP1-observation.json` are retained rather than overwritten.

Eight additional independent closure cases then ran:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py terminal_closure --verbosity 2
```

**8 passed in 21.032 seconds**, zero failures/errors/skips:

1. Genuine completed replay remains read-only after later human database edits,
   additional original uploads, request expiry and intentionally stopped services.
2. A request-domain signature cannot substitute for a terminal-proof signature.
3. A validly signed foreign request cannot reuse another terminal proof.
4. Changed signed receipt inputs or an incomplete receipt sequence reject replay.
5. Corrupt immutable backup media or retention proof rejects historical success.
6. Changed static target identity is rejected without touching later human rows.
7. Result UUID or owner-release-approval tampering is rejected in both commands.
8. Genuine cancelled and rolled-back histories also replay idempotently without
   executing Docker or repeating any update/recovery operation.

Every rejecting case exercised both `apply` and `recover`. Both commands retained
files rather than deleting or overwriting the tampered evidence. All closure
commands recorded zero external network attempts and zero fixture connections.
They used actual disposable SQLite/media/backup files and controlled Docker/
listener boundaries, not a real customer daemon or native vision service.

**UP1 is verified repaired within these reported and executed boundaries.** No
new exploitable defect was established in this bounded closure review. The
reviewer changed only private tests, receipts and this report. Final code hashes
matched the supplied functional freeze; no product/core test was altered by the
reviewer.

Private evidence under `updater-security/`: `UP1-original-green.log`,
`terminal_closure.py`, `UP1-closure-security.log`, `closure-source-before.json`,
`closure-source-after.json` and `UP1-final-closure-receipt.json`. Counts are
independent executions and must not inflate the ordinary unique suite total.

Separate Linux rehearsal changes addressing public-certificate readability and
build-context readability were inspected as fixture/configuration changes;
inspection is not an actual Linux run. Private-key/directory restrictions remain
separate requirements. Actual same-source Docker install, upgrade/recovery,
UID/mount permissions and final package results must be assessed from their
executed CI receipts, not inferred from these controlled tests.

CP1/CP2 retain their separate approved bounded closure. The eight older findings
A12/BR1/D1/D2/L1/CS1/CS2/AI1 remain held and were not repaired. Source/retained
verifier/key/journal trust, arbitrary hostile-root tampering, all power-loss
timings, customer devices, licensing and exact release approval remain outside
this closure. No public/customer deployment or merge was performed.
