# Compact QA Site Information

24 October 2026. User request: reduce the long Site Information interface while
retaining every required field. Scope is the existing QA Site Information step;
photo review, workflow rules, evidence, templates and permissions stay governed
by their existing services.

Pre-edit checkpoint: `.local/backups/project-checkpoint-20261024-154811`, based
on clean `03b5eed`. Consistent SQLite snapshots, archive CRC and Git bundle passed.
Agency Frontend/UX owns the presentation and unit tests; independent Agency QA
owns browser verification; separate Agency AppSec review follows functional
verification. Existing security findings are not authorized for remediation.

## Baseline and TDD evidence

Independent QA used an isolated saved submission with72 Site Information rows,
including56 additional required fields from its approved synthetic template.
The executed red browser check reproduced four visible columns instead of the
requested compact three-column default. Baseline table heights were4263px at
desktop1440 and6718px at mobile390; median rows55px and86px respectively.
The baseline required seven/fifteen internal viewport passes. These are synthetic
layout measurements, not site-data or native-model benchmarks.

Private evidence: `.local/qa-site-compact-20261024`. No operational records or
model requests are used by these tests.

## Acceptance checklist

| Expected behavior | Verification | Status |
| --- | --- | --- |
| Every row, stable field ID, required flag and value remains accessible | Saved API versus real rendered DOM | Verified |
| Two compact Field/Value pairs (four columns) with original-source comparison | Unit and desktop/mobile browser checks | Verified |
| Materially less vertical scrolling without unreadable controls | Same-fixture before/after dimensions and screenshots | Verified |
| Required/missing fields clearly identified | Empty/zero/false/required fixtures | Verified |
| Edit/Save/Cancel/Confirm, dirty edits, failures and refresh remain safe | Real saved-record browser journey and existing integration checks | Verified |
| Source/system/approved fields retain their locks | Existing strict API tests and browser controls | Verified |
| Separate security review and any findings reported without silent fixes | Independent Agency AppSec review; findings remain approval-pending | Verified |

Initial compact table height fell from4263px to2565px on desktop (**39.83%**) and6718px to
3046px on mobile (**54.66%**). All72 rows remain. The bounded table uses five
internal viewport passes on desktop instead of seven, and fourteen on mobile
instead of fifteen, with substantially less outer-page scrolling. This retains
readable fields rather than hiding required data.

The dedicated compact-layout and saved-data runs passed21+18 browser assertions.
The expanded workspace's final run passed1,040 backend tests and175 browser
assertions. Current commands, screenshots, scope limits and the separate security
report are in `QA_REVIEW_WORKSPACE_20261024.md`. Earlier1,030-test results remain
historical. W1 and earlier security findings are not fixed; verified here means
the requested review was performed, not security acceptance.

## Four-column follow-up

The later user correction replaces the initial three-column table with two
Field/Value pairs per desktop row and a subtle center divider. All72 saved fields
remain in their original order and each has its own stable row/cell identity and
Edit/Save/Cancel/Confirm controls. Submitted values and provenance remain
available inside each paired value cell when comparison is enabled. At390px the
pairs stack vertically instead of squeezing four columns. On the same saved
fixture the table is1484px tall versus2565px before this follow-up (**42.14%
shorter**). The independent saved-data browser run passed15/15 checks, including
edit failure recovery, persistence, mobile overflow and all72 field identities.
Screenshots: `output/screenshots/qa-site-compact/site-paired-four-columns-1440.png`,
`site-paired-inline-comparison-1440.png`, and `site-paired-stacked-390.png`.
