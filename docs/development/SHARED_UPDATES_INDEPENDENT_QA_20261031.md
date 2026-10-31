# Independent Update Center and retention QA — 31 October 2026

Scope: tasks20/21's saved Django Update Center and upgrade-retention fixture in
`.local/b6`, branch `feat/customer-server-readiness-20261031`. Repository rules,
handoff, original requirements and installed Agency QA profiles were read. The
reviewer did not implement the Update Center, styles, host updater or retention
helper and made no product-source edits. This report does not equate a signed
fixture receipt with a real privileged installation or recovery.

## Current independently executed results

- `core.test_update_center core.test_upgrade_retention`: **25passed in20.698s**,
  zero failures/errors/skips, zero external attempts or HTTP fixture connections.
- Fresh saved-data browser: **38/38passed**, covering authenticated owner requests,
  actual CSRF, persistence/replay, withdrawal, late/forged receipts and recovery
  state. Zero JavaScript exceptions, third-party requests or failed requests.
  One intentional customer-Admin403 was recorded, not hidden as a successful page.
- Additional actual mobile Save/Withdraw: **6/6passed** at390×844, including actual
  saved pending/cancelled states and unobstructed button click points.
- Existing mobile account menu → Update Center discovery/navigation: **3/3passed**.

The47browser assertions share the same isolated records. They are an independent
browser execution, separate from the backend agent's earlier22checks; they do
not represent47customers or a load benchmark. Unit/focused counts overlap full
regression execution and must not inflate its unique test total.

## Real browser scenario

The reviewer started a fresh isolated Django fixture on127.0.0.1:8973, using a new
private database/media directory, synthetic owner/Admin sessions and a synthetic
trusted catalog. Python-server outbound connections and third-party browser
destinations were blocked. No operational cookie, password, evidence or database
was copied. The environment's previously reported automatic-review problem did
not recur for this fixture startup or its executed checks.

1. Customer Admin GET was denied; the actual owner could discover the screen
   through the existing account menu and open the real route.
2. Save created exactly one pending request, not a host installation. Refresh and
   replaying the same submitted form retained one request/event.
3. Desktop1920×1080,1366×768 and mobile390×844 retained receipt/withdraw actions
   within the viewport without page-wide horizontal scrolling.
4. Pending withdrawal persisted cancellation and freed the next request slot.
   A late signed host verification could not undo the withdrawal or replace its
   occupied event sequence.
5. A second explicit request accepted a correctly signed verified receipt.
   Forged applying data showed a signature error and retained the prior state.
6. A valid applying receipt persisted. A signed completion naming the target was
   rejected because the fixture was still running the original release.
7. A signed interrupted phase retained the recovery lock and prevented another
   request. A subsequent correctly sequenced recovery receipt naming the running
   original release persisted `rolled_back` and released the lock.
8. Saved history/reload retained all five accepted events for that second request.
   A third request was saved and withdrawn using actual mobile clicks.

Read-only final SQLite inspection confirmed three requests: cancelled sequence1,
recovered sequence4, cancelled sequence1; nine retained events and zero active
requests. The original synthetic evidence bytes remained unchanged. Controlled
receipt files replaced during negative-case construction were copied aside,
preserving the failed fixture inputs. No actual Docker, migration activation or
rollback command was run by this browser scenario.

There is a small existing global Appearance-widget overlap at a mobile action's
left edge for some scroll positions. Both action centres remained unobstructed;
actual mobile Save and Withdraw worked. This is a cosmetic limitation, not a
blocked essential action. The reviewer made no unrelated/global widget changes.

Screenshots captured independently from the real interface:

- [1920desktop](screenshots/shared-updates-20261031/update-center-1920.png)
- [1366desktop](screenshots/shared-updates-20261031/update-center-1366.png)
- [390mobile](screenshots/shared-updates-20261031/update-center-390.png)
- [Recovery required](screenshots/shared-updates-20261031/update-center-recovery-required.png)
- [Actual mobile actions](screenshots/shared-updates-20261031/update-center-mobile-actions.png)

Private scripts/receipts live under `.local/customer-server-20261031/qa`:
`update_independent_fixture.py`, `update_independent_settings.py`,
`update_independent_browser.cjs`, `update-independent-browser-receipt.json`,
`update-mobile-action-receipt.json`, `update-navigation-receipt.json`,
`update-browser-persistence.json`, and `update-retention-independent.log`.
Only owned launcher61652/child50592 on8973 were stopped after the checks;
`update-server-stopped.json` records the shutdown. Other services were untouched.

## Retention-proof assessment

The helper inspected is `deploy/customer/upgrade_fixture.py`. Its seed is guarded
by the explicit disposable flag and a pristine synthetic-owner database. The
executed integration test creates an actual survey/template, three originals and
three previews, one PDF document, a manual evidence link, one immutable submission
revision, a queued AI job, a human remark and a governance event. A second seed or
non-disposable context is rejected. No engineering approval or native inference
is created by seeding.

The snapshot comparator checks old stable-primary-key rows and their values,
rejecting changed human answers, source hashes or deleted rows. Existing audit
rows remain identical while new audit rows may append. Authentication last_login,
sessions, migration tracking and maintenance-request/event tables have explicit
documented exclusions. Additive new tables are allowed. This is meaningful
retained-data evidence rather than merely a zero exit from `migrate`.

However, helper unit/integration tests alone are not a real supported-version
upgrade: actual old/new image execution, quiesced backup, failure recovery,
runtime activation and retained file/hash checks still require the privileged
tool tests and disposable Linux run. The seed does not cover every historical
approval/output state or prove a real customer database can be upgraded.

## Source reviewed and remaining gates

Source SHA256 values at this verification:

- `core/update_service.py`: `c364c5bfcd4329d312ff63855eff606ae2cd4d99facbbbff269fcb69c260076c`
- `core/update_views.py`: `a1055a2fe5564522c0e70c440bff33b198f94c599ff2c7c9289a7901d0d816c3`
- `templates/core/update_center.html`: `3fc89f20ccd23a40e0ae71b4f0bface216da0fbb11fbcb03aebfdbbc3eb4c11f`
- `deploy/customer/upgrade_fixture.py`: `53778021aae8c8aeb17e205a91fc765363b032c12c59088e7eeea82dd15d668e`

The previously reported CP2 quoted-YAML header case was independently rerun
against the final97b62369package repair: **one passed in0.626seconds**, zero
external requests. Separate AppSec closure and its broader checks are recorded
in the customer security report; this single repeat is not a universal secret scan.

Shared gate functional QA is in
[its separate report](SHARED_RELEASE_GATE_INDEPENDENT_QA_20261031.md). Independent
privileged host-tool countercases now have the bounded results below. Separate
phase6security review, final full regression, actual Linux supported-pair/failure-
recovery evidence, physical target access and owner exact-release/licensing
approval remain distinct gates. No merge,
deployment, real customer update, paid API or native Ollama call occurred here.

## Historical initial host-tool countercases: reproduced false completion

Private test module `qa/updater_independent.py` independently exercised actual
temporary SQLite/media and the real operator state machine with controlled Docker
responses. Initial run: **eight tests, seven passed, one failed in8.150seconds**,
zero errors/skips, external attempts or HTTP fixture connections. Receipt:
`qa/updater-independent-first.log`.

Passing cases verified expired authorization and wrong image IDs stop before
writer shutdown; a wrong running candidate release prevents listener activation;
the actual OS journal lock excludes a concurrent operation; hard interruption
retains the partial target and requires explicit recovery; activation uncertainty
never restarts the old listener automatically; and completed replay does not run
Docker again or change source/target human rows and evidence.

The failing case showed a **false completion**: a target proxy reported exited/
unhealthy while target web health remained good, yet the updater returned
`completed`. Its post-proxy health check examined only the web container. The
reviewer sent the executed reproduction to the lead/package developer for repair
before separate phase6AppSec. No product code was edited by this reviewer.
The same regression was retained and rerun after the repair as recorded below.
No actual Docker daemon or customer listener was contacted by this reproduction.

## Independent repaired proxy and actual TLS checks

After the product owner added proxy running/healthy checks and a bounded TLS
readiness probe, the unchanged eight independent cases plus19 tracked updater
tests passed: **27 passed in33.941seconds**, zero failures/errors/skips or network
attempts. Receipt: `qa/updater-independent-proxy-green.log`. This verifies the
reported false completion no longer occurs in the controlled Docker fixture;
post-activation failures retain `activation_uncertain` and cannot restart the old
source automatically.

Separately, `qa/updater_listener_tls.py` exercised the actual SSL/HTTP probe with a
synthetic local certificate, explicit fixture-only trust, correct SNI/Host and
three outcomes: exact-release readiness succeeds, wrong release fails, hostname
mismatch fails. **Three passed in1.708seconds**, three actual loopback fixture
connections, zero external requests. Receipt: `qa/updater-listener-tls.log`.
Only the TCP connector mapped the requested private-LAN address to the fixture;
certificate validation was not disabled and machine trust was not changed. This
is real local TLS evidence, not proof of Docker, a physical LAN or customer TLS.

## Final bounded cancellation recovery follow-up

The reviewer also identified a pre-ACK withdrawal case: a cancelled application
request could leave the independent host journal nonterminal before any writer
stop. The product owner added a narrowly bounded recovery path, rather than
deleting the journal or inventing a successful application receipt.

Final command (absolute project Python; private QA path added to `PYTHONPATH`):

```text
scripts/run_backend_tests.py updater_independent.IndependentHostUpdaterTests updater_independent.IndependentCancellationRecoveryTests core.test_customer_updates --verbosity 2
```

Result: **35 passed in42.369seconds**, zero failures/errors/skips, zero external
network attempts or HTTP fixture connections. These are13 independent private
cases plus22 tracked cases, overlapping the earlier runs rather than additional
unique full-suite tests. Receipt: `qa/updater-independent-final.log`.

The unchanged original eight cases remain green. Five new independent cases
verify exact owner withdrawal becomes host-only terminal cancellation with
idempotent replay; wrong nonce and unknown application state are refused; source
TLS failure cannot trigger a start/stop; and a preexisting partial target cannot
be treated as a safe no-op. Each negative preserves the unresolved journal,
original receipt, source database and target sentinel where applicable. Valid
cancellation does not add an application receipt or invoke stop/start/migrate.
The tracked set additionally verifies the next request can proceed and an
unhealthy source proxy prevents reconciliation.

Reviewed source at final execution:

- `deploy/customer/updater.py`: `a2744e625d64799f583269f5c9c6cfe035157bf9c079f56e067e8823c98e9087`
- `backend/core/test_customer_updates.py`: `547ce8fb98fdbbaa8e1ce7c3d24b3bb9264ced285c076f9ff90ab8c2ba4f8d7a`

No further functional defect was reproduced in these bounded countercases. This
does not close the separate security, actual Linux Docker, physical LAN, full
regression or owner release-approval gates. No product source was edited by this
reviewer and no operational records, native Ollama or paid service were used.

## Owner-approved UP1 repair: independent functional review

After the separate security reviewer reproduced UP1, the owner explicitly
approved that finding's repair. This approval does not apply to older held
findings. The implementing agent added shared terminal-history validation to
both apply/recover and a purpose-separated signed immutable terminal proof.
The original security RED and intermediate functional evidence remain retained.

Independent command (shared project Python; private QA path on PYTHONPATH):

```text
scripts/run_backend_tests.py up1_independent.IndependentTerminalReplayTests updater_independent.IndependentHostUpdaterTests updater_independent.IndependentCancellationRecoveryTests core.test_customer_updates --verbosity 2
```

**50 passed in82.500seconds**, zero failures/errors/skips, zero external attempts
or HTTP fixture connections. These are11 new independent UP1 cases, the prior13
independent host/cancellation cases and26 tracked cases; totals overlap prior
runs. Receipt: `qa/up1-independent-final.log`.

The11 new cases check both apply and recover. Invalid request HMAC, signed
foreign request UUID, altered result identity/release/status/approval, absent
terminal receipt, invalid receipt HMAC and changed retained-target installation
identity are rejected without Docker execution or journal replacement. Positive
controls preserve legitimate completed history after token expiry, later human
database writes and two successive successful updates with a changed catalog.
Rolled-back and cancelled histories remain idempotent. In particular, later
human data is not compared to the old backup or overwritten during replay.

Reviewed frozen hashes, confirmed before execution:

- `deploy/customer/updater.py`: `2ad0d506faf6e6453f493d12e1e0f308a8df8c6b797065e7830e6e2c9cfba2e0`
- `backend/core/test_customer_updates.py`: `0e6393574ebdb7bef2e1e85e206de1555e73229a34f89060fd220e445db6f71c`

No further functional defect was reproduced. This is functional regression
verification of the approved repair, not its separate security closure, actual
Linux Docker/physical LAN proof or release approval. Older unsealed draft
journals fail closed and need manual reconciliation; preserved original signing
keys, static installation metadata and immutable proof/backup artifacts remain
required. The reviewer's code changes are private tests/reporting only.

## Independent actual CI evidence and producer/consumer follow-up

At local HEAD `6f5f40d2b7e296e626636c700b85547f95bcd6be`, the reviewer executed:

```text
scripts/run_backend_tests.py core.test_release_gate --verbosity 2
```

**12 passed in0.966seconds**, zero failures/errors/skips or external attempts,
two controlled HTTP fixture connections. This includes the actual workflow
producer's `shared/release.json` output being consumed by the real updater
`_package` verifier. It is a real code/fixture integration, not Docker execution
or proof that the latest hosted shared artifact has already been published.
Receipt: `qa/release-consumer-final.log`.

The reviewer independently queried GitHub: customer workflow run41228058279,
job124616271002 completed successfully for exact source
`4ac435ff5d8e5de43abcb548de4cb9b74d199ebd`. The94KB verification artifact13052473014
was independently downloaded and its complete ZIP SHA256 matched GitHub's digest:
`3fa898e36934b309bd13722a01e59f7ec4c758a713f334f67b8b60af5b45857d`.

Actual JSON/log inspection verified:

- UID10001 could read the baked release and code; fresh image transfer/load,
  initialization, restart and repeat-initialization rejection passed.
- The artifact's actual manifest bytes match the reported SHA256; application
  and proxy image identities match across the manifest/install/upgrade proofs.
- Caught migration failure and separate interrupted-process recovery returned
  the original release; successful upgrade and idempotent replay passed.
- Source/target retention proofs agree:374 retained rows across73 tables and the
  same retained-row digest. Existing rows remain equal under the documented
  audit-append, last-login and maintenance-table exclusions.
- The separate isolated client verified TLS, persisted update history and exact
  Engineer original-photo bytes. Anonymous original access and platform-owner
  operational evidence access were denied. Raw media and external client
  connectivity were denied in the initial synthetic install.

The actual supported pair is the0057 baseline
`e37b28088a80de11e56f95a7989ad90f41fd9f48` to that exact4ac435f candidate. The proof
explicitly marks schema0056 automatic upgrade, native AI, physical customer LAN,
physical customer devices, real customer deployment and release approval as
false. The client uses an isolated proxy NIC; host-published TLS readiness was
checked separately. These boundaries are retained in the report.

The reviewer compared4ac435f to6f5: install/upgrade rehearsal assertions were not
removed. The shared workflow changed its record location and added a static
consumer verification before artifact upload. Current customer run41228944635 /
job124618873308 remained in progress at this observation, so the earlier passing
CI cannot establish latest-source acceptance. No complete transferable500MB
candidate was independently downloaded or installed by this reviewer.

Private evidence: `qa/ci-4ac435f-evidence.zip`, `qa/ci-4ac435f-job.log`,
`qa/ci-4ac435f-independent-receipt.json` and `qa/ci-independent-status.json`.
Final latest-source hosted checks, gated shared publication and owner exact
release approval remain the lead's separate delivery gates. No merge or
deployment was performed.

### Latest-source customer CI addendum

The later GitHub query independently confirmed run41228944635 /
job124618873308 completed **successfully** for exact source
`6f5f40d2b7e296e626636c700b85547f95bcd6be`. This supersedes the pending customer
status above. The reviewer hashed the latest locally retained ZIP, artifact
13053286662: SHA256
`858339416a0e72231441a09cd08520eeefd447a414719c94a9e113d2b0fc4913` matches the
recorded artifact digest.

Independent inspection of the ZIP's actual manifest/install/upgrade/result
records verified exact target source, matching manifest bytes and image IDs,
UID10001 readability, fresh install/restart, caught-failure rollback, interrupted
recovery and successful upgrade/replay. Source/target retention again agrees on
374 rows and73 tables, digest
`2287c755eccb935d644ef366746f6aa5d59147cebfdceafd70bbf62518076b13`.
The authenticated original-byte/access-denial and TLS checks are retained.
Only baseline `e37b28088a80de11e56f95a7989ad90f41fd9f48` is supported by this
proof. The earlier12 producer/actual-consumer integration tests remain applicable
to this exact source; no product code was changed during this addendum.

Receipt: `qa/ci-6f5-independent-receipt.json`. This closes the latest-source
**disposable customer Linux rehearsal** observation only. Full backend regression
and the hosted shared-release gate were still separate pending checks at this
review; physical LAN/devices, native AI, real customer deployment and owner
release approval remain explicitly unverified. No merge or deployment occurred.

### Final exact-source code-verification closure

The independent GitHub query subsequently confirmed all four workflows for the
same `6f5f40d2b7e296e626636c700b85547f95bcd6be` source completed successfully:

| Workflow | Run | Independently checked evidence |
| --- | --- | --- |
| Application verification | 41228944646 | Windows1611/1611 passed465.613s; Linux1609passed and2 existing Windows-only skips472.415s; pip/migration checks and Chromium job succeeded |
| Disposable staging | 41228944652 | Completed success for the exact source |
| Disposable customer server | 41228944635 | Actual install/update/recovery and hashed evidence inspected above |
| Shared immutable candidate | 41228944697 | Exact-source/fresh gate, actual-consumer step and draft artifact publication succeeded |

Backend counts/time were independently read from downloaded job-log footers;
frontend logs report19/19 scripts passed. The two Linux platform skips correspond
to existing native Windows launcher/process-tree cases, rather than newly
suppressed failing assertions. This hosted result supersedes the pending full/
shared observations above. It does not rewrite the disclosed earlier local
Windows privilege error or changing-source runs as successful frozen runs.

The actual shared artifact13052619886 ZIP SHA256 independently matches
`afb9e7c4de6c9550a08aa0b077b1e9dea482613c76560ccdbdb57b77de50fec5`.
The reviewer inspected its actual `shared/release.json` and consumer proof, then
ran the trusted current updater's static `_package` consumer against the real
downloaded package, with any Docker invocation explicitly rejected. It passed;
record/package/proof source, manifest and immutable image IDs agree. Both editions
reference those same image IDs. Eight existing holds and
`owner_release_approved: false` remain in the actual artifact.

Task19's exact-source draft gate/provenance, task20's owner-request/privileged
operator separation and task21's tested-pair recovery/retention have executable
evidence in the defined candidate scope. No additional in-scope omission was
identified in this final reconciliation. The supported upgrade is still only
e37b280(schema0057) to6f5(schema0057); this is not a general migration guarantee.
Physical customer/LAN acceptance, native AI accuracy, licensing, earlier eight
holds and owner exact-release approval remain outside this code-verification
closure. No customer deployment, merge or release approval occurred.

Private receipts: `qa/final-exact-workflows.json`, `qa/final-ci-windows.log`,
`qa/final-ci-linux.log`, `qa/final-ci-frontend.log` and
`qa/final-shared-independent-receipt.json`. Only this QA report and private
evidence were changed by the reviewer; shared requirements/ledger remain owned
by the lead.
