# Task04 company-boundary acceptance evidence

Owner: Dot. Phase1 Company access. Original acceptance:
**Prove company A cannot access company B records, files or jobs.**

Implementation branch `feat/company-boundaries-20261028`, product baseline
`fd365f1`, documentation parent `89b55b1` (PR24 merged during work as98350ba; parent tree identical). Main local source/data are
not modified by this implementation. Prior A12 and approval-held findings retain
their status; this task introduces no model service, cloud fallback or new module.

| Check | Expected behavior | Owner/location | Verification | Status |
| --- | --- | --- | --- | --- |
| 04.1 Tenant definition | Employer Company is the security boundary; client organization, industry and project are subordinate contexts. Document intentional shared standards and platform administration exceptions. | Agency backend definition; existing Company/Profile/Project | Review actual model/guard relationships and positive/negative fixtures | Verified: model/guard definition and shared/administrative exceptions checked. |
| 04.2 Current identity | Cached user/profile/project objects cannot retain revoked, locked, disabled or former-company authority. | Backend access/company service | Unit and authenticated HTTP RED/GREEN | Verified:18 new core cases and related82-test suite; current stored authority enforced. |
| 04.3 Records and lists | Project/site/checklist/history, people/invitations, search/export and identifiers remain within current tenant and project grants. | Backend central guards; record access guards | Independent two-company role matrix, own-company positive controls | Verified: independent own/foreign lists, profiles, private templates and records; both directions. |
| 04.4 Record changes | Invitations/grants and historical project reclassification cannot move retained company A data into B. No historical answers or approvals are rewritten. | Backend governance/company service | Invalid nested IDs, stale objects, company mismatch, retained-history tests | Verified: retained-history/template/location/qualification/rule transfers rejected without mutation. |
| 04.5 Private files | Originals/previews/documents/drawings/reports/branding require authorized scope; direct file URLs do not bypass it. Client release controls remain. | File/job owner and existing download routes | Real stored bytes and hashes, nested-ID swaps, denied foreign reads, positive own/released reads | Verified: real byte delivery and foreign nested-ID/raw-media denials; released Client positive controls. |
| 04.6 Local jobs | Queue/status/control/output access remains project/company scoped; forged or stale IDs cannot read or mutate foreign work. | File/job owner | HTTP fixtures with persistent jobs and unchanged denial-state | Verified: persisted job/status/control/source/output scenarios; no native inference. |
| 04.7 Remote credentials | A company A token never follows an issuer/project into B. Bind immutable issuing-company scope and intersect current authority. | Remote service/model owner | Executed old-token RED; unit/HTTP positive/negative lease/input/results tests | Verified: reproduced A-token/B-job claim now denied; current and pinned scope intersect. |
| 04.8 Migration compatibility | Preserve all credentials/jobs/history. Backfill only proven issuing company; ambiguous legacy credentials remain unbound/denied until Admin reauthorization. Do not apply migration to live data. | File/job owner, migration0054 | Isolated MigrationExecutor legacy/proven/ambiguous cases | Verified: legacy/proven/ambiguous migration tests, nondefault alias sentinel and actual-copy rehearsal. |
| 04.9 Existing controls | Keep same-company project restrictions, named reviewers, locks, release decisions, explicit revocations and Super Admin administrative limits. | Both implementers | Existing affected suites and independent positive controls | Verified:82/63 affected suites plus full1287 run retained existing authority/locks; suites overlap. |
| 04.10 Independent quality | Recheck original acceptance, then separate adversarial security review. Report new findings without fixing them absent owner approval. | Independent Agency Reality Checker/AppSec | Saved-data HTTP/browser checks and attack receipts | Verified: independent15-test/64-browser journey and separate5-test AppSec; no new finding established. |
| 04.11 Delivery/preservation | Full repository checks, frozen-source receipts, ledger status, recoverable source/data and review-only PR. | Lead | Final full suite/checks plus private data/source checkpoint comparisons | Verified: full gate/screenshots/preservation recorded; implementation defc27d pushed; draft PR25 open. No merge/deployment. |

## Ownership and recovery

- Backend owner: `access.py`, `company_service.py`, `governance_views.py`, related
  unit/HTTP tests and company-boundary definition. No file/job view edits.
- File/job owner: existing survey access guards, remote worker service/model,
  migration0054 and related unit/HTTP/migration tests. No central-identity edits.
- Independent QA: its own tests, isolated fixtures, saved-data checks and reports.
  No implementation edits or operational approvals.
- Lead: integration, source/data checkpoints, acceptance ledger and delivery.

Recovery checkpoint:
`.local/backups/project-checkpoint-20261028-222122-company-boundaries`.
It contains a fresh consistent SQLite copy, source ZIP and Git bundle; all3595
source data files were rehashed and matched the complete verified checkpoint
`.local/backups/project-checkpoint-20261028-215901`, whose archive was genuinely
restored in task02. No operational migration, token rotation, source-evidence
rewrite, model call, deployment or merge is performed by this task.

The retired Django `/admin/` surface is tested as actually routed. Hypothetical
remounting of dormant ModelAdmin classes is not presented as a current exploit.

## Final-source receipts

Full gate:1286passed/1unchanged Windows fixture error;19 frontend scripts and other checks passed. Source remained unchanged. See `COMPANY_BOUNDARIES_ACCEPTANCE_20261028.json` and independent reports. All Company-boundary tests passed; this does not describe the wider suite as green.

Delivery: [https://github.com/assimbaig/iSurvix-Field/pull/25](https://github.com/assimbaig/iSurvix-Field/pull/25). Task04 acceptance is Verified on the feature branch. The final ledger records3/4 accepted tasks; A12 remains Blocked.
