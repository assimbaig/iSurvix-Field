# Independent security review: QA matching resume

26 October 2026. Reviewed branch `feat/qa-photo-candidate-ranking-20261024`,
HEAD `db1803ab97f9041809cb04731282e8c0b93fdf8b`, including current working
changes and checkpoints after base `42cf64b`. The actual AGENTS.md, local handoff,
development rules and complete installed Agency Application Security Engineer
definition were read. Production source remained read-only. Only this report and
private probes under `.local/security-resume-20261026` were written.

No new Critical, High or Medium vulnerability was established in this focused
review. **One new Low evidence-integrity finding is reproduced below. No finding
was fixed. Owner approval is required before remediation.** This report does not
approve production deployment or close earlier findings.

## M1 - Low: an empty observation creates a high-confidence suggested photo link

Locations: `backend/core/qa_matching.py:53-68`,
`backend/core/survey_checklist_mapping.py:345-359`, and
`backend/core/survey_processing.py:663-674,700-709`.

The candidate-outcome code requires a high-confidence finding to contain an
actual value, component, notes or evidence quote before calling its photo
proposed. However, `valid_ai_sources()` also counts `mapping_reason` as evidence.
The worker itself generates that reason when an image result names an allowed
field. A completely empty finding can therefore acquire its own evidence through
the generated explanation.

Reproduction used the actual isolated worker `process_next()` with valid saved
synthetic photos and deterministic image responses. The image response had
`field_hint='manufacturer'`, `confidence='high'`, `value=None`, and empty
component, notes and evidence quote. These empty fields are permitted by the
observation data model. No text model request was made.

Observed result:

- Job reached `ready_for_review`.
- Both photo candidate outcomes were `unmatched`.
- The same two photos nevertheless appeared as `ai_suggested` manufacturer
  links, with `confidence='high'` and reason
  `The image analysis proposed this supported checklist location.`
- The meaningful assertion that empty observations must yield zero suggested
  links failed. The failing test remains in the private receipt.

Impact: the QA assigned/unassigned state and suggested-link count overstate
supported evidence, contradict the candidate panel, and may steer the reviewer
toward an unsupported location. No human acceptance, source modification,
engineering approval or role escalation was demonstrated. The evidence remains
available for human review; this limits severity to Low.

This is new relative to requested base `42cf64b`: its `valid_ai_sources()` required
both the checklist item and supporting finding to contain nonempty values. The
new support for unanswered inspection locations is useful, but the explanatory
mapping text must not substitute for an actual source observation.

Recommendation, **pending owner approval**: share one source-support predicate
between candidate outcomes and suggested-link projection. Accept a real value
or nonempty extracted component/notes/quote, while excluding generated mapping
explanations. Retain support for real inspection-location observations without
requiring a pass/fail answer. Keep the empty high-confidence observation as a
negative integration regression and the real unanswered inspection case as a
positive regression. Recheck assigned/unassigned counts after the change.

## Independently executed evidence

Private command, from this worktree:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' .local/security-resume-20261026/run_probes.py
```

**9 new adversarial tests: 8 passed, 1 failed (M1), 1.841 seconds; native exit 1.**
The expected secure behavior was deliberately retained as a failing assertion.
No test errors or skips. Receipt: `probes.log`; tests: `security_probes.py`.

Eight successful tests independently exercised:

- Exact source/finding IDs and approved template IDs; foreign source and
  `__proto__` candidate targets were rejected.
- Cache identity changes for image bytes, text, metadata, reference, template,
  full schema/catalog and model. Mapping identity changes for source, injected
  observation text, template and model.
- Actual saved raw-analysis reuse refused another checklist and model digest.
- An actual second submission reused both inference stages without inheriting
  human acceptance; prior immutable row digests remained unchanged.
- Authenticated Engineer, Team Lead and Client could not invoke QA matching
  writes; private candidate reasons and aliases were absent from their tested
  responses. Team Lead could read only its permitted projection; Engineer/Client
  review-state denial was also exercised.
- Boolean/foreign photo IDs, unknown fields, stale revision/source/review digests
  and approved-section writes were rejected without new matching events.
- Blank ordinary remarks did not bypass GPS, required-subject, clear-quality or
  explicit-site evidence-policy attestation reasons. This check used a fixture
  snapshot overlay rather than mutating immutable database snapshots.
- Hostile generated-name inputs produced bounded ASCII aliases and retained
  source snapshots; disallowed original extensions became `.img` aliases.

Separately reran **44 existing regression tests: all passed in 3.669 seconds,
native exit 0**, covering all `core.test_survey_acceleration` and
`core.test_survey_checklist_mapping` tests, stale QA-return/resubmission writes,
shared Client suppression of unaccepted AI values, and original-byte corruption
despite cached observations. Receipt: `existing-guards.log`. These 44 tests are
distinct from the nine new probes, but may overlap other agents' test counts.

Both runs used `scripts/run_backend_tests.py` isolation: temporary databases,
media and model caches, **zero external network attempts and zero native model
requests**. No operational records or service state were changed. At initial
inspection only loopback Ollama listeners on 11434/11435 appeared among checked
8000/8917/8919/11434/11435 ports; they were left untouched. Source SHA256 receipts
are saved in `source-hashes.json`.

## Existing approval-pending findings and review limits

W1 Low (private PDF derivative integrity), S1 Medium (stale Resume replay),
S2/S3 Low (retained-file policy/missing-task error), and R1/R2 Low (selected-photo
revision scope/partial worker startup cleanup) remain separate and unresolved,
as recorded in the actual handoff and the prior workspace, documents/pause and
refinement reviews. This review did not retest all six or authorize their fixes.

No browser execution, native image accuracy test, concurrency/load campaign,
fresh dependency advisory scan or production configuration audit was performed
by this reviewer. Hostile-name XSS assessment combines backend alias/projection
probes and source inspection: new DOM text uses `textContent`/text nodes and
`replaceChildren`; no actual browser exploitation claim is made. Model injection
tests verify trust boundaries and rejection of unauthorized IDs, not immunity
to incorrect proposals from a native model. The exact matching cache is scoped
to a checklist, and project authorization is inherited from the existing access
service; no direct cross-project native processing test was run.

## Final integration addendum - Engineer Help link

Separately reviewed the final narrow `backend/templates/base.html` diff restoring
the Local assistant link under Help. The actual Django condition is
`role_design.role == 'ENGINEER' and local_assistant_available`. This does not
expand link visibility to QA, Team Lead, Client, Admin, Super Admin, legacy
Project Manager or an unknown role. The existing capability context additionally
requires local AI to be enabled and the route to resolve. The changed guide
directs Engineers to upload and submit to QA; it assigns no matching/approval
capability to the Engineer. No route or authorization service changed.

A new test renders the actual extracted conditional using Django templates for
eight roles and both capability states (16 combinations); only an enabled
Engineer receives the link. Final adversarial rerun: **10 tests, nine passed,
one retained M1 failure, 1.655 seconds, native exit 1**. Receipt:
`probes-final.log`. The four existing AssistantCapabilityTests were independently
rerun against the final template: **four passed**, including hosted-disabled,
missing-route, local-disabled and available-local-route cases, with no inference
on render. Receipt: `assistant-capability-final.log`.

No additional finding from this narrow final diff. M1 and prior findings remain
unfixed and approval-pending. No product file was edited by this reviewer.
