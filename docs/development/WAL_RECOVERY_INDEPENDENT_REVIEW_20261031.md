# Independent WAL backup/recovery review — 31 October 2026

Result: no new exploitable finding established in the reviewed WAL repair. Independent execution passed 24 operations tests and 12 existing security regression tests, with zero failures, errors or skips. This is a bounded local review, not cloud or production acceptance.

## Authority, independence and scope

Reviewed after the implementation owner's final 63-test GREEN/freeze signal. The reviewer did not implement or edit application code or tests. Read `AGENTS.md`, `docs/LOCAL_CODEX_HANDOFF.md`, `docs/development/DEVELOPMENT_RULES.md`, and the installed Agency definition `C:/Users/Muhammad Assim Baig/.agency-agents/security/security-appsec-engineer.md`. Branch: `feat/cloud-staging-readiness-20261031`, worktree `.local/b4`.

The primary source scope was `backend/core/operations_backup.py` and `backend/core/test_staging_operations.py`. Root additionally authorized reading and rerunning the existing 12 tests in `.local/cloud-staging-20261031/security/security_assault.py`. No additional testing payloads were created. Existing approval-held D1/D2/CS1/CS2 findings remain unchanged and unremediated by this review.

Reviewed source SHA256 values, checked before and after verification:

- `operations_backup.py`: `615f3ceb1cf984e46d46d42a09739681e3a5b3989fd2c6c505c0d98caee8490c`
- `test_staging_operations.py`: `a89b4242e398645a3b9978e45017f9f008de4a6b552ef6a100bceb1aea0cd956`

## Evidence and interpretation

`operations_backup.py:143` changes journal mode only on the newly created destination snapshot, after SQLite's backup API has incorporated committed source WAL frames. The source connection remains read-only. `operations_backup.py:107` inspects standalone snapshots with `mode=ro&immutable=1`, preventing validation from creating WAL/SHM sidecars. Exact artifact inventory and digest checks remain before integrity inspection (`operations_backup.py:192`), and restore still rejects existing targets before copying (`operations_backup.py:200`).

The existing negative tests were executed against the frozen repair to challenge corruption handling, filename validation and destination preservation. These remained rejecting rather than bypassing integrity checks:

| Requirement | Executed evidence |
| --- | --- |
| Committed source WAL records survive backup/restore | WAL unit regression compares logical dumps with committed frames still in source WAL; saved-survey HTTP integration compares the complete captured database, including a committed WAL marker |
| Source records, main-file bytes, WAL bytes and WAL journal mode remain unchanged | WAL unit and saved-survey integration assertions pass while the source connection remains open |
| Newly created backup is standalone | WAL regression checks exact root contents and recovered DELETE journal mode |
| Repeated validation/restore does not mutate artifacts | Standalone WAL-header regression validates twice, restores into two fresh destinations, and compares complete source file hash inventories after each operation |
| Unexpected/missing files and corruption fail closed | Existing unknown-file, missing-file, corrupted-media and recomputed-hash/database-corruption regressions pass |
| Existing targets remain preserved | Existing destination and sentinel-preservation regressions pass |
| Path validation and file boundaries remain enforced | Existing traversal, drive/reserved/alias/prefix, duplicate-key, case/Unicode collision and actual local junction regressions pass |
| Interrupted copy is visibly incomplete | Existing synthetic copy-failure tests preserve originals and require INCOMPLETE without a complete manifest |

Commands ran from `.local/b4` using the project interpreter `F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe`:

```text
scripts/run_backend_tests.py core.test_staging_operations --verbosity 2
scripts/run_backend_tests.py security_assault --verbosity 2
```

For the second command only, process-local `PYTHONPATH` pointed at `.local/b4/.local/cloud-staging-20261031/security` so the existing private module could be imported.

- Operations: 24 tests passed in 30.374 seconds; zero external network attempts; 8 connections to in-process HTTP fixtures.
- Existing security regressions: 12 tests passed in 12.032 seconds; zero external network attempts; zero HTTP fixture connections.
- Both commands exited 0. The runner isolated database, media, model caches and logs; synthetic recovery fixtures stayed under this F: worktree.
- Raw private receipts: `.local/cloud-staging-20261031/wal-review/operations-tests.log` and `security-existing-tests.log`.

## Findings, recommendations and limitations

No new vulnerability severity is assigned because no new exploitable finding was established in this scope. Recommendation: retain these WAL preservation and immutable validation regressions as required recovery checks; keep restore restricted to new disposable destinations and require stopped writers as already documented. No remediation was performed.

This review does not verify an off-device restore, Linux/cloud filesystem behavior, private DNS/TLS, physical phones, native Ollama, hostile concurrent filesystem mutation, or administrator replacement of both artifact and manifest. Artifact hashes detect corruption, not authenticated provenance. The reviewer did not rerun the separate 36 actual-proxy HTTP checks or a full backend suite, inspect credentials, call external services/models, alter operational records/services, merge, deploy or commit. Broader security approval holds remain the owner's decision.
