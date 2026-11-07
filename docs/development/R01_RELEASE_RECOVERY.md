# R01 recovery repair and V1.3.1 Beta release

## Approval and scope

- The owner approved publishing the PR44 application, then explicitly approved
  the previously reported High-severity R01 repair on 7 November 2026.
- Work starts from merged source `53058ba`, including PR42's audit documents and
  PR44's application. The exact-source/merge-tree gate remains unchanged.
- The public patch version is **V1.3.1 Beta**. Release highlights are bullets;
  source/PR identities remain internal and in the release review record.
- R01 changes no Django models, company boundaries or engineering approvals.
  The previously approved application still requires additive migrations0065–0067.

## Recovery invariant

- Before opening either a candidate or a restored runtime to public writes,
  persist the public-write boundary in the transaction and active journals.
- Keep that boundary through diagnostic, freeze and subsequent phase writes.
  Legacy `phase` and `failure_phase` values also establish the boundary;
  a false or malformed marker must not erase that evidence.
- On restart, check the transaction journal as well as the active summary.
  Bind both to the same transaction, PR, source, merge, manifest and environments.
  Missing, corrupt or conflicting recovery evidence fails closed.
- An interrupted post-opening transaction requires a freeze and operator
  reconciliation. It must not activate an older backup over possibly newer work.
- Attempt to stop public writers even if saving the frozen journal fails.
  A failed stop or journal write does not grant permission to rewind on retry.
- Preserve safe pre-opening rollback, normal next releases after completed or
  rolled-back transactions, and the existing completed-replay identity checks.

## Executed verification and limits

- TDD reproduced the old defect before implementation. Thirteen new tests use
  actual controller execution, disposable SQLite records and evidence files.
- The focused controller/workflow/boundary suite ran67tests:64passed and3existing
  platform skips. No external network attempts; four in-process fixture calls.
- V1.3.1 notice integration:12backendtests and31browser fixture checks passed.
- The lead's final full suite and independent security review are separate
  receipts. Verify current exact-source CI before installation; focused checks
  and this document alone do not establish live delivery.
- No operational records, evidence or approvals were used for destructive tests.

## Trusted-helper installation and live verification

- Preserve a root-only checkpoint of the installed controller and verifier.
- Use exact reviewed Git blob bytes, not Windows newline-converted working
  copies. Validate hashes, compile without executing candidate code, preserve
  root ownership and reject unexpected installed-file changes.
- Hold the delivery lock, verify no old controller process is active and replace
  only the reviewed helper files atomically. Keep the backup and install receipt.
- The installed verifier must support the approved0065–0067 retention checks
  before a new delivery starts. Never weaken its schema or empty-table checks.
- Use the existing authenticated, owner-approved GitHub delivery with the fresh
  exact-source candidate. Do not replay the obsolete PR44 artifact or bypass
  merge-tree/approval checks.
- Verify public readiness, actual running source, schema, retained records/media
  proof and supervised workers after delivery. Do not send test emails or alter
  engineering decisions merely to validate a release.
- If a public-write boundary is interrupted, preserve the current data, backups
  and journals for approved reconciliation. Never blindly restore an older copy.
