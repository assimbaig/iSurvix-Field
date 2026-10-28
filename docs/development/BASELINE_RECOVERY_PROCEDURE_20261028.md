# Baseline recovery procedure and disposable restore proof

28 October 2026. Task02, owner Dot. This is a local recovery rehearsal, not a
production rollback, deployment or proof of an off-device disaster recovery plan.

## What was actually restored

The fresh checkpoint is `project-checkpoint-20261028-215901` under the project's `.local/backups`.
It contains a consistent SQLite backup, the committed merged-PR23 source at
`fd365f107b75c370caa2b765837d2a23f907a80c`, original media, private configuration and branding,
plus a verified Git bundle. Two unrelated untracked main-checkout audit reports
were preserved separately. The initial empty checkpoint 215521 was interrupted
before a backup was written; it is not a valid recovery copy.

The accepted restore is the NEW disposable directory
`F:\iSurvix\iSurvix-Field\.local\r0`. It was never extracted over operational
data. All 4657 restored file hashes matched,
including 3537 media files and
58 private/configuration files.
All 70 SQLite table row counts and ordered
content digests matched, including review, approval, audit and submission history.
SQLite quick_check returned `ok`. The operational tables, original files and main
uncommitted reports were unchanged throughout the drill.

A separate Git clone from `repository.bundle` recovered the exact source commit
and its identical Git tree plus all 1061 archived
source file hashes using the recorded Windows Git conversion policy against the
saved manifest. Windows checkout attributes
normalize 666 text files to
CRLF; these differ only in declared line endings, not Git content. The
older PR22 and PR23 feature refs remain recoverable. A separate Django process
loaded the restored source/database read-only, checked ORM review-history counts,
read a restored original, rejected a database write probe and attempted zero
network/model calls. The JSON companion reports FileField/drawing reference
existence/hash results and any inherited anomalies separately; files or historical
records were not silently repaired.

## Real issue found and repaired during the drill

The original long disposable path produced 265-character filenames on Windows;
extraction failed before completion. That partial directory is retained and marked
incomplete. The verified archive was reused in a NEW shorter 228-character target,
without changing registry settings or deleting originals. A private path-preflight
regression was executed RED, then all 8 recovery guard tests passed after the
preflight/short-path repair. The guard also rejects parent/absolute/drive paths,
symlinks, case-colliding entries, existing destinations and corrupt/partial ZIPs.
This repair happened before independent security review.

## Separate security review finding: BR1 / Low

After the functional restore passed, the independent reviewer found that a
malformed archive with prefix file/directory conflicts or Windows trailing-dot
aliases can partially populate a NEW disposable target before failure. No
outside-root write or overwrite was established. Use this procedure only with
the trusted self-created checkpoint whose hashes were verified. A failed target
is incomplete and must never be promoted or reused as an accepted restore.

Recommended improvement is stronger alias/prefix preflight or transactional
extraction, subject to the owner's explicit approval. Per the development rules,
this security finding was reported and was NOT fixed after review. This tool is
not presented as a general-purpose untrusted archive importer.

## Locate the recovery copy in File Explorer

1. Open `F:\iSurvix\iSurvix-Field\.local\backups\project-checkpoint-20261028-215901`.
2. Keep the whole folder together: ZIP, SQLite, Git bundle, manifests, recovery
   tools and preserved-main-untracked. It contains credentials and private site
   evidence: do not put it in GitHub or a public file share.
3. Review the checkpoint and independent QA receipts before using it. `r0` is an
   already-used test copy; never extract over it or over the operational project.

## Rehearse another restore without touching operational data

Use a new short folder such as `.local\r1`, after confirming that it does not
exist. Keep application workers stopped for a real recovery decision; this drill
starts no worker/model. These commands only create the disposable copy:

```powershell
$project = 'F:\iSurvix\iSurvix-Field'
$backup = Join-Path $project '.local\backups\project-checkpoint-20261028-215901'
$python = Join-Path $project '.local\venv\Scripts\python.exe'
$destination = Join-Path $project '.local\r1'
if (Test-Path -LiteralPath $destination) { throw 'Choose a NEW empty short recovery path.' }
$env:PYTHONPATH = Join-Path $backup 'recovery-tools'
& $python -c "from restore_guard import extract_new; import sys; extract_new(sys.argv[1], sys.argv[2])" (Join-Path $backup 'project-source-and-recovery.zip') $destination
if ($LASTEXITCODE -ne 0) { throw 'Restore failed: retain it as incomplete; do not use it.' }
git bundle verify (Join-Path $backup 'repository.bundle')
```

Compare every restored file to `private-file-manifest.json`, then run SQLite
integrity and ordered table-history comparisons against `private-table-manifest.json`.
Never treat extraction alone as acceptance. The current accepted rehearsal and
read-only application checks are captured privately under
`.local/b0/.local/baseline-20261028/recovery`; the public JSON carries sanitized
counts and results. Ordinary unit/HTTP tests remain the repository runner's job.

## Moving from rehearsal to an actual recovery

Do not automatically copy a test database over live data or roll migrations
backward. Preserve the current database/media/job state first, select the approved
source revision and check schema compatibility. Restore originals, outputs,
branding and immutable review/audit history together. Confirm company/project
scope, reviewer decisions and current credential revocations before resuming
workers. Keep AI proposals distinct from human acceptance and engineering release.

This rehearsal is same-drive only. It does not prove survival of F: failure,
Windows ACL restoration, credential revocation recovery, a clean-PC dependency
installation, VPS restore or accepted RTO/RPO. Store an encrypted off-device copy
through the owner's approved backup process and test that environment separately.
No product module, operational approval, native inference, merge or deployment
was performed by the recovery procedure.
