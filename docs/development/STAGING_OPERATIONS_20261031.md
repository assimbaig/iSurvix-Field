# Task08: operational visibility and verified recovery

This is application code and local controlled verification, not acceptance of an
installed VPS, real PC worker or off-device disaster-recovery process. No live
survey, credential, original evidence, model or approval was changed.

## Probes and diagnostics

- `GET /ops/health/live/`: minimal process liveness, `{status, release}`. No database
  access or inference. Unknown local release is explicitly `unknown`.
- `GET /ops/health/ready/`:200 only when the database answers, installed migrations
  are applied, media/static directories are accessible and a configured upload
  temporary directory is writable. Failure returns503 with only `{status, release}`.
  No exception messages, paths, survey data or credentials enter this response.
- `GET /ops/status/`: current platform owner only; aggregate survey/photo job
  statuses, stale processing leases, open upload sessions, configured remote-worker
  projects, active/expired leases and last recorded heartbeat. These are stored
  states, not proof that a PC is currently online. Queued jobs are not stale jobs.
  In particular, photo `running` and `completed` states remain distinct.

All probes are non-cacheable. A valid32-character lowercase hex `X-Request-ID`
is retained; other values are replaced by a generated ID. Readiness exception logs
contain the stable event, release and request ID, never the raw exception text.
Owner diagnostics do not return model prompts, findings, tokens or job identifiers.
The website remains ready when a PC/model is offline; readiness never calls Ollama.
Normal authenticated owner access is required for diagnostics, not for probes.

## Capture a private backup

Use the reviewed deployment environment described in `STAGING_DEPLOYMENT_20261031.md`.
Stop **all web, local processing and remote-result writers** and confirm uploads
have stopped before capture. `--quiesced` is an operator confirmation, not a magic
writer lock. Keep the website in maintenance until capture finishes. The command
does not stop services or automatically activate any release.

From the Django backend directory, with its private environment loaded:

```sh
python manage.py staging_backup --destination /private-backups/new-snapshot --quiesced
```

The configured file-backed SQLite database is captured with SQLite's backup API;
all `MEDIA_ROOT` files are copied. Source evidence is not renamed or rewritten.
The directory artifact contains `database.sqlite3`, `media/` and a versioned
`manifest.json` with reviewed40-hex release ID, sizes and SHA256 values. Every
artifact is a **new** directory outside media; existing targets are rejected.
The root directory is created0700 on Unix. Use a trusted private parent, never a
static/web-served destination. Windows verification does not establish deployed
ACLs. Media changes during capture fail the operation rather than producing a
successful receipt. An interrupted/failed target is retained as incomplete;
absence of a valid complete manifest means it must not be served or restored.

This format supports the current SQLite deployment. It is not a PostgreSQL backup
tool. Environment secrets, TLS material and PC bearer credentials are not copied
into this artifact; preserve them separately in approved private secret storage.
SHA256 checks establish corruption detection against the supplied trusted manifest,
not authenticity against an administrator replacing both manifest and files.
Off-device/encrypted retention, retention schedules and recovery credentials remain
operational requirements. Never commit an artifact or private environment to Git.

## Rehearse recovery into a new directory

```sh
python manage.py staging_restore --backup /private-backups/new-snapshot --destination /private-restore/new-rehearsal
```

All paths, portable names, case/alias conflicts, file inventories, SHA256 values,
sizes and SQLite integrity are checked **before** creating the restore target.
Missing, extra, corrupt, linked/junction-backed or unsafe paths fail. Restore
never overwrites a directory, current database or current media. A failed copy is
retained incomplete. Recovery does not mount the target, migrate it, start a worker,
approve a survey or release outputs. Inspect restored records and media first,
restore the matching reviewed application/environment, and separately authorize
any activation. The release ID in the manifest must be considered during that review.

For disaster recovery when no configured database exists, use only the deployment
guide's explicit one-off bootstrap/restore environment. Do not weaken normal web
startup's missing-database protection. The destination parent must already exist
and be private; the new rehearsal directory must not exist.

Existing interrupted-worker recovery remains controlling: lease expiry allows a
compatible scoped worker to reclaim work, completed inference checkpoints persist,
and incompatible versions do not mix. Queued work is retained while the PC is offline.
Do not delete jobs or bypass human review to recover a worker. Private diagnostics
and existing startup helpers remain available; no new automatic recovery policy is
introduced. The previously reported private BR1 helper is untouched by this tool.

## Executed tests and functional repairs

`core.test_staging_operations`:22 tests, including real file-backed SQLite/media
backup, verified restore, management commands, corruption/missing/extra files,
portable-path rejection, incomplete-copy handling, read-only health and role checks.
Its actual saved-workflow test uses disposable Django HTTP transfer of real image
bytes, controlled inference, actual PDF/DXF generation and an exact SQL dump/media
hash comparison after restore. Draft release/answer acceptance remain false.
This does **not** claim native Ollama or engineering accuracy.

Final focused command, from the feature worktree:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py core.test_staging_operations core.test_staging_independent core.test_remote_survey_worker --verbosity 1
```

**61 passed in19.421s**, zero failures/errors/skips, zero external network attempts;
38 connections to in-process HTTP fixtures. Counts comprise22 owned operations,
13 independent checks and26 existing remote-worker regressions (overlap the full
repository suite). Existing remote tests cover expired leases, interrupted image
and result transfers, busy/failure retry, durable PC cache/checkpoint reuse, actual
exports and duplicate-result protection.

Meaningful initial RED16 missing-module/route errors was executed before code.
The first test harness retained a SQLite handle on Windows; it was closed before
the corrected RED. A real status-count RED found queued jobs incorrectly labelled
stale; photo running/completed values also needed their existing model-specific
states. A `None` choices fallback caused a500, reproduced by implementer and
independent QA, then fixed before final verification. Request-correlation RED
was executed before its implementation. No assertions were weakened or tests skipped.

Private receipts are under `.local/cloud-staging-20261031/operations/`. Root owns
the full repository/source/preservation gate and separate AppSec review. Clean
Linux/container startup, off-device restore, deployed proxy/TLS behavior, a real
phone and a real PC-worker disconnection/restart remain staging gates. Do not mark
Task08's external acceptance Verified on the strength of these local tests alone.
# Approval-held operational retention gap

Separate review recorded **CS2 / Low**: the current Nginx template writes proxy
logs under its `/tmp/nginx/` prefix, and Compose uses tmpfs for `/tmp`. Application
database/media backups preserve uploads and results, but proxy log history is
ephemeral and is not emitted into `docker compose logs`. Actual Linux restart
semantics were not exercised here. After explicit owner approval, use a protected
persistent destination or privacy-preserving collector/stdout configuration with
bounded retention, then verify restart retention. No configuration fix was made.
