# Fixed review controls and easier unlinking - 27 October 2026

The shared QA/Team Lead view keeps filters, linking actions, category heading,
collections and brief guidance fixed above the evidence. Linking actions sit
immediately below the softer blue filter bar. Evidence scrolls in the existing
pane. General Info still hides photo-only tools and shows its own information.
Admin/Client retain their separate permitted gallery; Engineer retains upload.

Select photos to use **Unlink selected (count)** beside Link/Move. At a selected
checkpoint it removes only links to that point; category view uses the explicit
checkpoint selector. Confirmation names the point/count. Original files, other
valid links, selection and unsaved review input remain intact. Failed saves leave
the state available for retry. Unlinking never deletes a source photo or accepts
an engineering answer.

**Already linked** disables duplicate confirmation for a photo/checkpoint pair.
Mixed selections send only pending pairs; AI suggestions can still be confirmed.
Existing legitimate links to different checkpoints are preserved. This is not a
new global one-photo/one-checkpoint policy. Backend duplicate and lock protections
already existed; no API, schema, permission or approval-policy change was needed.

## Verification

- Agency Frontend Developer/UX implementation and independent Reality Checker
  testing followed repository TDD. Missing unlink/toolbar-order/selected-mobile
  tests were executed RED before their changes. Six added backend service unit/
  HTTP regressions were already GREEN because the server behavior already worked.
- Final affected backend suite:41 passed, zero failures/errors/skips. All19
  frontend scripts passed using installed Edge. Django/migration checks passed.
  Final source hashes stayed unchanged while the gate ran.
- Final actual saved-data browser:26 unlink checks and50 sticky-layout checks
  passed on isolated records, including phone selection, failure/retry, persisted
  links, preserved originals and unrelated links, and pinned controls on scroll.
  These checks overlap and are not a unique total.
- Separate post-functional AppSec:20 focused assertions passed; no new exploitable
  finding established. Wrong-role valid-CSRF, foreign project, stale identity,
  approved locks, repeat links and already-removed links remain protected.
  No exhaustive fuzzing, production DAST or native-AI benchmark was performed.

Independent QA found a real phone regression: selected actions expanded the
sticky tools above the entire358px evidence pane. The repair uses one touch-
scrollable horizontal action row and a620px mobile workspace minimum. Normal
photo checkbox clicks then pass with no injected overrides or forced clicks;
the selected header is about264px in a618px pane, leaving evidence space. The
initial failure/probes remain in private evidence. No new vertical scroll area
was added. Separate AppSec ran again after the functional repair.

The earlier full backend suite's Windows symlink privilege fixture error remains
disclosed; this focused follow-up does not claim a newly green full suite.
Prior unrelated security findings remain unapproved and untouched.

## Files and testing

Product: QA template, `qa_quick_review.css`, `qa_evidence_review.js`. Tests: new
`test_qa_unlink_safety.py`, existing toolbar render test, new bulk-unlink frontend
check, strengthened existing batch and toolbar checks, and the controller harness.
Reports and screenshots accompany this document; acceptance JSON lists commands.
JS cache token `qa-unlink-20261026-1`; CSS `qa-sticky-tools-20261027-2`.

Open http://127.0.0.1:8002/login/ and press Ctrl+F5. Select a checkpoint and two
photos, check Already linked, click Unlink selected, inspect the confirmation and
save. Other valid links must remain. Scroll: controls/category should stay fixed.
On phone swipe the compact action row horizontally for the remaining actions.

At the owner's request, old app ports8000/8001 were closed. Only the updated web
preview remains on8002; loopback model11435 and existing worker process IDs were
preserved. The original launcher was stopped before web children to avoid its
finally block terminating the active independent workers. No worker/model restart,
inference request or operational approval/recovery was performed.

Source/base/data checkpoint: `.local/backups/project-checkpoint-20261026-233722`,
including verified source ZIPs and consistent SQLite backup. Draft PR23 remains
for review; no merge or production deployment.
