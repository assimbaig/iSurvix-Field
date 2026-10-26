# Independent QA - compact evidence filter toolbar

26 October 2026. Installed Agency Reality Checker and UX Architect profiles read.
Reviewer owns tests/private fixtures/reports only; no product implementation edits.
The owner's added requirement puts the blue/navy filterbar ABOVE the category heading.

## Result

- Backend unit plus real HTTP integration:4 tests passed in0.489s. Initial missing-bar and later ordering RED runs each failed3/4 before implementation; Engineer isolation passed. `backend-red-final.log`, `backend-order-red.log`, `backend-order-green.log` retain receipts.
- Saved-data Chromium/Edge functional journey:`functional.cjs` / `functional.json`:92/92 assertions passed across15 role/viewport visits,0 JavaScript errors and0 failed local application requests. The isolated fixture has166 checklist points and460 photos.
- Actual search removes/restores thumbnails; Unassigned includes only photos without saved links; confirmed filtering agrees with saved links; thumbnail size changes real gallery; QA dirty answer DOM node/value and selected-photo count survive filters and keyboard refresh. Filters do not POST review decisions or matching changes.
- General Info retains its own header/table and hides photo-only toolbar/header/collections. QA and Team Lead share the redesigned panel. Admin/Client retain their existing compact legacy evidence interfaces; Engineer retains category upload without QA controls. The Client is tested on permitted released fixture14; un-released fixture5 correctly denies access.
- Final frozen-source visual gate:`final_visuals.cjs` / `final-visuals.json`:65/65 checks,15 role/viewport visits,0 JavaScript errors, source hashes unchanged. Widths1920,1366,390; QA/TL toolbar40px desktop,47px collapsed mobile; filters precede category heading and match actual interface header colours. No whole-page horizontal overflow.
- Final actual theme is rgb(20,43,70) background / rgb(242,246,252) ink, inherited from existing app appearance. Fallback palette is not hard-coded as the expected real theme.

Before screenshots use frozen committed1713e68 source on private8931 with the same isolated records. After screenshots `final-qa-1920.png`, `final-qa-1366.png`, `final-qa-390.png`, corresponding Team Lead/Admin/Client/Engineer images are final viewport captures. Reviewer visually inspected finalQA1366 and390: top navy filters, category beneath, useful evidence space, phone Filters disclosure.

## Honest limits and harness corrections

External CDN font/bootstrap/leaflet requests are deliberately blocked by browser isolation and separately recorded in `intentionallyBlockedExternal`; no model or external application request was allowed. Existing local navigation/toolbar styles supply the reviewed layout. No production approval, original evidence mutation, model request, AI throughput test or operational matching repair was performed.

Intermediate harnesses initially measured an intentionally hidden photo-scope select, expected a scope control before selecting a point, counted deliberately blocked CDN requests as application failures, and hard-coded fallback instead of actual theme colours. Original receipts remain private; fixes used actual visible controls and actual role/theme contracts, without product edits or forced pointer clicks. Refresh pointer interception after Playwright's long auto-scroll was not reproducible on fresh baseline/candidate pages (`refresh-probe.json` both mouse clicks passed); dirty-input refresh used ordinary keyboard focus/Enter. This is not evidence of a fixed pointer-navigation defect.

This verifies the scoped layout and existing filter behavior, not a full native-AI or production acceptance claim. Root's focused35-test/18-frontend gate is independently recorded by the lead; older full-suite Windows symlink-privilege limitation remains unchanged.
