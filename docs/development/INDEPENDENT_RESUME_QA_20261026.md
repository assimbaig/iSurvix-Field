# Independent functional QA, 26 October 2026

Reviewed using the installed Agency Test Automation Engineer and Reality Checker definitions. This report covers actual isolated saved-data browser checks and independently executed focused backend tests. It does not certify production readiness or native inference accuracy. Separate AppSec remains required.

## Isolation and evidence

Evidence directory: `.local/qa-independent-resume-20261026/` in this candidate checkout. The SQLite database and media were copied from the established disposable `.local/qa-site-compact-20261024` fixture, never operational data. Server is loopback `127.0.0.1:8921`, candidate Python source, no worker process. Playwright uses installed Edge. Browser routing blocks external origins and model routes. Existing CDN/font requests are blocked; this is recorded separately from model attempts.

`setup_fixture.py` copied the isolated database with SQLite backup and reported integrity `ok`. `refresh_sessions.py` created sessions for only the copied fixture users. `seed_matches.py` declares its artificial persisted source analysis, two ranked candidates and generated alias; these are controlled findings, not native model output. It injects them only into the copied fixture database. `seed_home.py` adds isolated draft, returned, unstarted and another owner's task. No model requests or model downloads were performed by this review.

`preservation-proof.json` verifies all460 original photos retain their recorded SHA256 and exactly match the original disposable fixture bytes. Original photo rows and the immutable revision snapshot/digest match the source fixture. The active synthetic workflow remains SUBMITTED at quality_engineer; no approval was issued.

## Results

55 independent browser assertions passed:

- `node .local/qa-independent-resume-20261026/browser.cjs seeded`:14/14. Real166-point/460-photo state; 1920x1080,1366x768 and390x844; no horizontal overflow, contained modal, findings to the right of the photo on desktop, alias/name stability after refresh, no JavaScript exception or model request. Screenshots: `seeded-viewer-1920.png`, `seeded-viewer-1366.png`, `seeded-viewer-390.png`.
- `node .local/qa-independent-resume-20261026/journey.cjs`:17/17. Generated display alias, direct extracted object answer, both ranked candidates with relative scores/reasons, zoom, keyboard pan, Fit, two confirmed associations preserving previous associations and every answer decision, Escape focus restoration, ordinary answer saved with blank remarks/reviewer note, explicit persistence, photo navigation, no-findings manual review and refresh persistence. Screenshot: `journey-confirmed-1920.png`.
- `node .local/qa-independent-resume-20261026/home.cjs`:18/18. Exactly three Engineer cards across all three viewports, counts4/2/1 on a controlled project, project scope retained in every card URL, real pending/returned task filtering and no other owner's record. Screenshots: `home-1920.png`, `home-1366.png`, `home-390.png`.
- `node .local/qa-independent-resume-20261026/guards.cjs`:6/6. Controlled503 visibly retains answer draft; a genuine concurrent saved-data update makes stale Save retain the draft and prevents acceptance; approved section disables all matching mutations; Engineer cannot read QA state (403); no JavaScript errors. Screenshots: `failure503-1366.png`, `approved-lock-1366.png`. Fixture lock is removed in cleanup.

Each command writes its actual JSON receipt beside the scripts. Initial `baseline-browser.json` contains13 successful functional checks and one overbroad harness assertion which classified blocked pre-existing CDNs as model attempts; the corrected seeded receipt checks model routes separately. Initial seeder digest mistake correctly caused409 integrity protection and was corrected before the successful run. These were fixture/harness errors, not product failures.

Independently executed focused backend command:

```powershell
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts/run_backend_tests.py core.test_qa_matching_backend core.test_qa_matching_workspace core.test_engineer_submission_simplification core.test_engineer_home core.test_engineer_task_buckets --verbosity 1
```

Final result:56 tests passed in16.451s, zero external network attempts, zero in-process HTTP fixture connections. This includes the existing late-AI reassignment/explicit-unlink regression, supported AI links, canonical labels, original-byte intake preservation and Engineer scope integration. The first independently reproduced WIP run had49 tests and three failures (label expectation and unsupported contact links); the final current-source rerun passes. Those failures were communicated to the implementation owner and resolved there.

## Findings and limits

No remaining functional blocker was found in these checks. A cosmetic literal question mark in an earlier extracted-observations screenshot was reported to the frontend owner. The final current-server repeat (`node .local/qa-independent-resume-20261026/browser.cjs final`) passes14/14 again and records the correct heading `Extracted observations — unverified`; screenshots are `final-viewer-1920.png`, `final-viewer-1366.png`, `final-viewer-390.png`. These14 repeated assertions are not added to the55 distinct checks above. Desktop1366 and mobile390 screenshots were visually inspected, including original-file disclosure and stacked mobile panel. On mobile, the modal scrolls vertically to reach later findings/candidates.

This reviewer did not run the full backend suite, live Ollama, real survey accuracy, sustained166/460 inference, CI, merge or deployment. The root agent owns the full-suite and separately permitted native-image evidence. Security review findings are not remediated by this work. Browser data and candidates are explicitly synthetic; behavior under actual model findings is limited to the deterministic backend/source projection checks reported here.

## Addendum: restored Engineer assistant under Help

After the root agent restored an existing assistant capability that the full backend suite exposed as regressed, this reviewer restarted the isolated8921 server to load current Python/templates and independently repeated `node .local/qa-independent-resume-20261026/home.cjs`:18/18 passed again across1920x1080,1366x768 and390x844. The same scoped counts, card URLs and task filtering remain correct.

`node .local/qa-independent-resume-20261026/help.cjs` passes8/8 new browser checks. It opens the actual1366x768 global Help menu, verifies the Engineer upload-to-submit guidance and single Local assistant anchor, clicks that anchor, receives200 from `/local/assistant/`, and finds the assistant form with an empty question. QA Help has no Engineer assistant anchor. Its automatic metadata-status request is explicitly intercepted and answered with a declared synthetic503 before reaching the backend; no chat/inference request is made. Evidence: `help-browser.json`, `engineer-help-1366.png`, `engineer-assistant-reachable-1366.png`. The initial Help harness strict-selector error on QA's additional More menu was corrected to select the summary labelled exactly Help, then the complete run passed. No product files were changed by this addendum.

Total distinct browser checks are now63, with the18 home and14 viewer checks also repeated successfully after their relevant changes. Full backend suite and inference results remain owned by the root agent.
