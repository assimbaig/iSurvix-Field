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
| General Info opens a data form without photo upload/gallery controls | Actual desktop/mobile browser | In progress |
| Assigned identity/project/company/Engineer information comes from authorized system records | Django and browser prefill checks | In progress |
| Available site data and approved general scalar fields prefill; absent/conflicting information remains honest | Real records and available photo capture details | In progress |
| On-site entries, zero and deliberate blanks save and reload without being overwritten | Actual HTTP/database/browser checks | In progress |
| GET does not write; only explicit Save/Submit persists values | Database/audit comparison | In progress |
| Dirty entries survive navigation/upload refresh; failed saves retain inputs and block submission | Browser positive/negative scenarios | In progress |
| Submission saves visible data and freezes the correct revision for QA | Engineer-to-QA saved-data scenario | In progress |
| System identity, cross-project access, stale saves and submitted/approved locks remain enforced | Server negative regressions and HTTP checks | In progress |
| Photo uploads/moves use Civil/Electrical/Tower; older blank-group files remain Uncategorised and intact | Actual upload/move and source hashes | In progress |
| Existing multi-select/retry/viewer actions still work | Browser and existing regressions | In progress |
| Saved General Info reaches the existing checklist/review/output path without inventing requirement IDs | Snapshot, QA payload and actual export | In progress |
| Desktop/mobile controls remain readable, keyboard-accessible and free of clipping | Screenshots, DOM/console checks | In progress |

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
previously failed operational jobs retain their existing authorized retry action.
