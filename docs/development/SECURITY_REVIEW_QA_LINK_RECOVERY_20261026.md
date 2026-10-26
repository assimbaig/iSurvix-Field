# Follow-up separate AppSec - previous-link recovery

No new exploitable finding was established. This attack phase began AFTER the15-check actual browser recovery journey passed on the new functional freeze. Reviewer remains independent of implementation. No security fix was made; previous audit D1/D2/L1 remain unapproved and untouched.

`recovery-separate-security-tests.txt` and `recovery-security-exit.json`:23/23 passed in13.099s, native exit0, zero external network attempts. These comprise ten original independent batch/comment/retention reattacks, four NEW independent recovery tests in `audit_recovery_attacks.py`, and nine inspected/executed owner recovery regression tests.

New independent attack evidence:

1. An existing historical empty current revision restores the expected pairs, remains idempotent, does not copy accepted answers or source snapshots, and records the current requesting QA as causal actor with original matching actor retained as provenance.
2. A REAL current QA unlink remains removed after recovery. A current accepted human answer and its empty selected evidence remain unchanged; older manufacturer links are not copied onto that field.
3. A foreign-company QA and all wrong current roles are denied without events. Missing CSRF, stale revision/source/review identity and wrong template cannot write. A locked candidate mixed with eligible fields rejects atomically without partial persistence.
4. A legitimately completed QA package rejects recovery without reopening completion or changing events.

Existing executed recovery tests additionally prove a bounded scan bridges empty legacy revisions, intervening unlink/reassign decisions beat older matching, no eligible result returns count0 honestly, altered/removed photo sources do not recover, and changed approved schema/template stops lineage recovery.

The first independent unlink fixture attempted to remove an already-absent pair and correctly received409. The scenario was corrected to establish and then remove a real current pair before recovery, testing the intended later-human-removal boundary. Initial failure and exit receipts are preserved as `recovery-security-initial-fixture.txt` and `recovery-security-initial-fixture-exit.json`. No product code changed to make a test pass.

Reviewed source: category_intake.review_action retains current source/revision, assigned-QA, config and completion gates; qa_matching.action requires current review digest and exact frozen/current template identity for restore_previous_links. qa_matching.restore_previous_links bounds traversal to20 prior same-task revisions and2000 saved links/request, requires continuous photoID+SHA and exact template/schema, checks prior snapshot integrity, blocks current accepted/answered/mapped fields and explicit link/unlink/reassign pairs, checks section locks before bulk creation and uses canonical replay. The compact response reports actual restored_count, and the frontend requires an explicit confirmation and preserves unsaved state. Source receipts: `recovery-reviewed-hashes.json`.

No native inference, operational recovery or production DAST was performed. The current source files were reviewed and tests executed, but an exhaustive adversarial concurrency/fuzzing campaign was not performed. No security remediation is authorized or included in this result.
