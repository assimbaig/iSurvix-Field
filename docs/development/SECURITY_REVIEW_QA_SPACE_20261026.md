# Separate AppSec review: compact QA spacing

26 October 2026. Reviewed working changes after
`ee082a2d02ebf7103f42edf6967ec8d609f4ad45` on
`feat/qa-photo-candidate-ranking-20261024`: scoped QA shell/CSS density,
phase-note relocation into the existing Analysis details disclosure, and the
corresponding template/test changes. Actual AGENTS.md, current handoff,
development rules and the installed Agency Application Security Engineer profile
were used. Product source remained read-only during this separate review.

**No new exploitable vulnerability or security finding was established in this
narrow UI change. No product fixes were made by this reviewer.** This does not
resolve earlier C1/M1/W1/S1/S2/S3/R1/R2: all remain under their existing approval
holds. The separately owner-approved WS1 remediation remains effective in the
tested cases; its prior verification is recorded in
`SECURITY_REVIEW_WEB_STUDY_20261026.md`.

## Independently executed adversarial checks

Private command:

```powershell
node .local/security-qa-space-20261026/space-security.cjs
```

**Eight new controller/security assertions passed, native exit0.** Receipt:
`.local/security-qa-space-20261026/space-security.json`; reproducible script:
`space-security.cjs`.

- A hostile phase note containing `<img src=x onerror=alert(1)>` remains literal
  text in the expandable list. Its rendered note node has no injected children;
  the compact phase strip does not contain that markup as active content.
  The implementation uses text-node creation and the `.title` property, not
  `innerHTML` or untrusted URL assignment.
- Removing phases clears previously retained note nodes and hides the strip.
  Missing stages render Unavailable, without invented zero counts, percentages
  or an approval claim. A failed matching stage remains visibly Failed while
  its saved count retains `total unknown`.
- Supplying completed phase states cannot turn a read-only QA response into an
  editable one. Pause/retry controls remain hidden and completion guidance stays
  read-only. Team Lead phase details stay hidden and cannot gain QA controls.
- All five original WS1 loopback forms are still rejected by the actual
  controller; a legitimate public manufacturer URL remains accepted.
- The compact body class is conditional on the QA quick-review presentation.
  The template retains CSRF and native `<details><summary>` semantics, preserving
  its existing keyboard-operable disclosure rather than adding a new custom
  focus or authorization mechanism.

The first private harness attempt omitted the mandatory
`unassigned_photo_ids` fixture field; the controller correctly rejected that
incomplete state. The test fixture was corrected without product changes.

Independent existing frontend reruns: **five suites,150 assertions passed**:
compact-layout4, finding-table12, web-references29, guided-state58 and workspace47.
Their full JSON receipts are retained in the same private directory. These
existing checks overlap functional QA coverage and should not be counted twice.

Independent backend guard rerun:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py core.test_qa_review_progress core.test_web_references.WebReferenceAccessTests core.test_qa_matching_backend --verbosity 1
```

**34 passed in12.283 seconds, native exit0; no failures/errors/skips.** Receipt:
`backend-guards.log`. This exercises actual role/project/revision/CSRF guard
behavior, stale writes, locked targets, stage projections and private/reviewed
data boundaries against the current UI source. Temporary database/media/model
caches were used, with **zero external network attempts and zero model calls**.

## Scope assessment and limitations

The reviewed diff changes no backend authorization route, database, approval
predicate or request mutation callback. Header/nav compression is scoped by the
conditional QA body class; it changes presentation of existing server-generated
links rather than their destinations or permissions. Read-only and approval
controls retain their original authorization source and CSRF request behavior.
Expanded explanatory details retain status/error/source-count text; the phase
strip reports processing state rather than a human engineering decision.

The small desktop fonts are the explicit owner-requested density change. This
report does not certify readability, accessibility compliance, measured layout
geometry or keyboard focus in a real browser. This reviewer used controller
fixtures and code inspection; the other agent's browser geometry checks are not
claimed as independent AppSec execution. No new browser session was attached to
the running QA fixture or operational app during this review.

Only this report and private probes/receipts were written. Operational records,
original evidence, existing8000/8001 services, isolated8921 QA service and model
workers were left untouched. Exact reviewed JS/template/CSS SHA256 values are
in `.local/security-qa-space-20261026/source-hashes.json`. No merge or deployment
is authorized by this focused review, and earlier held findings remain unchanged.

## Final navigation and toolbar follow-up - 26 October 2026

Separately reviewed the final scoped toolbar label/filter CSS and the
`_primary_navigation.html` QA branch. Only `QUALITY_ENGINEER` together with
`qa_quick_review` promotes the existing four More-menu anchors into the header.
The destinations, query values and existing outer role predicates are unchanged;
other QA pages retain More. CSS changes affect toolbar layout rather than
request, role or approval behavior.

Three new isolated template-security tests passed in0.054 seconds, native exit0:

- Rendered compact QA links exactly equal the old menu links, including their
  attributes and relative server-generated destinations.
- Hostile industry/project strings cannot create script/image tags, a new
  attribute or an external authority. Industry is URL-encoded after existing
  template escaping; project context remains HTML-escaped. This test does not
  claim that arbitrary project strings are meaningful project selectors or
  introduce a new project-authorization policy.
- Toggling the compact flag leaves Engineer, Team Lead, Client, Admin and Super
  Admin link sets unchanged; it does not grant them the QA My reviews branch.

Receipt: `navigation-security-final.log`; private test/runner:
`navigation_security.py`, `run_navigation.py`. An initial harness expectation
assumed encoding before the existing `firstof` escaping step; it was corrected
to the actual safe escaped/encoded output without product edits.

The eight phase/XSS/read-only controller probes were rerun and passed
(`space-security-final.json`). The full independent WS1 frontend reattack again
blocked31 unsafe URL cases, retained five public URLs and passed both unsafe
anchor-rendering attacks (`ws1-final.json`). The final compact-layout regression
suite passed5/5 (`compact-layout-final.json`). No additional finding was
established. Final hashes now include the navigation partial and toolbar CSS in
`final-source-hashes.json`; initial hashes remain preserved. Existing held
findings and service/data-preservation limits are unchanged.

Final mobile touch-target follow-up: inspected the last CSS-only rule under
`max-width:650px`, scoped to the existing QA reference-review mobile navigation
buttons/category-close control. It raises their minimum height to36px and adjusts
padding/line-height; no JS, template, URL, permission or request logic changed.
The eight phase/XSS/read-only controller probes still pass
(`mobile-final-controller.json`). Refreshed the final CSS hash in
`final-source-hashes.json`. No new security finding; actual touch geometry remains
the functional browser QA agent's evidence rather than this reviewer's execution.
