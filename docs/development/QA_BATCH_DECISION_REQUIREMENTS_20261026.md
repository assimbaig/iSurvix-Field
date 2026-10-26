# QA batch evidence, compact lists and review decisions

Owner requirements, 26 October 2026. Baseline merged PR22 `2b05179`.
Branch `feat/qa-batch-decisions-20261026`; short worktree `.local/wip`.
Recovery checkpoint `.local/backups/project-checkpoint-20261026-222351`
contains verified source/private/media archive and consistent SQLite backup.
The main and existing preview services remain on their saved release while
implementation and test fixtures are isolated. Prior audit reports stay intact.

| Requirement | Expected behavior | Implementation owner/location | Verification | Actual result/status |
| --- | --- | --- | --- | --- |
| Fast photo assignment | Avoid full multi-megabyte reload for one move; bounded saved-data patch and meaningful errors | Backend: category_intake/qa_matching; frontend QA controller | Before/after bytes/query/time, saved-data browser DnD | Verified: 10,408,463 to2047 response bytes;77 to28 queries; actual saved-data browser DnD. |
| Multi-select movement | Drag selected photos together and provide equivalent click/touch actions; preserve other legitimate links | Same owners; batch link API/controller | Unit + HTTP atomicity/stale/lock tests; real multi-photo browser flow | Verified: selected-photo drag/click, atomic failures, stale/lock protection and unrelated-link preservation. |
| Compact lists for users | Shared task/site list density fits desktop/mobile and preserves identifying data, filters, sorting and actions | Frontend task_explorer and scoped shared list styles | All six roles as permitted at1920/1366/1024/390 | Verified: six roles,12 final desktop/mobile visits; no whole-page overflow or JS errors. |
| Approval visibility | Assigned QA/Team Lead can find Approve next to Reject; incomplete QA sees a disabled control and actual requirement explanation | Root route context/photo workspace; frontend decision template | Context/HTTP tests and role browser checks | Verified: QA/Team Lead controls visible; actual completion guards retained. |
| Approve with comments | QA, Team Lead and Client may approve with a nonempty bounded comment using the existing approval policy | Root review_route_service/views; frontend shared template | Unit + HTTP3/4layer and blank/stale/unauthorized tests | Verified: QA/TL/Client comments,3/4-layer routes, blank/stale/wrong-role negatives. |
| Compact decision history | Tabular actor/date/action/stage/comment history preserves complete audit information | Frontend _review_route/review_route.css | Browser/table semantics, long/hostile comment tests | Verified: compact table, actor/stage/time/comments; hostile text escaped. |
| Resubmission photo links | Keep eligible previous QA photo associations for unchanged originals and unchanged template fields; no inherited answer acceptance or approvals | Backend category submission/matching replay | Full reject/resubmit browser + HTTP removed/hash/template/late-AI cases | Verified: reject/resubmit retained19 eligible links while AI queued; no answer/approval inheritance. |
| Already-resubmitted sites | Explicit QA recovery for valid links lost before the fix; preserve current corrections, never restore a later removed/reassigned link, no approval inheritance | Backend guarded recovery action; frontend More tools | Legacy-empty revision fixture, actual browser recovery, repeated action/current-change/lock/foreign-revision tests | Verified: legacy-empty revision restored21 eligible links; refresh/repeat/current corrections and locks tested. |
| Category label hierarchy | Larger category heading, smaller linked-photo quantity beneath; readable controls | Frontend QA styles/controller | Computed desktop/mobile sizes, unique count checks | Verified:16px category names;11/12px linkage counts on desktop/mobile. |
| Existing safety controls | Preserve permissions, frozen revisions, approved locks, stale tokens, originals and human decisions | All owners | Focused integration/negative tests + separate AppSec after functional completion | Verified within focused scope: separate AppSec28-test and23-test suites plus browser attacks; no new exploitable finding established. Q1 wider-suite fixture remains Blocked. |
| Delivery | Relevant final checks, screenshots, independent QA/security evidence and recoverable code checkpoint | Lead and independent reviewer | Current final-source receipts | Verified: code committed/pushed as67d7cad; draft PR23 created; reports/screenshots and recovery checkpoint saved. Q1 Windows fixture remains Blocked as disclosed. |

## Ownership and implementation boundaries

- Agency backend owner: photo batch API and resubmission linkage retention,
  related unit/integration tests. No route approval service edits.
- Agency frontend owner: QA interaction/layout, shared list density, decision
  template/history and behavioral checks. No server authority changes.
- Lead: existing route service/comments alias, guided Team Lead context and
  confirmed JSON decision response, integration/checkpoint/documentation.
- Independent Agency QA/AppSec: isolated fixtures, browser reproduction,
  negative tests, reports and screenshots; no product edits.

Comments are a presentation choice for the existing `approve` decision, not a
conditional waiver or new approval state. Matching confirmation is distinct
from acceptance of an engineering answer. Resubmission carries only eligible
associations, with honest origin metadata and no fabricated new QA action.

The previous audit's Pillow/Gunicorn/credential-ACL and other unrelated findings
are **not authorized fixes by this request**. Record any new security findings
from the post-functional review; do not fix them until the owner approves.

## TDD evidence currently recorded

Lead's new approval/context/HTTP tests were executed RED before source changes;
GREEN result:10 tests passed in3.111s, isolated DB/media/cache, zero external
requests. Tests include four-layer QA/TL/Client comments, three-layer closure,
blank/oversized/nonstring comment rejection, ordinary blank approval, named
reviewer and stale/clarification restrictions, incomplete QA guards and Team
Lead guided JSON success/failure. Private receipts are under
`.local/qa-batch-decision-20261026/` in this worktree.

The route integration run initially caught an old test defining every Team Lead
as outside the guided JSON response contract. Named Team Leads now intentionally
use that contract. The unauthorized-role assertion was retained using Engineer,
and a separate named-Team-Lead/wrong-stage JSON403/no-event test was added.
All56 affected route tests then passed in10.988s. This extends presentation and
error handling, not reviewer authority.

The first full verification checkpoint was superseded before completion to add
the guarded legacy-resubmission recovery case. It is not a final test result;
the final suite must run again after all recovery files freeze.

## Final verification

Final v3:1226/1227 backend tests passed,0 failures,1 environment error (Q1 Windows symlink privilege); no skips. All17 frontend scripts, Django check, migration-drift check, pip check, JavaScript syntax and static collection passed. Source remained unchanged during the gate. See `QA_BATCH_DECISION_ACCEPTANCE_20261026.json` for exact commands and receipts.

The superseded v2 gate caught old frontend expectations for `confirm_link` and a misleading loaded-photo label. Only its test fixture/contract assertions were updated for the guarded batch API and correctly labelled selected count, with stronger stable-identity and retention checks. Final v3 reran all checks; previous failures remain in private receipts.

Delivery: draft [PR23](https://github.com/assimbaig/iSurvix-Field/pull/23) targets `feat/secure-outbound-survey-workers`. Product commit `67d7cad`; subsequent delivery metadata is documentation only. All11 scoped requirement rows have verification evidence; wider full-suite Q1 remains Blocked, so the full suite is not green. No merge/deploy.
