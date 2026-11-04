# iSurvix Field: current development handoff

## Read before work

Read `AGENTS.md` and `docs/development/DEVELOPMENT_RULES.md`. Preserve records,
original evidence, credentials, branding, revisions and human approvals.
Use isolated tests and the established recovery checkpoints. Keep local data
under this F: project. Do not merge PRs or deploy automatically without the
owner's existing authorization for the exact action.

When this is the owner's working PC, read `.local/hostinger-deploy/STATE.json`
and `.local/ACTIVE_CODEX_STATE.json` for current private operational details.
These ignored files and all credentials/backups must remain outside Git.

## Current source and delivery

Work is on `feat/hostinger-github-release-20261104`, PR #34:
https://github.com/assimbaig/iSurvix-Field/pull/34
The maintained integration branch is `feat/ai-settings-routing-20261031`.
The old default `main` is historical; do not reset newer work to it.

The corporate homepage has a compact **Login** dropdown at the far right.
The fixed iField destination is https://app.isurvix.com/login/.
`website/corporate/` holds an eight-file partial update for existing shared
hosting. Never replace the full corporate site with that partial directory.
Manifest bytes are fixed; Git attributes preserve LF on Windows and Linux.

The existing VPS beta remains on its previously verified application release.
A separately installed restricted receiver verifies owner-merged, same-repo
PRs, all exact-source checks, immutable artifacts, proven upgrade support and
runtime identity. The initial real automatic application update still requires
owner review and a normal merge commit after green checks. Do not squash/rebase
this delivery flow. See `docs/development/HOSTINGER_DELIVERY.md`.

The receiver uses a dedicated nonroot SSH key, fixed sudo command, deadline,
nonblocking admission, private journals, verified backup and new-target recovery.
Never copy a root key to CI, expose Docker/Ollama/database ports, execute a
candidate root installer, or rewind human records after possible public writes.
Corporate shared-hosting publication is separate from VPS application delivery.

## Local records and recovery

Local database is `.local/survey.sqlite3`; originals are `.local/media/`.
The existing database was upgraded from core0053 to0059 after a disposable-copy
proof. All 14,434 prior rows/old column values across69 tables were retained.
All 3,537 original media files were compared byte-for-byte by SHA256 against
the preserved pre-work archive. No operational surveys were used for destructive
tests or approval experiments. The latest private receipt is in STATE.json.

Recovery anchors remain under `.local/backups/`. Before cleanup, a fresh source
bundle, current0059 database and original handoff/audit files were saved in the
checkpoint recorded by `.local/hostinger-deploy/cleanup-checkpoint.json`.
Historical standalone audit reports are archived in `.local/audit-history/`.
Do not delete other worktrees, unique evidence, jobs, backups or pending work
because a folder looks old. Verify ownership, activity and recoverability first.

## Review status and remaining gates

Owner explicitly approved CS1 release-trigger repair and HD-S1/HD-R2 receiver
repairs. Independent real Linux deadline/concurrency tests, SQLite recovery
cases and installed restricted-SSH negative checks verified these repairs.
The latest PR checks are authoritative; earlier passing runs do not establish a
later commit's status. The Windows source-byte check found Git CRLF conversion;
LF attributes and a real Git checkout regression address that issue without
changing live assets or weakening hashes.

Unrelated native-AI, licensing, pilot, physical-device, capacity and production
release holds remain separate. Earlier hold identifiers A12, BR1, D1, D2, L1,
CS2 and AI1 are not cleared by this task; verify the retained reviews before
changing them. The PC worker is not connected to the fresh
VPS beta. Do not download another model, add paid services or claim native
accuracy/engineering compliance based on ordinary tests. Two informational
operator observations are in the private independent review: missing empty SSH
home warning and this Windows default CA store's expired cross-sign. Full trusted
verification with the already installed certifi bundle succeeds; never bypass TLS.

## Checks and local preview

```powershell
.local\venv\Scripts\python.exe scripts\run_backend_tests.py --verbosity 1
.local\venv\Scripts\python.exe -m unittest discover -s website/corporate/tests -p "test_*.py" -v
.local\venv\Scripts\python.exe backend/manage.py check --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run --settings=checklist.settings_local
.local\venv\Scripts\python.exe -m pip check
```

Frontend checks: `npm.cmd ci --prefix frontend`, then run `npm.cmd test` from
`frontend/`; use the installed Edge via `PLAYWRIGHT_BROWSER_CHANNEL=msedge`
if Playwright Chromium is absent. No native-model downloads are required.

Local preview is loopback-only http://127.0.0.1:8000/login/. Startup:

```powershell
.local\venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:8000 --noreload --settings=checklist.settings_local
```

No worker was started by the website/delivery task. Review native runtime and
scoped worker credentials before starting inference. Private login details and
exact live Compose paths are referenced only in the owner's ignored state and
handover, never in public source.
