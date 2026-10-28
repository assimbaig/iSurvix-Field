# Task04: company access boundaries

28 October 2026. The tested implementation is in `feat/company-boundaries-20261028`
(`.local/b1`). It reuses the existing Django authentication, Company/Profile/
Project model, project grants, private file routes and persistent processing jobs.
It adds no product module, role, dashboard or AI service.

## Implemented behavior

- Employer **Company** is the tenant. ClientOrganization and industry are not
  substitute tenant identifiers. Same-company identity still requires the normal
  project/role/reviewer/release permission. Super Admin remains administrative;
  intentional shared standard catalogs do not expose private operational work.
- Role/company/active/lock/global authority comes from current stored identity,
  so old cached User/Profile/Project objects cannot keep revoked privileges.
- Inconsistent foreign-company invitations are not listed or actionable. An
  established project cannot be moved from A to B while it retains surveys,
  assignments, templates/branding, locations, qualifications, evidence-rule
  releases, memberships/invitations or audit history. No existing data is moved.
- Worker credentials have an immutable issuing-company pin. Current issuer,
  company, named project ownership, expiry/revocation and existing lease/source/
  version checks are all required. An old A token cannot inherit later B jobs.
- Existing record/file/output routes already enforced parent/nested scope; their
  actual own/foreign-company controls were verified, not replaced. Client release
  rules, original bytes, stable source IDs, answers and approval locks remain.

Product files are `access.py`, `company_service.py`, `governance_views.py`,
`remote_worker_models.py`, `remote_worker_service.py` and migration0054. New
regression modules cover core authority, files/jobs/migrations and independent
company access. Dormant Django ModelAdmin classes were not remounted or redesigned;
the actual retired routes remain closed.

## Evidence

Meaningful executed RED cases reproduced cached authority, a cross-company job
claim by an old token, malformed invitations, private-template/logo transfer,
standalone retained records, and nondefault migration/model routing. Fixes then
passed their unit/HTTP/migration tests. Existing behavior assertions were retained.

Final full suite: **1287 run,1286 passed,zero assertion failures,one error,zero
skips**. The unchanged error is Windows WinError1314 while constructing a symlink
fixture; its security assertion did not run. All19 frontend scripts, Django,
migration drift, pip, JavaScript syntax and static collection passed. The gate ran
on the feature working tree and retained all source hashes/fingerprint; the final
implementation commit contains that same application code.

Independent QA:15 backend HTTP/unit tests,64 browser checks,3 released-Client
positive controls and20 reverse-company controls passed. Counts overlap and must
not be added as unique coverage. Actual scoped pages/exports, profile qualification
text, private drafts/logos, PNG originals/previews, document/source previews,
PDF/DXF/ZIP delivery, job controls and worker inputs/results were exercised.
Own-company and released-Client200 controls distinguish real isolation from
simply denying everyone. Test files establish delivery/access, not drawing accuracy.

After functional completion, a separate AppSec phase passed5 adversarial tests;
no new exploitable finding was established within that scope. Tests included
valid-CSRF foreign mutations, forged company hints, current/revoked affiliation,
NULL legacy credentials and nested source-ID swaps. No new security finding was
silently fixed. A12 and earlier BR1/D1/D2/L1 approval holds remain unchanged.

## Migration and preservation

`0054_remote_worker_company_pin` adds a nullable protected FK and backfills only
coherent explicit issuance proof. Unknown older credentials fail closed; an owning
scoped Admin must provision a replacement. No credential/job/lease/history row is
deleted. Current local operational credentials:0; other target databases may differ.
See `COMPANY_WORKER_BINDING_MIGRATION_20261028.md` before a reviewed rollout.
Do not downgrade an operational server/schema and resume unscoped credentials;
recovery requires a reviewed matching source/data/configuration snapshot.

Migration0054 was rehearsed on a disposable copy of the actual database snapshot:
all68 business-data tables were identical, only migration history and its SQLite
sequence advanced byone; FK/integrity checks passed. A first verifier omitted the
expected SQLite sequence update; verification was resumed without reapplying the
already successful migration. The source snapshot stayed byte-identical. The
operational database was **not** migrated.

After all tests, all3595 protected media/private/config files and all70 operational
tables matched the pre-task checkpoint. Both pre-existing untracked audit reports
remain byte-identical. Recovery checkpoint:
`.local/backups/project-checkpoint-20261028-222122-company-boundaries`, reusing the
complete task02-verified archive215901 with a fresh SQLite/source/Git checkpoint.
No customer survey was submitted, approved, reclassified or destructively tested.
No Ollama request or operational app/worker startup was performed. Only the owned
isolated QA server8940 was used and stopped.

## Review and test

Use two isolated companies with one permitted project/actor set each. Verify the
own-company list/export/file/job succeeds, then replace each project/task/photo/
document/output/job ID with the foreign-company ID and verify denial with no state
or byte changes. Repeat as each supported role, including released Clients.
Reclassify the fixture issuer/project after issuing an A worker token; the old
token must not claim new B work. Attempt to reclassify a retained A project through
the application; the data and company must remain unchanged. Test only disposable
fixtures, not operational approvals.

See the acceptance JSON for exact commands, independent reports for assertions,
and `screenshots/company-boundaries-20261028/` for synthetic desktop/mobile views.
No deployed Nginx/TLS/VPS test was run (nginx unavailable), and this is not exhaustive
race/fuzzing or native-AI acceptance. Main local operational source/data are not
deployed from this feature; review, migration and rollout remain separate actions.
