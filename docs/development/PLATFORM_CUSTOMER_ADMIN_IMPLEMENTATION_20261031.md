# Task 05: platform and customer administration

Implementation commit: `81982db2d6fd3c6088856b54556112a9a2cd94da`.
Parent: Task 04 `d7f63ad`; PR25 was subsequently merged upstream as `7d69e57`.

Existing roles and approved workflows remain controlling. Administrative endpoints
reject protected role, company and global-permission overrides. Existing successful
administrative events include typed, allowlisted actor/target/scope and persisted
before/after snapshots. Audit failure rolls back the administrative mutation.
Admin invitation acceptance captures ownership before profile-save side effects.
No new schema migration, operational account change or deployment was performed.

## Executed verification

- Full ordinary backend suite: **1,323 run, 1,322 passed, zero failures, one error,
  zero skips**, 451.345 seconds; final run 28 October 2026, 20:14–20:22 UTC.
- The error is the unchanged Windows symlink-privilege fixture
  `RuntimeAdversarialTests.test_diagnostic_directory_symlink_is_rejected_without_touching_target`.
  Windows returns WinError1314 before the security assertion. This check is blocked,
  not passed or skipped. The full suite is consequently not green.
- All **19 existing frontend scripts**, Django check, migration-drift check,
  dependency check, JavaScript syntax and isolated static build passed.
- Focused implementer gate: 74 tests passed. Independent functional gate: 13 tests,
  two supplemental positive controls and 35 actual browser checks passed across
  six roles at desktop/mobile widths. These counts overlap full-suite coverage.
- Separate security review: nine adversarial tests passed; no new exploitable
  issue established in that bounded scope. See the independent QA and security
  reports. No subsequent security remediation was applied.
- Frozen application fingerprint:
  `6642e67dc4d06e08db3a400a602c39722fb3b28c7467c4100960da0b40ef6f91`.
  Final gate recorded no source changes during execution.

Commands, from the Task05 feature worktree using the existing environment:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py --verbosity 1
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' backend/manage.py check
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' backend/manage.py makemigrations --check --dry-run
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' -m pip check
```

Exact individual commands/timings are retained privately in
`.local/b2/.local/platform-customer-admin-20261028/final/receipt.json`;
browser fixtures and bearer/session material remain private.

## Preservation and limitations

Before Task06 work on 31 October, a fresh consistent SQLite backup, verified Git
bundle and CRC-checked source archive were recorded at
`.local/backups/project-checkpoint-20261031-165639-platform-customer-admin`.
All 3,595 protected evidence/configuration files still matched the previously
restored trusted recovery archive. Operational source remains `fd365f1`, schema
0053; Task04 migration0054 has not been applied to operational data. Task05 adds
no migration. No native AI calls were made. A12 and earlier approval-held findings
remain separate unresolved items. Production deployment and proxy validation are
not established by these tests.
