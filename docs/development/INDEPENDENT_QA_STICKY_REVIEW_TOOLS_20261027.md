# Independent QA - fixed evidence controls and softer toolbar

Completed27 October2026, continuing the26 October task. Installed Agency Reality Checker and UX Architect profiles used. Independent reviewer owns tests/fixtures/reports, not product edits.

## Final result

- Unit plus real HTTP render contract:`core.test_qa_filter_toolbar`4/4 passed in0.367s, after3 meaningful RED failures for the missing shared wrapper. The contract requires one wrapper inside the existing photo-evidence view, filters then linking actions then category heading, existing IDs, and Engineer isolation.
- Actual saved-data browser unlink regression:`functional.cjs` / `functional.json`:26/26 passed on final product CSS/template without injected overrides. Cancel, already-linked no-POST, failed-save retry, multi-unlink, current-point priority, preserved other links/original SHA256/answers/revision, refresh and390px phone checkbox/touch action all passed. No browser JavaScript errors.
- Actual scroll proof:`sticky_browser.cjs` / `sticky-browser.json`:50/50 passed across QA1920/1366/390 and Team Lead1366. Existing evidence pane scrollTop350 moves source-photo cards by350px while wrapper, filters, link action row, category heading and evidence collections remain stationary. Element hit checks prove photo cards do not paint over the filters. There is no whole-page horizontal overflow; no new vertical scroll pane was introduced.
- Final filter tone is softer blue with dark text. The mobile action row scrolls horizontally to retain accessible actions without wrapping over the photo area. Final CSS cache token is `qa-sticky-tools-20261027-2`.
- Final scroll-test source hashes stayed unchanged during the gate; hashes are recorded in `sticky-browser.json`. Lead separately runs the complete affected backend/frontend gate.

## Bug found, repaired and retested

The first sticky version passed desktop/default scroll checks but broke actual phone multi-selection. Selecting the first photo expanded fixed controls to387.6px inside a358px pane, covering the second checkbox. This was a real functional regression, not a forced-click test workaround. `functional-first-sticky-regression.json`, `phone-probe.json` and `phone-selected-sticky-blocker.png` retain the failed evidence.

The frontend owner compacted mobile actions into one row and gave the existing mobile workspace a620px minimum. The final real pane is618px; selected controls are about263px, leaving over350px for evidence. Both checkboxes and the explicit Unlink action now work with ordinary clicks. A separate browser-injected diagnostic originally established the height cause; that diagnostic is not used by any final passing scenario.

An immediate request after restarting the isolated server initially raced Django startup. Its receipt is preserved as `functional-startup-race.*`. The full functional26 was rerun after readiness, then the separate20-check security phase ran. No skipped or incomplete journey is counted as a final pass.

## Evidence and limits

- `sticky-qa-{1920,1366,390}-before.png` and `-scrolled.png`; corresponding Team Lead1366 images.
- `qa-selected-links-1366.png`, `qa-unlink-save-failure-1366.png`, `qa-unlinked-preserved-other-links-1366.png`, `qa-unlink-phone-390.png`.
- Reviewer visually inspected the final phone selected-photo screenshot: source photos remain visible below the fixed controls, both selected and original links retained.

All operations used copied synthetic166-point/460-photo records/media on owned loopback8930. External CDNs were deliberately blocked. No model/native request, customer mutation, operational engineering approval or production deployment was performed. The previous full-suite Windows symlink privilege limitation and unrelated unapproved security findings remain outside this repair.
