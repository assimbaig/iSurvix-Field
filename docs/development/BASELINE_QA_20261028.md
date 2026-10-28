# Independent baseline QA and recovery review - 28 October 2026

Reviewed source: `fd365f107b75c370caa2b765837d2a23f907a80c`, merged PR23,
on `audit/baseline-recovery-a12-20261028` in `.local/b0`. Read the installed
Agency Reality Checker and Application Security Engineer definitions. No product
implementation, test weakening, model download or operational mutation was made.

## Current checks

| Check | Actual result |
| --- | --- |
| Full isolated backend |1237 run:1236 passed,0 failures,1 error,0 skipped;472.013s test time /481.328s runner wall time. |
| Frontend |All19 existing check scripts passed, with installed Edge. |
| Django system check |Passed. |
| Migration drift |Passed; no changes detected. |
| Dependency consistency |`pip check` passed. |
| QA controller syntax |`node --check` passed. |
| Isolated static collection |Passed. |
| Application source gate |Unchanged before/after; fingerprint `1bc667534b90fdb1aca80b02d5e8a9174bfa9d46463cd62af2ad1fa4c8ea86fb`. |

The single error is the unchanged
`RuntimeAdversarialTests.test_diagnostic_directory_symlink_is_rejected_without_touching_target`:
Windows refused fixture symlink creation with **WinError1314** before the security
assertion. This is an environment/test-execution blocker. The assertion is **not
verified**, and the full suite is **not green**. Re-run it on a Windows execution
identity with authorized symlink capability or a suitable Linux runner; this
review did not change operating-system policy or skip/rewrite the test.

Environment: Windows11 build26300, Python3.12.10, Django6.1.2, Node22.23.2.
The companion JSON records installed package versions, exact commands, working
directories, exit codes and timings. Durations observed during concurrent local
work are not an AI-throughput benchmark.

The first ordinary test run was interrupted by the agent server restart and left
only a partial dot log; it was archived as **Interrupted**, never accepted as a
pass. The complete replacement ran as a detached hidden process with
`PYTHONFAULTHANDLER=1`. Its isolated runner recorded zero external/model network
attempts and46 connections to controlled in-process HTTP fixtures. No native
segmentation fault occurred in this current run. This does not establish the
cause or resolution of historical Linux A12; see the separate native report.

## Independent recovery verification

After the recovery owner's actual fresh restore completed, this reviewer:

- Confirmed the target was the explicitly approved fresh `.local/r0`, not the
  operational root/database/media/private directories.
- Independently matched the archive SHA256 and restored SQLite byte hash to the
  checkpoint manifest, and obtained SQLite `quick_check=ok`.
- Independently checked21 deterministic original-media samples against both the
  live originals and restored files. This supplements the recovery owner's full
 4657-file verification and does not claim a second independent all-file pass.
- Read every row in all12 review/audit/approval/revision-related history tables
  from both restored and operational SQLite in read-only mode; rows were equal.
- Independently ran Git bundle verification and confirmed the merged baseline,
  original PR22 and prior PR23 feature refs were all retained.

The Windows MAX_PATH failure in the first long disposable directory was retained
as incomplete, not called a valid restore. The successful new short target
avoids that path-length failure without changing system policy or originals.
Source recovery and readonly ORM/FileField checks are separately recorded in
the recovery owner's procedure/receipt. No actual approval or worker run was used.

## Final requirement-ledger review

Independently parsed Markdown, CSV and JSON against the three supplied task names,
acceptance checks, owner Dot and blank due dates. All formats agree:01/02 Verified
on2026-10-28;03 Blocked with no completed date. Confirmed main now matches the
merged baseline, both unrelated untracked audit-report hashes remain unchanged,
and the previous feature ref remains0656dec. The ledger explicitly discloses the
non-green full suite, failed native labels, missing A12 crash evidence and unfixed
BR1; it does not claim release or crash acceptance. Proof is retained privately
as `final-ledger-review.json` and summarized in the companion report JSON.

## Separate post-functional AppSec phase

After the successful core restore and independent checks above, bounded tiny
synthetic archives tested the private extraction helper. Seven cases were
rejected: parent traversal, absolute path, drive path, backslash UNC, alternate
data stream, case collision, and an existing destination. Existing bytes stayed
unchanged. No operation targeted live data.

**BR1 - Low - incomplete path-conflict preflight.** Two additional edge probes
(`prefix` plus `prefix/child`, and Windows `same` plus `same.`) reached a
`FileExistsError` after creating one file inside the new disposable destination.
The private helper claims complete preflight, but these aliases/conflicts are
not rejected before extraction. Exclusive creation prevented overwriting; there
was no escape or original-data modification. The impact is restore robustness
and an incomplete destination, not established unauthorized disclosure.

Recommendation: reject file/directory-prefix conflicts and Windows trailing-dot,
space and reserved aliases during preflight. **Do not fix without owner approval.**
No helper change was made by this reviewer. Until approved, use only the verified
self-created checkpoint, preserve failed targets as incomplete, and never extract
over an existing directory. This finding does not invalidate the verified
known-checkpoint restore; it limits generalized untrusted-archive handling.

This is not exhaustive process-race, malicious-compression/resource or production
DAST coverage. Backups are same-drive; Windows ACL recovery, off-device custody
and credential revocation remain separate acceptance concerns. Previously held
security findings were neither fixed nor implicitly approved by this task.

## Exact execution

The final gate invoked the existing environment:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py --verbosity 1
$env:PLAYWRIGHT_BROWSER_CHANNEL='msedge'
# Each existing frontend/check-*.cjs was run individually with node.
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' manage.py check
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' -m pip check
node --check backend/static/core/js/qa_evidence_review.js
```

Working directories and the isolated static build command are in the companion
JSON. This report records evidence, not a merge, deployment or release approval.
