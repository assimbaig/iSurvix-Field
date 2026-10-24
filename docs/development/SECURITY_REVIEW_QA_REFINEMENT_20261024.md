# Separate security review: QA refinement and evidence reuse

24 October 2026. Scope: working changes after checkpoint `9ad13ec` on
`fix/qa-guided-documents-pause-20261024`: the QA site-information table,
two-pane review controls, scalar progress endpoint, source-observation reuse,
duplicate annotations and the optional compact-response decoder.

This review is independent of implementation. It used the installed Agency
Application Security Engineer profile and kept production code read-only.
Only disposable probes and this report were written. No operational records,
approvals, originals, services or native-model requests were changed. **No
finding has been fixed; owner approval is required before remediation.**

## Result

No new Critical, High or Medium exploitable vulnerability was established by
these probes. Two Low gaps (including the closing-review appendix) and two
hardening observations are recorded below. Existing S1/S2/S3 remain unfixed and
approval-pending. This is not a production security approval or a claim that
all possible flaws have been excluded.

New review command, from the repository root:

```powershell
.local\venv\Scripts\python.exe .local\security-qa-refinement-20261024\run_audit.py
```

Result: **10 probe tests completed in1.261s, 0 failures/errors/skips, zero external
network attempts and zero native-model requests**. These are adversarial
observation tests: two deliberately assert a current gap/hardening behavior so
the reproduction remains executable. They are not ten claims that every
security expectation passes.

The prior review's13 probes were also rerun against the changed implementation:
**13 completed in3.760s, 0 failures/errors/skips**, again without external/model
requests. Their successful execution confirms that S1/S2/S3 still reproduce;
it does not resolve them.

Private artifacts:
`.local/security-qa-refinement-20261024/audit_refinement.py`, `run_audit.py`,
`adversarial-tests.log`, `observations.json`, and `prior-findings-recheck.log`.
An initial probe attempt was correctly blocked by the immutable ORM. The final
storage-corruption probes explicitly use raw SQL in the disposable test database
to simulate a privileged storage fault, while also asserting that ORM mutation
remains prohibited. No application endpoint was used to bypass that protection.

## R1 — Low: selected-photo progress checks task membership, not submission membership

Location: `backend/core/qa_review_progress.py`, lines35–49.

Reproduction using real saved Django records and the actual authenticated route:

1. Engineer submits a site containing its original photo.
2. Assigned QA returns it to the Engineer.
3. Engineer uploads another photo but does not submit a new revision.
4. Assigned QA requests the progress endpoint with that new photo ID.

Actual response:200 with the old submitted `revision_id` and
`photo: {id: <new photo>, observations: []}`. The new photo is not in that
revision's frozen photo list. The endpoint validates it against
`c.photo_evidence`, whereas the analysis query is correctly restricted to the
selected processing revision.

Impact is limited: no photo bytes or findings from another task were disclosed,
and this reproduction exposed no findings for the unsubmitted photo. Foreign
task IDs return404. The remaining issue is an inconsistent meaning of
"submitted source photo" and an unnecessary same-task ID-existence signal.

Recommendation: require membership in the selected immutable revision before
returning selected-photo progress. Preserve lightweight polling with a compact
immutable membership index if needed; do not reload every historical snapshot.
Return404 for an excluded, future or other-revision-only source. Add explicit
returned-task and excluded-photo tests. **Fix approval pending.**

## H1 — Low hardening: a warm duplicate cache delays storage-corruption detection

Location: `backend/core/survey_acceleration.py`, `photo_duplicates()`, lines143–189.

The cold path verifies the digest of immutable fingerprint events and source
analyses. A warm cache returns before those checks. In the isolated fault probe,
the cache was populated, then a fingerprint event was corrupted with raw SQL
without updating its stored digest. A warm read returned the earlier advisory;
after cache eviction, the next read correctly raised an integrity error.
The configured cache timeout is60 seconds.

This is **not an HTTP cache-poisoning exploit**: the normal immutable manager
blocked the attempted mutation, and no application route capable of injecting
the corrupted event was found. It requires privileged storage mutation or an
out-of-band fault. The cached result affects duplicate advice, not evidence
deletion, inference skipping or engineering approval.

Recommendation: document this bounded detection delay. If immediate fault
detection is required, add a cheap trusted mutation-generation signal or
explicit cache invalidation after authorized maintenance, rather than removing
the performance protection without measurement. **Any change needs approval.**

## H2 — Low improvement: maintain extractor-version discipline for future releases

Location: `backend/core/survey_acceleration.py`, `analysis_identity()`, lines31–43.

Code inspection and invalidation probes confirm that identity includes actual
normalized inference image bytes, text, metadata, reference/type, full approved
schema digest, template, model pin, prompt, response schema, options and token
bounds. Changes to these tested values miss the cache. The source-code
implementation of response normalization is not itself hashed; semantic changes
that leave those values unchanged depend on incrementing `EXTRACTION_VERSION`
or the reuse version.

No unsafe cross-release reuse was demonstrated in the current build. This is a
future-release maintenance dependency. Recommendation: explicitly require an
extractor/reuse version bump whenever parsing or post-processing semantics
change, with a regression test; alternatively consider an implementation pin
similar to the existing outbound-worker compatibility check. **Approval required
before implementing an automatic pin.**

## Existing findings remain separate and approval-pending

See `SECURITY_REVIEW_QA_DOCUMENTS_PAUSE_20261024.md` for full reproductions.

| ID | Severity | Current status |
| --- | --- | --- |
| S1 | Medium | An older Resume can override a later Pause in the same unchanged revision. Reproduced again; not fixed. |
| S2 | Low | Owning Admin access to a soft-removed original differs between the new and legacy file routes. Reproduced again; not fixed. |
| S3 | Low | A nonexistent task in document removal can return500. Reproduced again; not fixed. |

The earlier active-PDF-original, draft-source visibility and production/dependency
assurance observations also remain unresolved policy/hardening items. This new
feature request is not approval to remediate any of them.

## Controls independently exercised

- Cache lookup cannot reuse another checklist's observations even when the model
  input identity is otherwise identical.
- Changes to model pin, governing schema/template, metadata, source image bytes,
  text, reference/type and extraction prompt miss the cache.
- Corrupt cached observation payloads fail digest verification before new
  findings are saved. Immutable source/event ORM mutations are refused.
- Reuse does not transfer `accepted`, confirmed verification status or measured
  claims; finding source IDs are rebound to the current source.
- A forged/shared advisory image fingerprint cannot turn different actual image
  bytes into a reuse hit. Similarity does not delete or skip evidence.
- Source-only cells, forged site identity and approved-section cell edits are409;
  frozen Engineer inputs and the processing snapshot remain unchanged.
- A `preserve_evidence` request cannot smuggle photo-link changes or bypass a
  stale review digest. No QA answer event is recorded for those attempts.
- Scalar progress denies Engineer, Team Lead, Admin and Client access; a revoked
  QA grant is404, as is a photo belonging to another task.
- Static review of the changed frontend found descriptions/AI observations and
  cell labels rendered through text nodes, same-origin source URL checks, CSRF
  headers on mutations, and failed-save handling. This was not a separate
  browser XSS campaign and does not replace the independent UI journey tests.
- Deferred snapshot fields still load on actual integrity/review access; the
  deferral does not itself remove a verification call. Compact-response decoding
  remains closed to unknown/repeated compact keys, with canonical generation
  still the default in the worker path.

## Limits

No production Nginx/VPS penetration test, dependency-advisory scan, physical-device
test, native parser exploit campaign, hardware throughput benchmark or new native
Ollama accuracy check was performed by this security reviewer. Native verification
and functional browser/full-suite evidence are maintained separately by the
implementation and QA owners; their passing results do not erase the findings
above. Choose and approve remediation separately, then retain and rerun the
appropriate adversarial probes and ordinary regression tests.

## Closing review appendix: provenance and two bounded consumers

The final follow-up reviewed user-visible revision numbers, metadata-only model
readiness outside the inference lease, and the Windows launch of two existing
survey consumers. The same immutable source/context/model identity remains in
place; moving metadata reads does not introduce a cloud fallback or an inference
bypass. Actual `analyse_source` and mapping calls still hold the shared
`photo_inference_lease`, with source analysis rechecking local vision capability.

The private review suite added four probes and reran the initial ten:
**14 total probes completed in1.611s, zero failures/errors/skips, zero external
network attempts or native requests**. This is a superset of the earlier ten;
do not add the counts. Evidence: `closing-adversarial-tests.log` and the updated
private `observations.json`.

Independently checked:

- A reused source records the user revision number separately from its database
  revision ID. The fixture deliberately uses different values.
- Legacy provenance resolution looks up revision numbers within the same
  checklist. A forged foreign-task revision reference cannot supply a displayed
  user revision number. That fault probe needs direct isolated SQL mutation;
  no application path for forging immutable provenance was found.
- A fresh uncached source encountering a busy inference lease remains queued,
  saves no new analysis, and does not call the model boundary.
- An identical cache-only revision can finish with that lease held busy, retains
  two unverified raw observations, makes zero model-boundary calls, and accepts
  no engineering answer. Inference was controlled for these security tests;
  native timing/actual-image evidence remains a separate root/QA responsibility.
- The normal launcher cleanup iterates both returned survey-process handles and
  uses the existing exact process-tree cleanup. Distinct logs and hidden windows
  are retained. Local SQLite uses `transaction_mode=IMMEDIATE`; job claims still
  lock/select persisted work, and the worker handles transient database errors.
  This reviewer did not run an independent two-OS-process stress benchmark.

### R2 — Low: partial worker startup can escape the cleanup scope

Locations: `scripts/Start-SurveyWorkers.ps1`, helper loop; `Start-iSurvix.ps1`,
worker startup before the app's `try/finally` block.

A controlled probe invoked the actual helper while substituting process creation:
the first consumer returned a process handle and the second raised a terminating
startup error. The result was one created handle, zero handles assigned to the
caller, and zero cleanup calls. The surrounding launcher enters its cleanup
`try/finally` only after the helper succeeds. Thus failure of the second launch
can leave earlier workers running even though app startup failed.

No real process was started or left orphaned by the probe. The helper control
flow was executed; the surrounding cleanup placement was inspected in source.
Receipt: `.local/security-qa-refinement-20261024/closing-startup-result.json`.
Reproduction:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .local\security-qa-refinement-20261024\closing_startup_review.ps1
```

Impact: unintended background work/resource consumption after a partial startup,
and less predictable shutdown. This is a lifecycle/availability gap, not a
cross-project authorization or engineering-approval bypass. Earlier photo-worker
startup already has a similar cleanup-placement exposure; the new second-survey
consumer adds another partial-success case.

Recommendation: put all worker acquisition and app startup inside one cleanup
scope; retain each handle immediately, and clean up already acquired process
trees if any later launch fails. Add controlled first/second-launch failures and
an isolated real-process shutdown check. **R2 is not fixed; owner approval is
required. S1/S2/S3/R1/H1/H2 were not remediated by this follow-up.**
