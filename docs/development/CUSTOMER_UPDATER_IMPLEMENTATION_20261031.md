# Customer host updater implementation receipt

Branch: `feat/customer-server-readiness-20261031`, isolated worktree `.local/b6`.
The installed Agency DevOps definition and repository TDD rules were applied.
The implementation owns `deploy/customer/updater.py`,
`backend/core/test_customer_updates.py` and `deploy/customer/UPDATES.md`.
Root owns installer integration, deployment CI and release-gate checks; the
backend agent owns Update Center, signed bridge, model and migration0057.

## Implemented behavior

- Operator-host apply/recover CLI; no Docker socket or package execution in web.
- Exact current/source/catalog/artifact/edition/nonce bindings and short-lived
  application HMAC request; independently trusted package SHA verification using
  the installed verifier before loading/executing any candidate code.
- Fresh application authority after offline image loading, and confirmed
  verified/applying receipt acknowledgements before stopping managed writers.
- Durable private host journal and lock outside application DB/data. Other
  requests cannot bypass an unfinished transaction; completed replay is idempotent.
- Existing production SQLite/media backup validation and restoration into a NEW
  candidate; original source and every failed partial target are retained.
- Migration only against the copy; existing row/answer/review data and evidence
  hashes compared before internal-web readiness/baked-release checks and cutover.
- Durable activation boundary; pre-activation failures restore the old service
  and record safe failure/rollback history. Post-activation uncertainty never
  automatically reopens the old proxy or discards potentially new target writes.
- Explicit interrupted-process recovery reconciles receipt history and returns
  to the preserved source only before activation. No blind live downgrade.
- Source packages produced by a previous upgrade work for a second upgrade.
- Offline no-pull/no-build execution; no package/model downloads, paid calls,
  operational migrations or engineering approvals in this implementation work.

## Executed TDD and verification

From the isolated worktree, using the existing absolute project interpreter:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py core.test_customer_updates --verbosity 2
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe deploy/customer/updater.py --help
git diff --check -- deploy/customer/updater.py backend/core/test_customer_updates.py deploy/customer/UPDATES.md
```

Initial nine tests executed RED before the updater module existed. Additional
executed REDs reproduced missing explicit recovery, second-upgrade package-root
rejection, an unrecovered request bypass, the disposable hard-interruption hook,
and owner revocation after a slow offline image load. No assertion was loosened
to obtain green. Test-only fixture writes preserve Windows file bytes/hashes.

Final focused run: **22 passed in28.235s, zero failed, errored or skipped**.
The runner recorded zero external network attempts and zero HTTP fixture calls.
Tests use real disposable SQLite/media and the actual backup/restore helper;
Docker is controlled. Signature compatibility is compared against the real
Django bridge implementation. Unit/integration cases cover success, malformed
or stale signed requests, wrong bindings, corrupt packages/catalog/source rules,
withdrawal ACK failure, retained records/evidence, migration/health failure,
interruption/recovery, activation uncertainty and two successive updates.

Private receipts are under `.local/customer-server-20261031/package/`:
`updater-red.log`, `updater-recovery-red.log`, `updater-second-upgrade-red.log`,
`updater-recovery-boundary-red.log`, `updater-fresh-authority-red.log` and
`updater-green6.log`. Independent functional QA then found a false completion
when the candidate web was healthy but its proxy had exited. Three tracked RED
regressions reproduced stopped/unhealthy candidate proxy, failed TLS readiness
and false recovery with an unhealthy original proxy. The repaired bounded check
requires running/healthy proxy and actual private-LAN TLS readiness with validated
host/certificate and exact release before completion or rollback success.
`updater-proxy-readiness-red.log` and `updater-proxy-readiness-green.log` preserve
this loop. Ordinary tests explicitly control Docker and listener I/O; actual
TLS integration is the separate Linux rehearsal. Help and whitespace checks passed.

A further executed RED reproduced the ACK1-withdrawal race leaving the independent
journal blocked after the website had authoritatively cancelled the request.
Recovery now performs a fixed read-only local-container ORM query with a separate
UUID argv, requires exact immutable bindings and failed/cancelled sequence1,
checks current source web/proxy/TLS, and closes only the pre-stop host journal as
`cancelled`. It does not alter the database, conflict receipt, audit or source
service state; no completed/rolled-back application event is invented. Replay is
idempotent and a subsequent valid request proceeds. Unknown states, changed nonce
and unhealthy source remain gated. Receipts:
`updater-cancelled-recovery-red.log` and `updater-cancelled-final-green.log`.

## Remaining verification/operational limits

Independent QA and separate AppSec review, actual Linux Docker CI upgrade and
recovery, full integrated regression and physical customer-server/second-LAN
device acceptance are separate gates. Docker/WSL are unavailable on this PC.
An ordinary controlled-Docker test does not establish those outcomes.

Unknown pre-first-applying receipt conflicts and post-activation uncertainty need
operator reconciliation. Exact terminal cancellation has the verified no-op
recovery above; other authority states are not guessed. External/unmanaged writer quiescence remains an explicit operator
responsibility. Only exact independently tested source commit pairs may appear
in the release support list. Legacy releases lacking the bridge are unsupported
by automatic updates. Windows-to-Linux absolute historical output paths are not
silently rewritten.

This receipt does not grant licence/commercial clearance, customer release,
deployment approval or immunity from defects. Existing unapproved security holds
are unchanged. No commit, push, merge or deployment was performed by this agent.
