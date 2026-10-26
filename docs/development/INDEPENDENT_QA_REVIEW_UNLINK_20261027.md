# Independent QA - explicit unlink and duplicate-safe linking

26 October 2026. Installed Agency Reality Checker/UX profiles were used by the independent reviewer; implementation belongs to the frontend owner. Only synthetic isolated records/media were exercised on owned loopback8930.

## Results

- New `core.test_qa_unlink_safety`:6 unit/HTTP service regressions passed in2.970s. Existing backend already implements the desired duplicate-safe and scoped-unlink behavior, so this is not claimed as a newly failing backend defect. The frontend owner separately recorded meaningful UI RED before adding the visible action.
- HTTP repeated identical photo/checkpoint links create no extra processing events or duplicate pairs; the same photo may remain validly linked to another checkpoint.
- Unit replay and HTTP multi-unlink preserve other links, all original bytes and records, immutable snapshot and human answer state. A repeat/partly absent unlink returns409 without partial writes. Approved sections and failed bulk persistence remain protected.
- An initial new test left a read stream open and caused Windows fixture teardown WinError32; the test now uses a storage context manager. The original receipt is retained; product code was not changed to hide a test error.
- Actual saved-data browser `functional.cjs` / `functional.json`:26/26 assertions passed. Two photos were seeded against two checkpoints using the existing authenticated endpoint, then tested via the real UI.
- Already-linked selected photos display a disabled **Already linked** action; a repeated native click produces no POST.
- **Unlink selected (2)** is visible. Confirmation names the checkpoint and count and says other links/originals remain. Cancel sends no POST.
- An intercepted503 failure leaves backend links unchanged, keeps both selected photos and permits retry. The subsequent real save makes one batch request for just the current point, even with a different dropdown target selected.
- Other valid checkpoint links and source SHA256 remain identical; photos with remaining links do not become Not Assigned. No accepted answer, revision or source digest changes. Reload preserves the saved unlink. Repeated unlink is disabled and produces no POST.
- Phone390px click/touch alternative is usable, with no whole-page horizontal overflow. Desktop1366 screenshot inspected: action is adjacent to existing link/move controls, checkpoint target is explicit, other links remain distinguishable.
- No browser JavaScript errors. External CDNs intentionally blocked; no native/model requests. Two server broken-pipe notices occurred when closing pages with lazy thumbnails in flight, not failed matching saves; explicit503 is the controlled negative scenario.

## Screenshots

- `qa-selected-links-1366.png`: two selected existing links; Already linked and Unlink selected visible.
- `qa-unlink-save-failure-1366.png`: honest failed-save state with retained selection.
- `qa-unlinked-preserved-other-links-1366.png`: current links gone and other associations preserved.
- `qa-unlink-phone-390.png`: touch alternative.

This is focused evidence for the new interaction, not a native-AI benchmark or universal bug-free claim. No operational survey, approval, original evidence or worker was modified by these tests.
