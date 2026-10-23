> Historical PR15 evidence. The General Info site-data correction and repaired Ollama11434 verification in `ENGINEER_GENERAL_INFORMATION.md` supersede the older photo destinations and runtime diagnosis below. Historical test counts are not current totals.

# Engineer photo selection and bulk category move

23 October 2026. Follow-up to PR15 on
`fix/engineer-category-qa-intake-20261023`, starting at `dac8d6c`.
Recovery checkpoint: `.local/backups/project-checkpoint-20261023-212618`;
1,729 source/recovery files, archive CRC and database integrity verified.

The owner requested multiple-photo selection beside the Engineer viewer's
`1 / n` counter and moving selected photos between existing categories.

## Scope and ownership

Reuse the existing Engineer capture route and category endpoint. No new modules,
models, categories, AI steps or approval behavior. Engineer selection is available
only before submission or following an authorized return. Original bytes and
historical photo relationships remain retained.

Installed Agency Frontend Developer/UX Architect profiles own the existing
`engineer_capture.html/css/js`. Backend Architect owns the category service and
bulk regression tests. Independent Reality Checker/API Tester verifies the actual
saved-data desktop/mobile journey with isolated databases/media. The integration
lead owns checkpoint, checks, preservation, documentation and Git delivery.

## Acceptance evidence

| Requirement | Verification | Status |
| --- | --- | --- |
| Select several saved photos from thumbnail checkboxes | Real browser, exact saved IDs checked | Verified |
| Select the current photo beside the viewer counter; selection survives next/previous | Desktop and mobile viewer, before/after storage checks | Verified |
| Select all, clear selection, shared selected count and existing category choices | 41 saved photos, 36 rendered, collapsed group; all41 moved and selection retained after refresh | Verified |
| Move the entire selection in one authenticated atomic request | HTTP/database regression and browser request count/refresh | Verified |
| Preserve selection and prior categories when saving fails | Controlled503; modal refresh/retry and actual stale409 recovery | Verified |
| Reject foreign/excluded IDs, invalid categories and stale requests without partial writes | Actual Django regressions, mixed-foreign/missing404 and wrong-role403 browser requests | Verified |
| Retain submitted locks, source bytes and single-photo compatibility | Django regressions, actual submitted viewer and source hashes | Verified |
| Usable desktop/mobile controls without clipping; pending uploads remain distinct | 1440x1000 and390x844 browser screenshots, native checkbox/touch and console | Verified |

## Executed verification

- Final full backend suite: **903 passed in313.992 seconds**, native exit0,
  no failures/errors/skips. Source fingerprint remained unchanged throughout:
  `279c27ca72c891f2d7b9f67ce10e61bda32f42d3af10391b47a899a16f3d4d0c`.
- Nine new bulk HTTP regressions plus related existing intake tests:34 passed.
  Includes an actual group update followed by an injected database audit failure;
  the enclosing transaction restored all groups and left no audit or partial move.
- Independent actual Edge scenarios:53 desktop,53 mobile and14 lazy-thumbnail
  assertions; no unhandled JavaScript errors. These overlap other checks and
  are not added to a unique test total. Touch was emulated, not a physical phone.
- Django checks, migration drift/pending checks, pip check, all four retained
  frontend scripts, changed JavaScript syntax and diff checks passed.
- Browser tests used isolated saved Django records/media and actual authenticated
  HTTP operations.503 was deliberately injected for the failure test. Stale,
  foreign-ID, unauthorized and post-submission requests reached the real server.
  Two synthetic jobs were left queued; no native AI inference was invoked.
- One private mobile driver initially checked incoming HTML before its JS/state
  loaded. Waiting for the new document and state hydration fixed that harness
  race; the original persistence assertion then passed unchanged. Product code
  was not changed or errors suppressed to make the check pass.
- Original archived media/private files and existing photo file/hash/task
  references remain intact. Operational uploads/category edits continued while
  isolated testing ran; added photos, audited group changes and their related
  upload/search/audit records were preserved rather than rolled back. No
  operational approval was performed by these tests.

Commands from the project root:

```powershell
.local\venv\Scripts\python.exe scripts\run_backend_tests.py core.test_engineer_bulk_categories core.test_engineer_category_submission_acceptance core.test_category_intake_regressions
.local\venv\Scripts\python.exe scripts\run_backend_tests.py
node --check backend/static/core/js/engineer_capture.js
```

Private raw receipts: `.local/engineer-bulk-move-20261023`. Current screenshots:
`output/screenshots/engineer-bulk-categories/desktop_final-*`, `mobile_final-*`
and the41-photo lazy-selection screenshot. Fixture accounts/session data are
private and are not part of Git delivery.

## Test procedure

1. Engineer opens an editable assigned task and uploads several photos.
2. Select two thumbnails, or open a saved photo and select it beside `1 / n`.
   Navigate to another photo and select it too.
3. Choose Civil, Electrical, Tower or General Info and use Move selected.
4. Refresh and verify all selected photos have the saved category; unselected
   photos retain theirs. Select all/clear operate on saved photos.
5. Submit to QA after uploads finish. Photo-selection/category mutation controls
   are unavailable for the frozen submission.

Native AI is not invoked by selection or category moves. This focused change does
not claim new native-model accuracy, throughput or physical-device acceptance.
