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

Current work branch: `feat/invitation-email-20261105`, based on `bf3ca39`.
PR35 is merged and the live app was verified at `bf3ca39`. This branch prepares
Microsoft 365 invitation delivery from **ifield.notify@isurvix.com**; it is not
deployed or activated. See `docs/development/INVITATION_EMAIL.md`.
The shared mailbox and single-tenant registration exist. Private registration
details/credentials are under `.local/private/email/`; do not print or commit them.
The latest live authentication check returned HTTP401/AADSTS7000215. The saved
secret appears ID-shaped; the owner must supply the active secret **Value** for
this app privately. Scoped Exchange `Application Mail.Send` and live delivery
remain unverified. No real invitation email was sent during implementation.
The owner approved new EM-S1/EM-S2 repairs; independent security retests passed.
Earlier holds below remain separate. Private evidence and final-run status:
`.local/email-configuration-20261105/STATE.json`.
Final local regression:1897 backend tests,1891 passed/6 platform skips;
105 isolated Linux checks passed,21 frontend scripts passed with installed Edge,
and12 independent saved-record/11 actual browser checks passed. Both approved
Low findings were fixed and independently retested. Real Microsoft token
authentication still fails as described above; inbox delivery is not verified.
Before a0060 hosted upgrade, update the trusted controller/retention helper from
the reviewed source; retain owner review and the existing two-service runtime.

Previous follow-up branch: `feat/hostinger-trusted-push-20261105`.
PR #34 (https://github.com/assimbaig/iSurvix-Field/pull/34) is merged. Its
application release `dab9c55` was installed by the actual approved GitHub/VPS
delivery run, with trusted HTTPS/readiness and provenance confirmed.
The maintained integration branch is `feat/ai-settings-routing-20261031`.
The old default `main` is historical; do not reset newer work to it.

The corporate homepage has a compact **Login** dropdown at the far right.
The fixed iField destination is https://app.isurvix.com/login/.
`website/corporate/` holds an eight-file partial update for existing shared
hosting. Never replace the full corporate site with that partial directory.
Manifest bytes are fixed; Git attributes preserve LF on Windows and Linux.

The restricted receiver verifies owner-merged, same-repo PRs, all exact-source
checks, immutable artifacts, proven upgrade support and runtime identity.
The original PR-event run was rejected by the base-only environment policy.
An exact temporary rule admitted only the already merged PR34 for its successful
retry; that rule was removed. No wildcard PR rule was applied.
The follow-up uses a trusted integration-branch push, resolves its canonical
merged PR in a read-only job, and only then requests protected credentials.
Retain owner review and normal merge commits after green checks. Do not
squash/rebase this delivery flow. See `docs/development/HOSTINGER_DELIVERY.md`.

The receiver uses a dedicated nonroot SSH key, fixed sudo command, deadline,
nonblocking admission, private journals, verified backup and new-target recovery.
Never copy a root key to CI, expose Docker/Ollama/database ports, execute a
candidate root installer, or rewind human records after possible public writes.
Corporate shared-hosting publication is separate from VPS application delivery.

## Local records and recovery

Local database is `.local/survey.sqlite3`; originals are `.local/media/`.
This task added local migration0060 after a disposable-copy proof. All14,490
existing rows across79 prior tables were retained; the new outbox is empty.
Checkpoint: `.local/backups/email-configuration-20261105-182253` contains the
verified pre-task database and source bundle. Original evidence was not changed.
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
changing them. BR1 remains an explicit trusted-base assumption: the integration
branch has no protection/ruleset and the current sole repository collaborator
is its owner. The follow-up does not authorize changing that governance policy.
The PC worker is not connected to the fresh
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
