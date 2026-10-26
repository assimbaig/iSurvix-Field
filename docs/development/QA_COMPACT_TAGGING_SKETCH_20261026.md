# Compact QA support, saved tagging and hand-sketch drafts

26 October 2026. Feature branch `feat/qa-photo-candidate-ranking-20261024`.
This checkpoint extends `9e849e6`; it does not merge or deploy production.

## Implemented and verified

- Photo support uses Matching / AI details / Links tabs, a candidate selector
  and one observation at a time. Desktop support content fits the viewer;
  mobile retains deliberate vertical scrolling without horizontal overflow.
- Retained suggested links are visible for older completed results without
  candidate metadata. During checklist preparation, digest-checked persisted
  mapping proposals can appear before the final result. Opening a photo can
  refresh these proposals without replacing dirty reviewer input. Progress
  distinguishes analysed evidence sources from finished checklist matching.
- Small bounded checklist catalogs retain valid synonymous points instead of
  incorrectly treating a lexical top-three shortlist as the complete catalog.
- Uploaded hand-sketch documents contribute source-referenced draft tracing
  sheets to the existing PDF/DXF export. Full source imagery is preserved;
  extracted measurements are transcribed only with recorded units/source text.
  Missing/unreadable dimensions are highlighted. PDF pages, image uploads and
  workbook embedded images are supported; unavailable geometry remains explicit.
  Register rows and warning totals include the appended sheets.

## Verification evidence

Executed before the subsequent web-reference feature:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py --verbosity 1
```

**1,085 tests passed in 361.302 seconds**, zero failures/errors/skips; isolated
database/media/model cache, zero external network attempts, 33 in-process HTTP
fixture connections. Log: `.local/qa-followup-20261026/full-suite-final.log`.
The product source fingerprint remained
`b3f443d49eed4d0124c5041b3e9c3a3a49e4f8fe3eb08717084130562f012148`.
All eight frontend check scripts, Django system check, migration-drift check,
dependency check, JS syntax and 214-file static build passed.

Independent Agency QA: **52 browser assertions**, 47 focused backend tests,
six saved-projection assertions and nine artifact assertions. Desktop 1920x1080
and 1366x768 plus mobile 390x844 were checked using isolated 166-point/460-photo
fixtures. Sources, saved revisions and original evidence bytes were preserved.
See `INDEPENDENT_QA_COMPACT_TAGGING_20261026.md` for commands and receipts.

The existing operational ZBHA993 revision 3 was inspected read-only. Its six-page
hand-sketch PDF and six retained analyses produced eight private draft sheets
with no database writes, model calls or release. The original source is not
committed. Repository samples under `samples/hand-sketch-20261026` are synthetic.

## Limits and security approval holds

The sketch output is source tracing, not semantic CAD reconstruction or verified
engineering geometry. Older retained analyses may omit visible measurements;
the source remains visible and unsupported dimensions are flagged. No scale,
concealed connection, manufacturer dimensions or engineering approval is inferred.
No new native model calls were performed for this follow-up.

Separate AppSec reproduced **C1 Low**: a retained in-progress mapping may have an
obsolete model/batch context even though its payload digest and field IDs pass.
It remains advice requiring QA confirmation. No approval bypass was established.
C1, prior M1 and older W1/S1/S2/S3/R1/R2 are held for owner approval; none was fixed.
See `SECURITY_REVIEW_QA_COMPACT_SKETCH_20261026.md`.

## Recovery and local review

Consistent checkpoint:
`F:\iSurvix\iSurvix-Field\.local\backups\project-checkpoint-20261026-135127`.
The feature preview is `http://127.0.0.1:8001/login/`, sharing existing local
records/media with distinct session and CSRF cookies. Original port 8000 and
its in-flight workers remain untouched. The private preview bootstrap is
`.local/qa-followup-20261026/live-preview/serve.py` in this feature checkout.
Use existing Windows startup scripts for the normal app/worker; do not start
duplicate workers merely to test this visual candidate.

The requested internet keyword references are a subsequent change. The test
counts above do not claim verification of that new feature.
