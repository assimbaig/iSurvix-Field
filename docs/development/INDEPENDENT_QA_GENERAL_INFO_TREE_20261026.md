# Independent QA: General Info, checklist tree and category gallery

26 October 2026. **70 browser assertions passed; six independently executed backend integration tests passed.** No unresolved functional defect was found in this bounded scope. This report does not certify deployment or replace the separate security review.

QA followed the installed Agency Test Automation Engineer and Reality Checker definitions. Ownership was limited to isolated scripts, fixtures, evidence and this report. Product changes belonged to the frontend/backend owners. Baseline was commit `feb0649`; its complete templates/static files were archived before implementation, then served from an isolated baseline directory.

## Isolation and evidence

Private work: `.local/qa-general-info-tree-20261026/`. Database/media were copied from the previous synthetic QA fixture, never from an operational survey. The saved workspace contains 166 approved checkpoints and 460 original synthetic photos: Civil 40 points/200 uploaded photos, Electrical 160 photos, Tower 100 photos. Only owned loopback port 8921 was used. No worker, Ollama, external provider or native inference call was made.

`before-browser.json` records five meaningful RED assertions against the archived baseline: the review pane was always open; categories/groups/sections began open; bottom collections occupied the left pane; independent numeric photo badges were absent; General Info jumped to the Site Information step. The implementation then passed these requirements against the actual Django saved-data page.

## Independent results

| Script / receipt | Passed | Coverage |
| --- | ---: | --- |
| `checks.cjs` / `checks.json` | 23 | Default two panes; optional drawer closed; fresh collapse; collections moved; central read-only General Info without POST; all 40 Civil groups including zero-link points; bounded scroll loads 200 unique uploads; no gallery pager; globally unlinked pool last; linked-elsewhere source retained; duplicate-card selection synchronized; drawer Escape |
| `flow.cjs` / `flow.json` | 16 | Actual assignment POST, badge 1 and reload, no answer acceptance, source guard unchanged, removal from unlinked; controlled 503 preserves count/selection and creates no link; separate Site Information cell save/reload; saved correction in summary; desktop/mobile overflow checks |
| `boundaries.cjs` / `boundaries.json` | 11 | Explicit expansion memory; search reveals without persisting expansion; drawer focus return and unsaved draft retention; photo viewer Previous/Next; continuous AI findings; mobile General Info and no page overflow |
| `edge.cjs` / `edge.json` | 8 | Explicitly controlled HTTP response: submitted numeric 0, boolean false, missing value, duplicate original/crop physical ID counted once, suggested versus confirmed. Actual Team Lead page: editors absent, linking not enabled |
| `final-gallery.cjs` / `final-gallery.json` | 5 | Latest source: upload-category label retained, 200 unique photos via scrolling, All photos retains other-category unlinked pool, current pool remains last, mobile no page overflow |
| `reject.cjs` / `reject.json` | 7 | Separate copied database with queued 0/460 job and no final result: incomplete review cannot approve, whole-task rejection available and succeeds, no point-review/approval mutation, Engineer returned task and protected original download |

The 70 count includes five explicitly controlled response-rendering assertions and the controlled 503 response. These are not native-provider results. Ordinary saved Django data and actual mutation endpoints were used for the remaining flows. The fixture's original General Info values are missing; unverified AI proposals of 0/false were deliberately not presented as accepted submitted values. Controlled submitted 0/false tests cover renderer semantics without modifying the frozen source revision.

Actual links were saved for photo 37 to `civil_033` and independently photo 39 to `civil_035`. Each produced one confirmed unique-photo badge and persisted across reload. Photo 38 to `civil_034` was deliberately failed with HTTP 503; no saved link/count increase occurred, and the photo stayed selected. A repeated original/crop physical photo ID counted once, with the aria summary showing zero confirmed and one suggested. Category aggregate counts remained independent of review status. Photo 4, uploaded under Civil but linked under Electrical, stayed visible with its original upload label and was excluded from the globally unlinked pool.

The separate Site Information editor successfully saved the synthetic contact through the existing real endpoint. Reload retained it and the central General Info table displayed it as a saved QA record. Merely opening General Info made no mutation. Closing/reopening the optional point drawer retained an unsaved draft, and Escape returned focus to its trigger.

## Backend and task rejection

Independently executed from the candidate worktree:

```text
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts/run_backend_tests.py core.test_qa_task_reject_without_photo_review
Ran 6 tests in 2.120s — OK
zero external network attempts
```

Browser rejection used **separate `reject.sqlite3`**, copied from the synthetic QA database. Explicit fixture preparation removed its copied final result and set its existing job to queued, completed 0/460. No model ran. The actual Decision form returned HTTP 200, the task became `REJECTED`, the recorded route moved to `engineer`, and the job remained queued at zero. Approval remained unavailable while incomplete. The only mutation from that browser flow was the task rejection. Engineer access to an original returned HTTP 200 with identical SHA-256. `reject-data.json` independently confirms the final status, absence of result, unchanged frozen revision, 460 identical photo records and all original hashes.

## Preservation and limits

`preservation-proof.json` checks all 460 original files against both their recorded SHA-256 and the prior synthetic source fixture. All bytes, photo filenames/records, frozen snapshot and revision digest are unchanged. The deliberate QA contact correction and confirmed links are review events, not source-evidence edits. No human approval was granted. No product files were edited by this QA agent.

The browser used installed Playwright with Microsoft Edge at 1366×768, 1920×1080 and 390×844. The saved-data workflow and mobile overflow were exercised; this is not a claim of exhaustive accessibility, all-role release policy, or the separate new all-page header task. Team Lead uses its existing read-only variant rather than the guided QA-only DOM. Six sanitized screenshots were opened and visually inspected before copying below.

Harness corrections were kept distinct from product findings: initial search used a field ID rather than its displayed label; an assertion used `link.status` instead of actual `link.state`; the intentional dirty-draft test required a fresh page before unrelated mobile navigation; role-specific guided controls were absent on Team Lead by design; redirected decision response bodies could not be reread after navigation, so rejection was verified through its status and persisted database state. Final receipts above have no failures/fatal errors.

At report completion the rejection fixture server was stopped after verifying its command, and the primary owned synthetic 8921 fixture was restored for the parent-requested separate header QA. Private cleanup evidence: `reject-server-cleanup.json`. Main application 8000, parent-owned preview 8001 and model 11435 were not changed by this QA work. Final server shutdown will be recorded separately when the parent releases the shared fixture.

## Screenshots

- [Before: left footer, default open tree and permanent third pane](screenshots/qa-general-info-tree-20261026/before-tree-1366.png)
- [Before: General Info jumps to editing step](screenshots/qa-general-info-tree-20261026/before-general-info-1366.png)
- [After: centre General Info with saved QA correction](screenshots/qa-general-info-tree-20261026/after-general-saved-1366.png)
- [After: grouped category gallery, desktop](screenshots/qa-general-info-tree-20261026/final-category-1366.png)
- [After: category gallery, mobile](screenshots/qa-general-info-tree-20261026/final-category-390.png)
- [After: central General Info, mobile](screenshots/qa-general-info-tree-20261026/after-mobile-general-390.png)
