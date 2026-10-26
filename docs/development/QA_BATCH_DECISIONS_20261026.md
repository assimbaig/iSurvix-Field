# QA photo matching and review decisions

Candidate branch: `feat/qa-batch-decisions-20261026`, based on merged PR22
`2b05179`. Existing project permissions, immutable evidence/revisions and
engineering approval rules remain in place. The previous independent audit's
Pillow/Gunicorn/credential-ACL findings are outside this UI/workflow repair and
still require separate owner approval.

## What changed

- Selected photos drag together. Batch link/move/unlink saves through one
  bounded transaction and an opt-in compact response rather than returning the
  entire evidence package after each photo. The legacy response contract remains.
- Compact updates preserve selection, scroll, unaffected thumbnails and unsaved
  review input. Failed/stale requests keep input/selection and report failure.
- A move removes only the explicitly selected source-checkpoint links. Other
  legitimate evidence associations remain. The click/touch action provides the
  same operation as drag-and-drop; ambiguous source links require an explicit
  source choice instead of silently deleting unrelated links.
- Valid photo links carry forward automatically when an Engineer resubmits
  returned work. Original photo ID/hash and approved template/schema must match.
  Removed photos, changed sources/templates and explicit unlink decisions are
  excluded. Prior answer acceptance, completion and workflow approval do not carry.
- Already-resubmitted sites can use **More tools → Restore previous photo links**.
  This explicit, guarded QA action preserves current corrections/accepted answers
  and later unlink/reassignment decisions. It records honest origin provenance
  and reports the actual saved count, including zero eligible links.
- Category headings are16px; linked-photo counts beneath are11px desktop/12px
  mobile. Counts remain scoped to unique photos, distinct from link counts.
- Shared operational task lists use compact tables, filters and workflow badges.
  The Super Admin's existing administrative tables receive scoped compact rules.
- QA and Team Lead share the guided evidence/Decision workspace. Team Lead's
  evidence remains read-only; QA matching permissions have not been granted to it.
- Assigned QA, Team Lead and Client reviewers have Approve, Reject and Approve
  with comments at the appropriate stage. QA approval stays disabled with its
  actual explanation until the existing review requirements are satisfied.
- Decision history is an escaped compact table with actor, time, action,
  stage transition and comment. An approval containing a note is labelled
  Approved with comments, using the existing canonical approval/signature.

## Quick manual verification

1. Open the candidate at `http://127.0.0.1:8002/login/`, using the existing local
   account. It serves the real saved application/database. Review synthetic/test
   tasks when checking approvals; do not approve customer work just for a test.
2. In QA, select two photos and drag one selected card to a real checkpoint.
   Confirm both associations and counts. Choose **Move selected links** to move
   from an explicitly chosen source point; check that unrelated links remain.
3. Return a test task with a reason. As Engineer, resubmit its unchanged evidence.
   QA should see eligible retained links while AI is still queued. Required human
   answer/approval review remains outstanding.
4. On a test site resubmitted before this repair, choose **More tools → Restore
   previous photo links**. Cancel should save nothing; confirmation should show
   the actual restored count. Refresh and verify persistence.
5. Complete the existing QA evidence requirements, then open **Decision**.
   **Approve** permits an empty note; **Approve with comments** requires one.
   Rejection still requires its reason and returns only one stage.
6. Continue as the assigned Team Lead, and Client for a four-layer project.
   Verify comments in the compact history. A three-layer project closes at Team
   Lead; no Client decision is introduced for that route.
7. Open task lists on desktop/mobile for each permitted role and confirm search,
   project filtering, sorting, pagination, exports and record return context.

## Measured evidence and limits

A dense synthetic100-photo/50-observation-per-photo fixture measured a one-photo
matching response at10,408,463 bytes/77 queries/553.79ms before, versus2047 bytes/
28 queries/152.17ms for the compact path. This is a local controlled ORM/request
comparison, not real-site AI throughput or internet latency. Actual independent
two-photo browser dragging used one POST and preserved unaffected DOM nodes.

Independent browser evidence covers150 original functional assertions and15
legacy-recovery assertions, six-role responsive visits, three/four-layer permitted
approval journeys, failed saves and dirty-input preservation. Separate security
review covered28 backend tests plus three browser XSS checks; a new23-test
post-functional recovery review rechecked original attacks and new recovery
bounds. These suites overlap; do not add them as unique tests.

Before/after first-row heights: Admin/Team Lead130px to71px on desktop and146px
to73px mobile; Engineer95px to44px desktop; QA71px to44px. Admin/Team Lead rows
remain taller than40–55px because workflow information is retained. No whole-page
overflow or browser JavaScript errors appeared in the final six-role visits.

Explicit recovery scans at most20 prior revisions and restores at most2000
associations per request. Its response explains whether another request is useful.
It is a matching repair, not an engineering approval or reconstruction of evidence
that no longer matches the immutable source/template.

No native AI benchmark was needed for this change. Existing live services and the
active operational AI job were left running; candidate8002 starts no new workers.
The candidate uses separate session/CSRF cookies to keep the old local tabs intact.
Use the candidate URL when testing this branch. Canonical8000/8001 remain on their
saved release until a separate reviewed update.

## Checks, independent evidence and source ownership

The final frozen-source gate is recorded in
`QA_BATCH_DECISION_ACCEPTANCE_20261026.json`. The known Windows symlink fixture
privilege error must be reported if it recurs; it is not skipped or described as
a passed security assertion. No migration is expected from this repair.

- Backend matching: `category_intake.py`, `qa_matching.py`, batch/resubmission/
  recovery unit and HTTP integration tests.
- Review decisions: `review_route_service.py`, `review_route_views.py`, Team Lead
  context in `photo_views.py`, new comment and role/stale tests.
- Frontend: QA controller/templates/styles, shared task-table styles/template,
  shared decision/history panel, scoped shared list styles and behavioral checks.
- `INDEPENDENT_QA_BATCH_DECISIONS_20261026.md` and
  `INDEPENDENT_QA_LINK_RECOVERY_20261026.md` preserve the independent functional
  reports. Their script paths refer to private synthetic fixture evidence.
- `SECURITY_REVIEW_QA_BATCH_DECISIONS_20261026.md` and
  `SECURITY_REVIEW_QA_LINK_RECOVERY_20261026.md` preserve the separate attack review.
- Synthetic screenshots are in `screenshots/qa-batch-decisions-20261026/`.

## Windows candidate startup

The existing environment is `F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe`.
Restart only the candidate web preview with its saved private bootstrap, after
checking port8002 ownership:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' 'F:\iSurvix\iSurvix-Field\.local\wip\.local\qa-batch-decision-20261026\live-preview\serve.py'
```

Normal application/worker startup remains `Start-iSurvix.cmd` in the reviewed
checkout, with the existing installed local model/configuration. Do not start a
second worker set merely to view this candidate, or replace operational data with
the isolated browser fixture. No merge or production deployment is authorized.
