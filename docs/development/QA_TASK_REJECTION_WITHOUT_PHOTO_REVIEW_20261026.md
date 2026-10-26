# QA whole-task rejection without photo review

26 October2026. Backend verification for the owner's simplified photo workspace.
Used the installed Agency API Tester instructions and repository TDD/isolation
rules. Ownership: the new focused regression file and this report only. No
backend service, model, permission, approval policy or operational data changed.

## Finding: existing rejection behaviour already meets the requirement

`review_route_service.route_context` permits the assigned QA reviewer to reject
in the review stage independently of `qa_review_required`. `act_on_route` applies
the completed-QA-package and engineering checks to **approve/clarify**, not to
**reject/return**. A reason and current route token are still required.

The actual CSRF-protected `review_route_action` endpoint can therefore return a
whole task to its assigned Engineer while AI is queued/running and with no
`qa_answer`, `qa_link`, `qa_complete` or technical-approval event. The Engineer
receives the original categorized photos and correction reason, can edit the
returned task, and can resubmit a new source revision.

The backend has no mandatory per-photo reviewed flag in this path. Required
checklist-point acceptance is a separate approval condition: the existing
`category_intake.missing_for_review` and `require_qa_complete` rules still apply
when QA attempts an engineering approval. This UI request does not silently
remove that control or turn a photo link into an acceptance.

## New real-HTTP regression coverage

`backend/core/test_qa_task_reject_without_photo_review.py` adds six tests:

1. Unreviewed queued submission rejects successfully through the actual JSON
   decision endpoint, even while required checklist review is incomplete.
2. Active AI does not block rejection or reset its saved progress counters.
3. Completed raw analysis and the result survive return and unchanged Engineer
   resubmission; the old snapshot/digest/files remain intact and repeated submit
   does not duplicate the new revision/job.
4. Missing rejection reason and stale request token fail without recording a
   decision.
5. Engineer, Team Lead, Client, Admin, unassigned/foreign QA and missing-CSRF
   requests cannot perform the assigned QA rejection.
6. Repeated rejection creates only one return event, while an incomplete
   engineering approval remains blocked.

All tests use actual Django records, upload/download routes and isolated media.
The three uploaded photo categories are Civil, Electrical and Tower. After
return, every original download is compared byte-for-byte with its pre-submit
source. No approved operational record or customer media was used.

## Executed checks

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py core.test_qa_task_reject_without_photo_review --verbosity 1
```

**6 passed in3.312s**, zero external attempts or HTTP-fixture connections.
These tests passed on the existing services; no failing product behaviour was
reproduced and no artificial RED or implementation fix is claimed.

Related rejection/returned-evidence/model-reuse regressions:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py core.test_qa_task_reject_without_photo_review core.test_engineer_returned_site core.test_survey_model_identity core.test_measurement_unit_worker_pin --verbosity 1
```

**33 passed in10.054s**, zero failures/errors/skips, zero external attempts and
zero HTTP-fixture connections. Two logged processing errors are expected
negative-case fixtures in the existing model tests; the suite completed OK.
Private execution log: `.local/qa-task-return-20261026/regressions.log`.

## Limits

This establishes the saved rejection/resubmission contract and retention of old
analyses. It is not a new native-model throughput or extraction benchmark. No
Ollama request, worker restart, production load test or deployment was performed.
Frontend layout, category badges and the independent security review remain
separate responsibilities. Earlier approval-held findings were not modified.
