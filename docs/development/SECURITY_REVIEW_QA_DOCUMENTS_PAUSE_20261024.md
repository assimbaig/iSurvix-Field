# Separate security review: QA review, source documents and AI controls

Review date: 24 October 2026. Branch:
`fix/qa-guided-documents-pause-20261024`, based on retained WIP `3668cbb`
and the merged PR16 history. This review inspected the current working files,
including changes since `e179206`; it is separate from implementation and QA.

The installed Agency profile
`C:\Users\Muhammad Assim Baig\.agency-agents\security\security-appsec-engineer.md`
was read and used. The application source was read-only throughout this review.
Only private disposable probes and this report were written. No operational
database, evidence, approval, Ollama request, credential or running worker was
modified. **None of the findings below has been fixed. Owner approval is required
before remediation**, as instructed in `DEVELOPMENT_RULES.md`.

## Result and evidence

No Critical or High exploitable defect was established by this scoped review.
There are three reproduced gaps and two further policy/hardening observations.
This is not a production security approval or a claim that no other flaws exist.

Command, from the project root:

```powershell
.local\venv\Scripts\python.exe .local\security-resume-20261024\run_audit.py
```

Final execution: **13 probe tests completed, 0 failures/errors/skips, 3.551s**;
temporary database/media/model caches, **zero external network attempts** and
zero native-model requests. Some probes deliberately assert an undesirable
observed behavior to reproduce a finding; a green probe suite does not mean
every security expectation passed. Two earlier runs had a harness assumption
that malformed filenames would upload; the multipart/parser boundary correctly
rejected both payloads with409. The final probe verifies that rejection and
checks a valid download separately.

Private reproducible evidence is retained under
`.local/security-resume-20261024/`: `audit_cases.py`, `run_audit.py`,
`adversarial-tests.log`, and `observations.json`. No private credentials are
included in this public report.

## Reproduced gaps awaiting approval

### S1 — Medium: an older Resume can override a newer Pause

Location: `backend/core/survey_pause.py`, `control()`, lines85–127; both HTTP
interfaces use this service.

The source digest and revision ID identify evidence, not the generation of a
processing-control command. Reproduction with one authorized QA reviewer and
an unchanged synthetic revision:

1. Pause the queued job.
2. Resume it; save that request.
3. Pause it again; the saved state is `paused`.
4. Deliver the earlier Resume request again.

Actual result: the job becomes `queued`, with a second `resumed` audit event.
The newer pause intent is lost. A delayed HTTP retry or another stale browser
tab can cause this; no separate attacker privilege is required. Project and
role authorization still apply, and no checklist answer or approval changed.

Recommendation: add a control-generation token and request idempotency key.
Compare the expected generation while holding the job lock; return the earlier
receipt for an already completed command and reject a command from an older
generation. Test delayed retries across multiple Pause/Resume cycles and tabs.

Classification: workflow-integrity/replay gap, not a role escalation or a proven
engineering-approval bypass. Approval for this fix is pending.

### S2 — Low: retained-document access differs between the two file routes

Locations: `backend/core/engineer_documents.py`, `delivery()`, lines183–204;
`backend/core/survey_processing_views.py`, `document()`, lines357–374.

After an Engineer soft-removes a supporting document from the active draft,
the new capture file route returns404. An authorized owning Admin can still get
the same retained original through the older survey-processing document route
without supplying an explicit historical revision. The delegation to the new
membership rules is limited to Engineer, QA and Team Lead roles.

Reproduced result: new route404, old Admin route200, original bytes unchanged.
Engineer bypass attempts through both routes return404. Foreign-project,
unassigned and revoked accounts remain denied.

Recommendation: explicitly decide whether Admin has an unrestricted retained
evidence/audit privilege. If so, expose and audit it as historical access. If
not, delegate all category-document reads to one shared revision-membership
policy and require an explicit authorized revision for retained evidence.

Classification: authorization-policy consistency gap. The current owning Admin
already has project authority, so this is not established cross-tenant leakage.
Approval for a policy change/fix is pending.

### S3 — Low: nonexistent task IDs can produce HTTP500

Location: `backend/core/engineer_documents.py`, `remove()`, line170; similar
locking patterns also exist in other task services, including `survey_pause.py`.

An authenticated Engineer POST to the document-removal endpoint for a nonexistent
task produces500 because `Checklist.objects.select_for_update().get()` runs
before the scoped lookup and the exception is not normalized. This was
reproduced with the actual Django endpoint, not a substituted service response.

Recommendation: use a scoped not-found lookup under the lock, or consistently
map missing records to404 before continuing. Add invalid-ID tests with production
`DEBUG=False`. Keep the denial response independent of foreign-record existence.

Classification: error-handling/availability gap. This review did not establish
secret disclosure from a production500 response. No record or file changed.
Approval for this fix is pending.

## Policy and hardening opportunities

### H1 — Medium: define handling of active content in downloaded PDF originals

The existing PDF validator accepts a valid PDF containing a JavaScript OpenAction.
The new Engineer document flow preserves and serves that original unchanged.
The probe created an inert synthetic `app.alert` action and verified retention;
**it did not execute that action in any browser or desktop PDF application**.
Inline previews have `Content-Security-Policy: sandbox; default-src 'none'` and
`nosniff`, which is a useful control. A downloaded original may instead be opened
in a separate PDF application whose behavior was not tested.

Recommendation: make the untrusted-original policy explicit. Consider malware
scanning/quarantine and generated raster previews, while retaining originals
privately; do not silently rewrite forensic originals. Treat any proposed scan
or disarm service as a separately approved dependency. This is an attack-surface
observation inherited from the existing parser, not proven code execution.

### H2 — Low: document draft-source visibility and complete release assurance

Assigned QA, assigned Team Lead and the owning Admin can download a newly uploaded
supporting document before the Engineer submits it (all three returned200).
The existing assigned-site policy permits this; similar visibility already
exists for photos. If drafts should remain private to the Engineer, that requires
an explicit policy change and tests across both photos and documents. Do not
describe this as submitted-revision-only access without qualification.

This review did not test a production Nginx/VPS configuration, physical mobile
devices, arbitrary native parser exploits or actual JavaScript execution in a
downloaded PDF. A dedicated dependency-advisory scan was not run:
`pip_audit` is not installed, and no tools were downloaded. A successful `pip
check` elsewhere establishes package compatibility, not absence of advisories.
Run the appropriate deployment and dependency gates before production promotion.

## Controls independently exercised

- Anonymous file reads redirect to authentication; foreign-project, unassigned
  QA, Client and revoked-project users cannot obtain document bytes.
- CSRF-free mutation is403; stale document removal is409; submitted evidence
  removal is403 and preserves the source record.
- A soft-removed original cannot bypass current-membership checks through either
  file route when requested by the Engineer.
- Malformed CR/LF and quote/semicolon filename payloads are rejected; a valid
  download has no injected response header and its file hash is unchanged.
- Engineer, Team Lead, Client and Admin cannot control the QA processing job.
  Locked QA and stale revision requests leave job/audit state unchanged.
- Revoked outbound-worker bearer credentials cannot heartbeat or request the
  next task even while a job is `pausing`.
- Forged, expired and replaced worker leases are403. A stale implementation
  result is409 and creates no saved source findings.
- Code inspection found new document/AI descriptions rendered with text nodes;
  protected source links are checked for same origin. This is not a substitute
  for a dedicated browser-based XSS campaign.

Remediation work should begin only after the owner selects and approves the
findings to address. Retest each approved correction against these retained
probes and the ordinary regression suite; keep the review record intact.
