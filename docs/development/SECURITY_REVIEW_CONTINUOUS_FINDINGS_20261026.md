# Separate AppSec review: continuous AI findings

26 October 2026. Reviewed the continuous findings additions on
`feat/qa-photo-candidate-ranking-20261024`, after baseline
`ee082a2d02ebf7103f42edf6967ec8d609f4ad45` and the separately reviewed compact
spacing changes. Scope: one semantic QA table with all current-photo finding
groups, the completed-study equivalent, thin cell styles and cache-token changes.
The actual handoff, AGENTS.md/development rules and installed Agency AppSec
profile governed the review. Product files remained read-only.

**No new exploitable vulnerability or security finding was established. No
security/product fixes were made by this reviewer.** Earlier C1/M1/W1/S1/S2/S3/
R1/R2 remain under their existing owner-approval holds. WS1's approved
remediation remains effective for the tested URL forms. This focused review
does not authorize deployment or certify all application security.

## New independent adversarial evidence

Private directory: `.local/security-continuous-findings-20261026`.

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' .local/security-continuous-findings-20261026/run_security.py
node .local/security-continuous-findings-20261026/frontend-probes.cjs
```

**Six new backend tests passed in1.250 seconds**, native exit0, no failures,
errors or skips (`backend-probes.log`). These use actual isolated uploaded and
submitted records and the actual completed-study HTTP view, plus two value/schema
unit probes:

- Multiple hostile component titles, notes and quotes remain template-escaped.
  Both findings appear in their own groups while `False` and measured zero retain
  their actual values. Merely displaying all rows creates no review events,
  source records or acceptance and retains the unverified disclosure.
- Two saved photos with distinct finding markers remain isolated: selecting one
  photo shows all of its findings and none belonging to the other photo.
- The Client receives two accepted values linked to its selected photo, including
  false, while a same-photo unaccepted value and private raw source observations
  remain absent. An accepted value linked only to the other photo appears only
  when that photo is selected.
- Foreign revision IDs, noncurrent Client revisions and mismatched released
  review signatures return404 before shared content is shown.
- A25-level nested legacy value remains plain display text, bounded to4000
  characters by the study formatter. The native Observation schema rejects
  object/list values before saving new native findings. This is bounded-depth
  evidence, not a claim of arbitrary-depth JSON safety.

**Seven new frontend controller assertions passed**, native exit0
(`frontend-probes.json`): one table with context first and all three groups
visible; hostile title/note/quote/nested keys remain text-only cells; false and
zero/unit preservation; no source mutation or outbound request from rendering;
switching photos clears all earlier finding groups; Team Lead still gets no
private raw table; and original WS1 URL rejection remains intact. The source
uses text-node creation for group headings/rows and `<pre>` source text rather
than inserting untrusted HTML.

The expanded independent WS1 controller reattack also passed:31 unsafe URL forms
blocked, five public URLs retained and both unsafe-anchor rendering attacks
passed (`ws1-expanded.json`). No DNS lookup, provider access or unsafe navigation
was needed for these checks.

## Existing guards and source assessment

**30 existing backend study/web-reference/phase regressions passed in4.865
seconds**, native exit0 (`regression-guards.log`). They include saved-analysis digest
failure handling, anonymous/foreign-role denial, POST denial for the study,
Client filtering, CSRF, stage-count honesty and web-reference protections.

Existing frontend reruns: **14 finding-table,29 web-reference and47 workspace
assertions passed**,90 in total. Full receipts use the corresponding script names
in the private directory. These overlap functional QA and must not be counted
twice as unique acceptance coverage.

Code inspection confirms the only removed paginator is the per-finding selector;
photo pagination remains one photo at a time. The study's role/project access,
current Client revision check, QA completion and exact matching released-drawing
signature predicates are unchanged. The Client list is assembled only from
accepted checklist items linked to the selected photo, without copying raw AI
notes/confidence/quotes into that projection. Internal tables remain explicitly
unverified; no group is presented as automatically accepted. The base template
change only refreshes the existing QA stylesheet query token.

All backend runs use temporary databases/media/model caches, with zero external
network attempts and zero native-model requests. No operational survey, original
evidence, approval, worker or app service was mutated. Only this report and
private probes/receipts were written. Exact reviewed study/helper/template/JS/CSS
hashes are in `source-hashes.json`.

## Limits

No actual browser exploitation, large retained-data stress campaign, arbitrary
deep-JSON fault campaign, live provider/native-model accuracy check, dependency
advisory audit or production test was performed by this reviewer. The controller
DOM is a test fixture; real continuous-table geometry/accessibility remains the
functional QA agent's evidence. The isolated Client release records establish
read-projection behavior, rather than claiming this test performed an operational
engineering approval. Earlier held findings and WS1's documented DNS/syntax-only
policy limits remain unchanged.

## Final unit-only display follow-up - 26 October 2026

Inspected the final small helper change: a unit without a value now receives a
Recorded unit row while Extracted value stays Not recorded. The frontend group
heading separator changed from a literal question mark to ` / `; destination,
source, role and release predicates are unchanged. Existing QA stylesheet URLs
now share the fresh cache token; this changes resource caching, not permissions.

Added a real study-response probe with a hostile HTML-like unit, a missing value
and a separate false value. The unit is escaped, no number is invented, and
`False mm` remains an actual value rather than becoming the missing-value case.
The current Client acceptance/photo-isolation and stale-release probes were
rerun in the same execution: **seven private backend tests passed in1.442
seconds**, native exit0 (`final-unit-backend.log`). Seven private frontend
security assertions also passed, including hostile findings, source clearing,
Team Lead suppression and the original WS1 negatives (`final-unit-frontend.json`).
The final existing finding-table suite passed15/15 (`final-finding-table.json`).

**No additional security finding.** Final reviewed hashes are retained in
`final-source-hashes.json`; original receipts/hashes remain preserved. No product
files, approval holds, external providers, native models or operational data were
changed by this reviewer.

Final caption-only cleanup: inspected the literal separator change from
`Site, photo & AI findings ? N` to `Site, photo & AI findings - N` in QA JS.
No data, branching, request, URL or approval logic changed. The seven private
frontend security assertions still pass (`final-caption-frontend.json`), and
the final QA JS hash was refreshed in `final-source-hashes.json`. No additional
finding or broader backend-verification claim is introduced by this check.
