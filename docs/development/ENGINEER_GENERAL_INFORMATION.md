# Engineer General Info: site data and system prefill

23 October 2026. Follow-up to merged PR15, baseline
`405c5079839ae3ef23d9077c436d9ddab65f117d`, branch
`fix/engineer-general-information-20261023`.

Recovery checkpoint `.local/backups/project-checkpoint-20261023-214945` contains
2,460 source/recovery files and a consistent SQLite backup. Archive CRC and
database integrity passed. One temporary Office lock file was excluded; its
actual workbook and the other private files remain preserved.

## Requirement and ownership

The owner clarified that General Info contains site information, not photographs.
It should prefill available system data and allow information collected on site.
Reuse the existing survey, approved template fields, assignment, account/company
data, prefill logic and permissions. Do not add a separate application or new
approval/checklist-matching step for the Engineer.

Installed Agency Backend Architect owns the saved-data service and regressions;
Frontend Developer/UX Architect owns the existing Engineer template/CSS/JS;
independent Reality Checker/API Tester verifies saved-data browser scenarios.
The integration lead owns checkpoint, integration checks and release evidence.

## Verification checklist

| Expected behavior | Method | Status |
| --- | --- | --- |
| General Info opens a data form without photo upload/gallery controls | Actual desktop/mobile browser | Verified |
| Assigned identity/project/company/Engineer information comes from authorized system records | Django and browser prefill checks | Verified |
| Available site data and approved general scalar fields prefill; absent/conflicting information remains honest | Real records and available photo capture details | Verified |
| On-site entries, zero and deliberate blanks save and reload without being overwritten | Actual HTTP/database/browser checks | Verified |
| GET does not write; only explicit Save/Submit persists values | Database/audit comparison | Verified |
| Dirty entries survive navigation/upload refresh; failed saves retain entries, and QA handoff waits for a confirmed Save or submit auto-save | Browser positive/negative scenarios | Verified |
| Submission saves visible data and freezes the correct revision for QA | Engineer-to-QA saved-data scenario | Verified |
| System identity, cross-project access, stale saves and submitted/approved locks remain enforced | Server negative regressions and HTTP checks | Verified |
| Photo uploads/moves use Civil/Electrical/Tower; older blank-group files remain Uncategorised and intact | Actual upload/move and source hashes | Verified |
| Existing multi-select/retry/viewer actions still work | Browser and existing regressions | Verified |
| Saved General Info reaches the frozen QA source view; only QA-accepted answers reach the reviewed worksheet, without invented requirement IDs | Snapshot, QA payload and actual accepted-answer Excel export | Verified |
| Desktop/mobile controls remain readable, keyboard-accessible and free of clipping | Screenshots, DOM/console checks | Verified |

This change does not infer engineering values or approve work. Unknown measurements
remain unknown, approved templates and historical submissions remain retained,
and physical-device/native-AI accuracy claims require separate evidence.

## QA layout choices: proposals only

The owner also requested a simpler QA workspace and options. No replacement QA
layout has been selected or implemented as part of the site-data correction.

| Option | Main workspace | Intended use |
| --- | --- | --- |
| 1. Photo-first review (recommended) | Large photo area, compact category navigation; open checkpoint assignment and AI detail only when needed | Fast visual inspection with fewer permanent controls |
| 2. Checklist-first review | Checklist and categories together on the left; selected point's evidence on the right | Methodical requirement-by-requirement review |
| 3. Guided category review | One category at a time, followed by the existing final QA decision | A clear sequential path for occasional reviewers |

The current QA screen gains only a read-only Submitted site information dialog
so the new Engineer data is reviewable. It does not introduce template editing,
change engineering decisions or implement an unselected redesign.

## Automatic background AI

Submission creates the persistent job in the same transaction as the QA handoff.
The independent local worker polls the saved queue without requiring a QA page
to open. When idle, its polling interval is three seconds; busy/offline work
remains queued. QA can still open the task before processing finishes.

Two existing operational jobs were stopped by explicitly truncated model output.
A bounded retry now resends the identical source/schema once with a larger
completion allowance. It still rejects incomplete/malformed output; it does not
accept partial JSON or grant engineering approval. The previously failed source
`photo:418` was replayed read-only: the normal allowance truncated, the one retry
returned complete, strictly valid structured findings. Original bytes and the
immutable submission were unchanged; no result was applied to the operational
job or answers. This verifies that failure case, not an entire460-photo benchmark.

An isolated worker-before-submission test is recorded in the final evidence;
previously failed operational jobs retain existing guarded retry/resubmission
controls where their current workflow permits.

## Independent final review

The final upload-test failures were obsolete Engineer fixtures omitting a photo
category. Three valid requests now explicitly use Civil; their original
permission, duplicate, corrupt-batch, worker, stale-answer and lock assertions
remain. A regression proves omitted Engineer categories are rejected and legacy
non-Engineer inspection uploads retain their original blank-category behavior
and bytes. The independent reviewer approved this policy-preserving test change;
27 focused tests passed, with no product-policy relaxation.

An additional isolated database/media export check performed General Info save,
submission, explicit QA item acceptance and the actual Excel download. Opening
the workbook verified all18 approved field labels, zero, deliberate blank,
date/select, corrected contact/notes and canonical site ID. Engineer answers and
the immutable submission stayed unchanged; no technical approval or model call
was performed. Unaccepted reported fields correctly remained absent from the
reviewed worksheet and available in the frozen QA source viewer. Receipt:
`.local/engineer-general-info-20261023/general-info-export-result.json`.

The returned-site browser journey passed39 checks with zero JavaScript errors;
the first revision, source analyses, drawings and29 prior media hashes stayed
unchanged after correction and a second submission. The QA assistant passed two
actual browser calls/15 checks against repaired11434. Its counts were correct;
one explanation conflated missing links with section approval, so the answer
remains advisory. Server matching, confirmation and engineering acceptance are
separate operations.

## Final resumed verification

Final full run: **929 tests passed in 308.208 seconds**, native exit0, zero failures/errors/skips, identical source fingerprints.

Source SHA256: `a7f101315ee1b05ed6c39ed6fe60e6909ee9d106dfd4758cf1146fe7341e6ec0`.

The owner explicitly resumed on23October after repairing Ollama. Repaired loopback11434 reports0.40.10 with local qwen3.5:4b vision. Actual scoped QA application requests and a browser Ask action returned complete200 answers; actual synthetic image input succeeded. No new model was downloaded. Text and photo URLs are explicitly configured to that repaired runtime for this run; the launcher retains its existing project-runtime option.

The assistant now reports uploaded originals/current submission counts separately from confirmed field links. Internal QA can see Engineer-submitted General Info labelled Reported; Client context omits raw/unaccepted/private values. The assistant receives text/counts, not image pixels, and cannot approve work.

Three HTTP return lifecycles cover current routed, legacy quality and pre-GeneralInfo snapshots. A read-only inspection of the reported operational task returned all460 original photos, editable/submittable Engineer flags and the correct Engineer return stage; no records were modified by that inspection. The existing return notice now links directly to retained photos, without hiding General Info drafts or changing evidence selection.

Private receipts remain in `.local/engineer-general-info-20261023`, `.local/qa-ai-error-20261023` and `.local/qa-return-20261023`. They contain private test/session details and must not be uploaded wholesale. Final browser return and uploaded-count evidence is recorded alongside the final audit summary. Physical-device and whole-site accuracy/throughput acceptance is still outstanding.
