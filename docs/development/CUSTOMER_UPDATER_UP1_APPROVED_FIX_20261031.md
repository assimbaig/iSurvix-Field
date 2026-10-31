# UP1 approved terminal-history binding repair

The owner explicitly approved **UP1** with "Approve UP1 fix". This repair is
limited to the host updater's terminal replay validation. Earlier
A12/BR1/D1/D2/L1/CS1/CS2/AI1 holds remain unchanged. The original independent
security reproduction and observations are retained without rewriting their RED
result. Independent QA/AppSec closure and actual Linux CI are separate gates.

## Change

Both `apply` and `recover` now share terminal-history validation before returning
a completed, rolled-back or cancelled result. It requires the correct journal
format and operator paths, the requested UUID and purpose-correct original HMAC,
the exact derived result/status/release, and the retained signed receipt chain.
Historical request expiry is exempted for this read-only replay; a new apply
still requires fresh application authority before stopping writers.

Completed history additionally requires its retained target runtime and package,
initialization/configuration identities, database/media/static directory
existence, verified original backup and retained-record/proof artifacts. A new
immutable `terminal-proof.json` uses a separate `host-terminal-v1` HMAC purpose to
bind those static identities, exact proof/receipt hashes, request, paths and
result. The Django request/receipt wire protocol and database schema are unchanged.

The current human database and media file contents remain mutable. Replaying
history neither compares them to an old backup nor requires the historical
version to be running or present in today's catalog. Later human edits/uploads
are preserved. Missing or corrupt retained artifacts and old unsealed draft
metadata fail closed for manual reconciliation; no update is executed, no
retrospective seal is invented and no evidence/history is replaced.

## Executed TDD and focused checks

From `.local/b6` with the existing absolute project interpreter:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py core.test_customer_updates.CustomerUpdateTests.test_UP1_foreign_signed_terminal_journal_is_rejected_by_apply_and_recover core.test_customer_updates.CustomerUpdateTests.test_UP1_terminal_result_tampering_or_missing_retained_target_is_rejected_without_docker core.test_customer_updates.CustomerUpdateTests.test_UP1_backup_and_retention_proof_corruption_cannot_report_historical_success core.test_customer_updates.CustomerUpdateTests.test_UP1_historical_replay_preserves_later_human_writes_without_uptime_or_fresh_token --verbosity 2
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py core.test_customer_updates --verbosity 2
git diff --check -- deploy/customer/updater.py backend/core/test_customer_updates.py
```

Before repair, four tracked tests recorded **18 failed assertions**, including
both replay entry points. They promoted the independent foreign signed journal
case and added result tampering, missing retained target, corrupt backup and
retention proof controls. The later-human-write/expired-history positive already
passed before the repair and remains unchanged.

After repair, **26 tests passed in38.767 seconds**, zero failures, errors or
skips; zero external network attempts and zero fixture HTTP connections. They
include existing cancellation/rollback replay and two successive upgrades.
Docker and listener I/O are controlled; actual disposable SQLite/media and the
real backup verifier are used. No operational data or native model was touched.
Whitespace checks passed. Private logs:
`.local/customer-server-20261031/package/updater-UP1-red.log` and
`updater-UP1-green1.log`.

Functional freeze SHA256:

| File | SHA256 |
| --- | --- |
| `deploy/customer/updater.py` | `2ad0d506faf6e6453f493d12e1e0f308a8df8c6b797065e7830e6e2c9cfba2e0` |
| `backend/core/test_customer_updates.py` | `0e6393574ebdb7bef2e1e85e206de1555e73229a34f89060fd220e445db6f71c` |

Independent reruns, separate AppSec closure, full exact-source regression and
Linux Docker installation/upgrade/recovery remain the integrating lead's gates.
Physical customer LAN acceptance, licence/commercial approval, arbitrary opaque
image trust and off-device recovery are not established by these focused tests.
No commit, push, merge, production deployment or held-finding repair was performed
by the implementing agent.
