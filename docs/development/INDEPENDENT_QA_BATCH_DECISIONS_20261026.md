# Independent QA - batch matching, decisions and retained links

Status: requested functional paths verified with isolated synthetic data. This is not production/native-engineering acceptance. Reviewer was separate from implementers and made no product/source changes. Applied installed Agency Reality Checker, Test Automation Engineer and AppSec definitions. AGENTS.md, current handoff and development rules were read first.

## Isolation and reproducibility

Working product: `.local/wip`, branch `feat/qa-batch-decisions-20261026`, base `2b051791c96bd83aa283f48432187ef66ba0169f`. Owned files are only this `.local/qa-batch-decision-20261026` folder. `setup_copy.py` makes a read-only SQLite backup and media copy of the explicitly synthetic166-checkpoint/460-photo audit fixture. `server.py` uses the wip backend with copied DB/media and own logs on127.0.0.1:8928, disables outbound socket connections and model calls. No model/outbound attempt log was created. No operational record, original source evidence, production approval or live8000/8001/model11435 service was changed. Additional decision tasks were created through normal configure/submit/permitted-review services; no QA completion or approval lock was waived.

## Before/after evidence

`baseline.json` and12 `before-*-tasks-*.png` screenshots record six roles at1366 and390px. Admin/TeamLead task first rows were130.3px desktop/146.0px mobile;390px pages overflowed to627px. Engineer rows94.9/126.3px, QA71.4/85.9px. `baseline-details.json` and `before-decision-*.png` show3/4-layer permitted-stage panels lacked Approve with comments and used history article cards.

`final-visuals.json` and12 `after-final-*-tasks-*.png` screenshots verify frozen final page geometry: all six roles had no document-level horizontal overflow and no browser JavaScript errors. SuperAdmin operational task route remains forbidden. Admin/TeamLead first rows71px desktop/73px mobile; Engineer43.5/57px; QA43.5/45.5px. Client released-only row content differs after new synthetic approval tasks were added; measured59.8/73px, so a like-for-like Client density reduction is not claimed. Wide task columns scroll within the table container. Category names16px, link counts beneath11px desktop/12px mobile independently verified and captured in `after-category-labels-*.png`.

The initial independent65px density threshold was a reviewer interpretation, not an owner requirement. It was replaced by actual geometry/reduction evidence. Initial mixed-snapshot DnD attempted during implementation used new static JS with old backend imports; its identity mismatch is retained in `baseline-drag.json` as a diagnostic, not reported as a final product defect.

## Executed functional journeys

- `functional-browser.json`:114 passing checks. Six roles at desktop/mobile; ten disposable3/4-layer QA/TeamLead/Client stages each exercised ordinary Approve or Approve with comments, same-row Approve/Reject controls, blank-comment prevention, saved decision/comment persistence after reload and compact decision-history table. Ordinary approval retains optional comments. Source route services were already green; later final source edits were CSS/cache tokens/copy, with final visual recapture and final backend tests separately recorded.
- `batch-browser.json`:19 passing checks. Real desktop two-selected-photo drag uses one batch POST, compact24,129-byte response,449ms observed local interaction, no full-state GET, and preserves an unrelated thumbnail DOM node. Both links survive reload and counts update. A503 synthetic save failure commits nothing and preserves selected photos. Phone390px controls save a two-photo link batch. Actual QA rejection followed by actual Engineer browser resubmission created revision8 from revision2; all19 valid confirmed links remained while AI was queued. No accepted answers/completion were inherited.
- `move-browser.json`:15 passing checks on frozen UI. Desktop two-photo MOVE source015?016 uses one POST, removes only the selected source-point links, adds target links and preserves every unrelated existing link. Phone390px two-photo MOVE016?017 likewise uses one POST and persists. Incomplete QA Approve and Approve with comments stay visible but disabled with completion reason. A separate link batch succeeds while an unsaved QA answer remains the SAME input node and unchanged value. Repeatable move setup uses an authorized synthetic batch API; all actual moves use browser controls.
- `separate-security-browser.json` additionally verifies2 category typography cases. Three attack assertions are recorded separately in the AppSec report.

The private harness initially referenced a hidden obsolete mobile pane tab and a multi-node strict locator. Both harness errors were corrected to the actual Checklist & categories drawer and a unique node; no product fix was needed. These are not silent product-test retries.

## Representative screenshots

Before: `before-admin-tasks-390.png`, `before-qa-workspace-1366.png`, `before-decision-4-client.png`.
After: `after-final-admin-tasks-390.png`, `after-two-selected-drag.png`, `after-batch-failure-retained.png`, `after-two-photo-move-1366.png`, `after-two-photo-move-390.png`, `after-dirty-answer-batch-preserved.png`, `after-incomplete-QA-visible-disabled.png`, `after-engineer-resubmitted.png`, `after-carry-forward-queued.png`, `after-decision-4-client-approve_with_comments.png`, `after-category-labels-390.png`.

The reviewer visually inspected the actual mobile move screenshot and escaped-comment history screenshot, as well as the baseline QA workspace. Full-page screenshots and JSON receipts retain other visits for inspection.

## Limits

Browsers were headless installed Microsoft Edge, viewport emulation1366/390, not real touch hardware or mobile Safari. The observed449ms is one local synthetic run, not a production percentile or throughput guarantee. No native inference, paid web provider, real operational surveys, merge or deployment was exercised. No ten-repeat CI stability certification is claimed. Root owns final full-suite/static/frontend-script results. Final supplied frontend source hashes were independently matched in `freeze-verified.json`.
