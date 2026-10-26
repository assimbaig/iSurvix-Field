# Separate AppSec review: QA General Info and grouped gallery

26 October 2026. Reviewed the General Info/tree/gallery UI additions after
`2d4590fc46f54303b6f9e9d913a2adf7de340526` on
`feat/qa-photo-candidate-ranking-20261024`: central read-only General Info,
collapsed/persisted tree, unique-photo badges, optional point-review drawer,
grouped evidence and bounded lazy thumbnail loading. Actual AGENTS.md, current
handoff/development rules and the installed Agency AppSec profile were used.
Product source remained read-only. Concurrent shared-header/navigation work is
excluded pending its separate final review.

**One new Low provenance finding, G1, is reproduced. No new Critical, High or
Medium issue was established. No finding was fixed. Owner approval is required
before remediation.** Existing C1/M1/W1/S1/S2/S3/R1/R2 remain under their own
approval holds. WS1's separately approved repair remains effective in the tested
cases; no other repair approval was inferred.

**Subsequent explicit owner-approved G1 repair passed independent reattack. G1
is resolved for the reproduced mapping-only provenance issue.** Original finding
and failure receipts below remain historical evidence; see the closure appendix.

## G1 - Low: mapping-only provenance promotes an unaccepted AI value in General Info

Locations: `backend/static/core/js/qa_evidence_review.js`,
`generalInformationRows()` lines54-60; existing provenance producers in
`backend/core/category_intake.py`, `review_action()`, and
`backend/core/qa_site_information.py`, `table()`.

The new read-only General Info view treats `row.reviewed_by` or `item.qa_by` as
proof that the **value** was saved by a human. The existing compatibility `map`
action records `qa_by` for a photo-location decision without changing or accepting
the answer. The site-information projection derives `reviewed_by` from that
marker too. Consequently a source-link decision can cause the central General
Info table to show the still-unaccepted AI answer as `Saved QA correction`.

Actual isolated reproduction:

1. Submit synthetic source photos and save a high-confidence manufacturer
   proposal, `AI_VALUE_WITHOUT_HUMAN_ANSWER`, against a real General Info field.
   Its submitted Engineer value is empty.
2. Read actual QA state: the new General Info projection correctly uses the
   empty submitted value, suppressing the unaccepted AI proposal.
3. POST the existing authenticated `map` action for that field/photo, with a
   reason explicitly stating only the source location was checked.
4. Feed the resulting actual QA-state response to the real frontend controller.

Observed: the table's value becomes `AI_VALUE_WITHOUT_HUMAN_ANSWER`, labelled
`Saved QA correction`. The actual saved item still has `accepted=false`, and
there is **no `qa_answer` event**; only `qa_mapping` was recorded. The assertion
that mapping alone must not replace the submitted value fails.

Impact: the new factual General Info summary misattributes an AI proposal to a
human and may mislead later review. An authorized QA compatibility mapping action
or equivalent retained mapping history is required. The current `confirm_link`
flow does not itself create this marker. No human acceptance, engineering
approval, original-source write or role escalation occurred; severity is Low.
This is distinct from earlier M1 (empty-observation suggested links) and C1
(obsolete in-progress mapping context).

Recommendation, **pending explicit owner approval**: distinguish answer/value
provenance from link-mapping provenance. Use explicit saved value/answer evidence
such as `qa_value_by` or a verified accepted `qa_answer` overlay, rather than
`qa_by`/`reviewed_by` alone. Preserve intentional human blank/zero/false values.
Add the real legacy-map regression alongside ordinary answer and link-only
confirmations. Preserve historical events; do not rewrite earlier human records.

## Executed evidence and successful boundaries

Private directory: `.local/security-qa-general-gallery-20261026`.

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' .local/security-qa-general-gallery-20261026/run_backend.py
node .local/security-qa-general-gallery-20261026/frontend-security.cjs
```

**Two new saved-data backend probes completed in0.976 seconds, native exit0.**
One deliberately records the undesired mapping-only state for the frontend
security assertion; its success is reproduction evidence, not a claim G1 is safe.
The second verifies permitted photo original/preview downloads return200 while
photo IDs belonging to another checklist return404. Original application storage
and records were isolated by the ordinary runner.

**Nine new frontend security assertions: eight passed, one failed (G1), native
exit1.** Full receipts: `backend-reproduction-final.log`,
`mapping-only-state.json`, `frontend-security-final.json`; source/scripts:
`backend_cases.py`, `run_backend.py`, `frontend-security.cjs`.

Successful attacks/guard checks:

- Explicit human blanks, zero and false stay intact rather than falling back to
  older submitted or AI values. Hostile submitted labels/values remain text-only
  General Info cells, with no active HTML insertion.
- Duplicate int/string photo references and a foreign photo ID do not inflate
  checkpoint unique counts or create a foreign gallery card. Link-count display
  does not change the underlying `accepted=false` state.
- The true unlinked group stays last and excludes photos linked to another
  approved point. Cross-category relationships retain their existing scope.
- Refusing dirty-input discard prevents the General Info context switch and
  preserves the unsaved text. Opening the optional review drawer cannot give a
  read-only, locked state editing authority.
- A100-photo controlled category initially renders36 lazy thumbnails; an observed
  scroll sentinel adds24, reaching60. Original-file URLs are not eagerly loaded;
  an injected external preview URL is rejected by the same-origin URL helper.
- Original WS1 obfuscated loopback forms stay blocked and a legitimate public
  manufacturer URL stays accepted.

**27 existing backend guard tests passed in11.490 seconds**, native exit0:
QA matching, whole-task rejection without per-photo review and Client exclusion
of removed source originals. They include stale writes, source/target locks,
review/approval separation, unassigned/foreign QA denial, CSRF, frozen originals
and retained-analysis preservation. Receipt: `backend-guards.log`.

**Four existing frontend suites passed149 assertions**: navigation/gallery15,
workspace47, guided-state58, web-references29. Their JSON receipts are retained
privately. These existing checks overlap functional QA and should not be added
twice to unique acceptance coverage.

All backend runs used temporary database/media/model caches, with **zero external
network attempts and zero native-model requests**. No operational task was
rejected, resubmitted or approved. No app, model worker or existing QA fixture
service was modified. Only this report and private probes/receipts were written.
Exact reviewed QA JS/template/CSS and provenance-source hashes are retained in
`source-hashes.json`.

## Limits

The new badges and gallery are presentation projections; malformed response
probes do not prove an attacker can write such rows through the guarded API.
No claim is made that arbitrary malformed JSON is accepted operational data.
This reviewer did not execute the other agent's70 browser checks, measure actual
gallery layout, test physical-device focus/scroll, run a load campaign or verify
native-model accuracy. The new rejection tests confirm the existing route's
return behavior without weakening its distinct engineering-approval checks.
Shared global navigation changes were still owned by another worker and are not
certified by this report until a separate stable-source addendum is recorded.

## G1 owner-approved repair and independent closure - 26 October 2026

The owner explicitly approved the narrow General Info value-provenance fix, as
conveyed in the instruction `Owner explicitly asynchronously approved G1 fix now`.
The implementation agent changed only the new General Info projection and its
tests; this reviewer edited no product source. No approval for the older Site
Information projection, backend changes or other held findings was inferred.

Actual final code requires the item to carry `qa_value_by` or `accepted===true`,
plus a present saved value. Link-only `qa_by`/`reviewed_by` markers no longer
promote an AI proposal. Presence checks preserve intentionally empty values.

Independent closure evidence:

- The original real HTTP `map` response now renders the frozen empty Engineer
  value rather than `AI_VALUE_WITHOUT_HUMAN_ANSWER`; its status stays submitted
  information. The unchanged backend item remains unaccepted and has no answer
  event. Original failed JSON receipts remain retained.
- Added a second actual saved-data sequence: an Engineer submits a nonempty
  original, then QA explicitly saves an empty answer with `preserve_evidence`
  (`qa_value_by`) and later a legacy `None` answer (`qa_by` plus accepted=true).
  Both real responses retain those human blanks against the older nonempty
  source. Fixtures are in `qa-answer-states.json`.
- **All ten independent frontend security assertions passed**, native exit0,
  including the original nine and the real-answer positive case
  (`g1-reattack.json`). Source blanks, zero and false, hostile text, photo scope,
  lazy bounds, dirty/read-only guards and WS1 negatives still pass.
- **Three saved-data backend probes passed in1.279 seconds**, native exit0
  (`g1-answer-provenance.log`): original reproduction capture, protected source
  membership and real human blank/None answer capture.
- Expanded WS1 checks again passed31 unsafe URLs, five public URLs and both
  unsafe-anchor cases (`ws1-expanded-final.json`). Four final frontend suites
  passed18+47+58+29 assertions (`g1-final-*.json`).

G1 status is resolved for the demonstrated issue. Other held findings remain
unchanged. Final source hashes, including the shared-header files subsequently
reviewed, are in `final-source-hashes.json`; initial hashes remain preserved.

## Stable shared-header follow-up

After the navigation worker reported its files frozen, independently reviewed
the shared CSS/template role branches and query escaping. Three new template
security checks plus six existing header tests passed9/9 in0.867 seconds. Link
text/destinations match the committed role-specific baseline, hostile query
values cannot escape into attributes/tags/external authorities, and Profile does
not falsely claim an active review/admin location. No new authorization route
or role capability was introduced.

Also executed actual authenticated Edge/Playwright against a private consistent
copy of the synthetic fixture, with no operational/model actions: initial36
page visits/144 assertions and final targeted10 visits/60 assertions. Manual
inspection caught a functional Admin1024 dropdown collision missed by initial
containment checks; the header worker repaired it and the final matrix included
pairwise control-collision checks. Those checks and final screenshots pass.
Detailed source-qualified evidence and the preserved initial limitation are in
`INDEPENDENT_QA_SHARED_NAVIGATION_20261026.md`. The owned8924 test server is
stopped; original8000/8001/model services were untouched. No additional security
finding; no other approval hold was changed.
