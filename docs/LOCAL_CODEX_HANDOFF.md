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

## Current work: Super Admin desk and notification controls

The owner selected the Company Management Desk and authorized implementation.
Branch `feat/superadmin-company-desk-20261106`, draft PR #40, prepares V1.2 Beta.
It reuses existing governance/onboarding services, real saved records and
Company → Project → Site/task → Submission history navigation. Independent
saved-record browser checks and security tests passed; consult the PR and local
test receipts for final regression results rather than treating this note as
proof that every release check passed.

The owner subsequently requested company-customizable action messages and a
combined end-of-day notification report. That work is isolated in
`.local/worktrees/custom-notifications-20261106` until integration into PR #40.
Its additive migration 0064 requires exact retained-data/schema verification;
never bypass the trusted upgrade gate or apply operational migrations merely
because a migration file exists.

PR #39 is merged and live at source `8b39decc28638f19fc7ab584e6ebbe97238fb46a`.
Its first deployment safely rolled back because the installed trusted helper
lacked migration 0063 support. Reviewed helper/controller installation followed
by the guarded retry passed; preserve its helper checkpoint and runtime proof.

Email was explicitly enabled by the owner on 6 November 2026. Microsoft returns
canonical text `True`/`False` for native scope checks; the protected operator now
parses only those exact strings or booleans. Target-mailbox and outside-mailbox
checks passed, the owner confirmed the controlled inbox test, live application
authentication passed and the supervised worker was verified running. Private
activation receipts are under `.local/private/email/`, with server configuration
checkpoint `/var/lib/isurvix-delivery/email-activation-20261106`. Do not print
credentials, recreate the valid grant or reopen administrator sign-in merely
to inspect progress. Custom notification controls remain development work until
their reviewed release is installed.

## Previous source and delivery

Current work branch: `feat/admin-company-overview-20261106`, based on merged
PR36 commit `980d786`. The owner selected Company overview option A after three
completed design previews. The actual company Admin dashboard now uses scoped
saved-record totals and existing Project, Task, Client and Invitation actions.
Other role defaults, technical approval rules and explicit `?view=my_work`
behavior remain in place. The owner-approved AD-S1 malformed-project-ID guard
was fixed and independently retested; its regression remains in the suite.

The owner added all-role **What's New** notices for each installed release.
Migration0062 adds per-account/per-release acknowledgements only. A remembered
notice suppresses the current version; new release identities always prompt
again. Unchecked/X/Escape dismissal is limited to the current login. Keep the
curated content in `core/release_note_content.py` truthful for every release.
Read `docs/manual/ADMIN_COMPANY_OVERVIEW.md` and
`docs/development/ADMIN_DASHBOARD_AND_RELEASE_NOTICES.md`.

Source/data recovery checkpoint:
`.local/backups/admin-dashboard-20261106T115009Z` (verified source bundle,
coherent database/disposable restore and all3537 media files with hashes and
ZIP CRC). A second protected working-source ZIP/patch preserves the completed
Admin view before the notice addition. A coherent disposable0061→0062 proof
retained all14,359 policy-retained rows across77 prior tables, with an empty new
acknowledgement table. Consult `.local/ACTIVE_CODEX_STATE.json` and the private
task ledger for actual local migration, full regression, independent review,
PR and runtime status; code or documentation alone is not delivery evidence.

PR36 was explicitly owner-approved, merged and deployed. Its source972a71d is
live and healthy; guarded GitHub delivery run42207475930 confirmed it after an
idempotent retry. Email stays disabled: Microsoft organization customization
completed and the exact mailbox scope exists, but the final sending-role grant
failed. The owner objected to repeated `info@isurvix.com` administrator sign-ins.
**Do not reopen a Microsoft sign-in merely to check progress.** All native setup
sessions closed; retain the private recovery receipts and inspect offline until
the owner is ready for a single final, properly instrumented setup session.

Notice migration0062 also requires the reviewed exact-table retention-helper
prerequisite before hosted delivery. Do not weaken the trusted receiver,
old-row/permission/evidence checks or owner approval gate. Nothing in the Admin
or notice work authorizes an automatic PR merge or production deployment.

## Prior invitation-email implementation notes (historical)

Current work branch: `feat/invitation-email-20261105`, based on `bf3ca39`.
PR35 is merged and the live app was verified at `bf3ca39`. This branch prepares
Microsoft 365 invitation delivery from **ifield.notify@isurvix.com**; it is not
deployed or activated. See `docs/development/INVITATION_EMAIL.md`.
The shared mailbox and single-tenant registration exist. Private registration
details/credentials are under `.local/private/email/`; do not print or commit them.
Live Microsoft application authentication now passes with the replacement Value
saved privately. Do not ask the owner to paste a secret into chat. The actual
guarded Exchange administrator sign-in worked; a permission-binding conflict
still needs read-only inspection and positive/negative mailbox-scope verification.
Recorded partial progress is not proof that a tenant change did not occur.
No real invitation email was sent during implementation. The owner approved
EM-S1/EM-S2 and local setup-tool EM-S3 repairs; independent security retests passed.
Earlier holds below remain separate. Private evidence and final-run status:
`.local/email-configuration-20261105/STATE.json`.
Baseline04dd local regression:1897 backend tests,1891 passed/6 platform skips;
105 isolated Linux checks passed,21 frontend scripts passed with installed Edge,
and12 independent saved-record/11 actual browser checks passed. Both approved
Low findings were fixed and independently retested. Microsoft token
authentication passes; inbox delivery is not verified. All four04dd GitHub checks
passed. Those results do not cover newer uncommitted workflow-notification work.
The two reviewed04dd trusted helpers were checkpointed and installed on the VPS;
policy/runtime/application version remained unchanged. A private UID10001/0400
credential is staged, with permitted/denied reader checks; mail remains disabled.

The owner expanded notifications to task/reviewer assignment, submission,
approval/rejection, daily summaries and authorized full-report links. Additive
migration0061 and the shared background worker implement this extension. The first
full Windows run passed1956 tests with6 platform skips; independent workflow QA
passed23 checks and separate notification security review passed19 checks. A final
combined run/CI must include those added security regressions. See
`docs/development/WORKFLOW_EMAIL_NOTIFICATIONS.md`. The current operational local
database is now0061 after a coherent-copy migration proof and strict retained-row
verification. The new outbox is empty and local email remains disabled. All14,354
policy-retained rows across76 tables matched before/after; excluded maintenance
tables follow the documented retention policy. The pre0061 backup is private.
Do not deploy this candidate before exact-source release verification and owner
approval. Recovery checkpoint:
`.local/backups/workflow-email-20261105T203601Z` (verified source bundle/coherent DB).
Before a0061 hosted upgrade, install the reviewed candidate retention helper;
the currently installed helper admits0060 only. Keep owner review, strict retained
rows/permissions/evidence checks and the existing two-service runtime.

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
