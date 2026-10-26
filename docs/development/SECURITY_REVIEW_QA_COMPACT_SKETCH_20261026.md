# Separate security review: compact QA support and source sketch tracing

26 October 2026. Reviewed uncommitted changes against
`9e849e610fab7a630866adbe365bdc7cefe8e2ad` on
`feat/qa-photo-candidate-ranking-20261024`. Scope: compact photo support tabs,
legacy and partial candidate read projections, complete small-catalog bindings,
and the new source-tracing sketch PDF/DXF integration. The actual handoff,
development rules, AGENTS.md and installed Agency Application Security Engineer
profile governed this separate review. Implementation source remained read-only.

**One new Low stale-advice finding (C1) is reproduced. No new Critical, High or
Medium issue was established. No finding was fixed. Owner approval is required
before any remediation.** Earlier M1/W1/S1/S2/S3/R1/R2 remain unresolved and
approval-pending; this review does not close them or authorize deployment.

## C1 - Low: partial candidate reads omit current mapping-context verification

Location: `backend/core/qa_matching.py:155-184,190-196`.

When a job is `preparing_checklist`, the new read projection accepts every
same-revision `mapping:*` row whose JSON digest is valid. It verifies photo
membership and approved field IDs, but does not verify the saved mapping's
`batch_identity`, model binding `identity`, or versioned key against the current
batch. By comparison, the worker explicitly verifies these identities at
`backend/core/survey_processing.py:675,697` before reusing a mapping.

Executable isolated reproduction:

1. Submit synthetic photos, retain a raw analysis for a submitted photo, and set
   its synthetic processing job to `preparing_checklist`.
2. Store a retained `mapping:0001` row in that revision with a correct payload
   digest, but deliberately obsolete batch/model identities. Its candidate
   targets a real approved field and explains `STALE_MODEL_CONTEXT`.
3. GET the actual authenticated QA review-state endpoint.

Observed: HTTP200 includes that explanation as a proposed candidate on the
submitted photo. The secure expectation that an explicitly obsolete context
must not appear as a current candidate fails. The normal JSON integrity check
still works; a deliberately wrong payload digest is rejected separately.

Threat/impact limits: this is a retained-history/read-projection gap, not a
demonstrated endpoint for an attacker to write mappings. It becomes relevant
when obsolete mapping rows coexist with current processing after an interrupted
job or algorithm/version transition; retention is intentional in the worker.
The reproduction seeds such a retained row through the test ORM rather than
claiming a native model or migration created it. No foreign-photo disclosure,
confirmed link, accepted answer or engineering approval was produced. QA must
still make an explicit source-backed link decision. These limits justify Low.

Recommendation, **pending approval**: project only durable mappings verified
against the current revision's raw findings, schema, model pin and mapping
version/batch identities. Preserve obsolete rows as historical records. Do not
aggregate a legacy mapping solely because its digest is correct. Reuse the
worker's context-verification contract without initiating inference on a GET;
if necessary, persist a compact verified-context receipt. Add a stale-row read
regression alongside valid in-progress candidate coverage.

## Executed adversarial evidence

Private receipt directory: `.local/security-compact-sketch-20261026`.

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' .local/security-compact-sketch-20261026/run_security.py
```

Final result: **12 new tests, eleven passed, one failed (C1), 5.463 seconds,
native exit1; zero errors/skips**. The negative security assertion remains
failing rather than treating reproduction as a clean security result. Tests are
in `security_compact_sketch.py`; final output is `probes-final.log`.

Successful checks:

- A mapping whose photo is outside the submitted snapshot cannot supply partial
  candidates; Engineer, Team Lead and Client responses omit private mapping text.
  No acceptance was created. Bad saved JSON digests are rejected.
- Complete-catalog native responses still reject foreign field IDs, and
  oversized/repeated candidate lists fail before inference.
- Sketch asset traversal/absolute paths and invalid base64 fail before output
  publication; isolated staging cleanup leaves no published files.
- Corrupt images, encrypted PDF input and mismatched original-analysis hashes
  fail. Pixel, aggregate image-asset and sheet resource limits fail explicitly.
  Resource tests lower limits in isolation; they do not allocate production-size
  hostile files or claim a load-test result.
- Script-like filenames/notes remain data during real PDF rendering. The
  generated PDF contained no links or annotations from those inputs; asset
  references stayed beneath the isolated output directory. Original bytes were
  unchanged by rendering.
- The actual renderer produced a draft PDF, DXF, ZIP and preview from a real
  synthetic upload/submission. Assigned QA could download each; a foreign-company
  QA user and Client received404. Reads did not release the package or add
  approval events. Engineer, QA, Client and Team Lead premature-release requests
  were denied; no released drawing set appeared.
- Replacing the new PDF bytes made its protected download return409; corrupting
  its uploaded source made original verification reject the revision.
- Final workbook support also rejects injected traversal archive entries, VBA
  parts, external relationships and XML entities before rendering. Analysis from
  another worksheet does not appear in the embedded sketch's notes. The full
  uploaded workbook remains unchanged, and its sketch is indexed in the register.

The first harness run expected `ValueError` rather than Django's correct
`ValidationError` for corrupted originals; a later harness run expected only
403/409 rather than also accepting404 denial. These test assumptions were
corrected without product edits. C1 reproduced throughout.

Final independent regression rerun: **70 tests passed in16.261 seconds**, native exit0,
covering the complete sketch unit/integration modules, mapping module and QA
matching module. Includes real PDF/DXF generation, full-source preservation,
red dimension warnings, multipart/multipage notes, trace-overflow warnings,
legacy unlink replay, uncertain/unassigned suppression and partial read/write
separation, including final workbook and register changes. Receipt:
`regression-final.log` (earlier pre-final run:68 passed in15.772 seconds in
`regression-guards.log`). These are existing tests and overlap
functional QA counts; do not add them to another agent's unique coverage total.

Four existing independent review/release tests also passed in1.166 seconds,
covering assigned QA/Team Lead separation and actual three/four-layer survey
routes with required Client decisions. Receipt: `release-guards.log`.

All runs used the ordinary runner's temporary database/media/model-cache
isolation, **zero external network attempts and zero native model requests**.
Only this report and private probe/receipt files were written by this reviewer.
Operational database/media, app/worker/Ollama processes and prior findings were
untouched. Final reviewed source SHA256 values are in `source-hashes-final.json`;
the initial review hashes are retained separately in `source-hashes.json`.

## Additional boundaries and limits

Code inspection confirms sketch originals come from authenticated immutable
snapshot records, are hash-checked before decoding, and carry original document
ID/hash and analysis source references into drawing geometry. The feature never
derives engineering scale from pixels; records are marked Draft For Review,
Not to Scale and unverified. Download routes still bind the drawing set to its
authorized checklist and enforce Client release/current-review gates. The late
functional XLSX compatibility and register refresh changes were inspected and
included in final probes: workbook loading uses existing archive/XML/image bounds
and disables external links; no-image worksheets get explicit warnings; appended
sketch sheets and current warning counts are indexed with bounded continuation
register pages. No additional security finding was established from those changes.

No browser exploitation run, native sketch-recognition/accuracy assessment,
large hostile-file performance campaign, fresh dependency advisory scan or
production-hosting audit was performed. No claim is made that prompt injection
cannot influence an unverified model proposal. Existing approval-pending
findings were not re-remediated or comprehensively retested here. This focused
report is not a production security clearance.
