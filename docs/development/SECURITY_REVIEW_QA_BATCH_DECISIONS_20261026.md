# Separate post-functional security review

Status: no new exploitable vulnerability established in the reviewed implementation. No security remediation was performed. Earlier root audit D1/D2/L1 findings remain unapproved and untouched by this unrelated feature request.

Functional verification completed before this distinct attack phase. Same reviewer remained independent of implementation throughout. Scope: batch-links API and compact response, retention across rejection/resubmission, comment approvals and current-stage authorization, CSRF, safe rendered decision history. Frozen frontend hash receipt matches the final supplied hashes. This is bounded review evidence, not a full-application security clearance.

## Attack evidence

`separate-security-tests.txt` + `security-exit.json`:26 tests passed in10.018s, native exit0, zero external attempts. Eight were new independent probes;18 reran existing retention and approval integration tests after inspection of their actual assertions. `separate-security-scope-retention.txt` + `security-scope-exit.json`:two additional independent tests passed in1.053s, native exit0, zero external attempts. Combined28/28 passed, including ten new independent attacks.

The independent attacks cover:

1. Mixed valid/unknown/bool/duplicate photos and fields,501-photo batches,101-field batches, unknown operation, malformed reason and forged template type cannot partially persist or accept answers.
2. Unassigned QA, Engineer, TeamLead, Client and Admin cannot write the assigned QA batch. An ACTUAL foreign-company QA supplied otherwise valid current revision/source/template/review identities and received404 without events.
3. Old revision/source/template/review digests and replayed requests cannot create further events. Current genuine QA browser sessions still require CSRF.
4. Locked source/target fields cannot be linked or moved, and frozen source snapshots remain unchanged. Forged accepted/value/qa_by/section_approval/client_approval properties cannot accept answers or grant approval.
5. External return_to cannot redirect the authenticated reviewer to another origin; a repeated approval cannot add another decision.
6. A malicious comment is retained as literal text in server-rendered history, without raw executable markup. Actual Edge attack `separate-security-browser.json` and `security-comment-escaped-1366.png` additionally show literal </textarea>/<img onerror>/<svg onload> text, no inserted attacker img/svg elements and no event-handler execution.
7. A SECOND Engineer resubmission preserves the explicit prior unlink, retains original QA matching provenance and records the new retention event's causal actor as the submitting Engineer. No answer/completion acceptance is inherited.

Existing retested integration assertions independently checked changed image hash/schema/template invalidation, removed source and removed link exclusion, late-AI inability to overwrite retained links, actual controlled worker-cache reuse without new inference,3/4-layer named-stage approval semantics, blank/oversized/non-string comment rejection, ordinary Approve without a comment, clarification/stale-token rules, incomplete-QA409, TeamLead read-only guided evidence, permitted JSON save and wrong-stage403. These are actual assertion reviews and executed cases, not reliance on implementer summary counts.

## Reviewed source boundaries

- `backend/core/category_intake.py:487`: task/revision/current-source/QA-stage gate before matching mutation; completed packages remain locked.
- `backend/core/qa_matching.py:263`, `:322`: frozen template identity, bounded distinct IDs, operation validation, photo×field limits, explicit source move semantics, field locks and atomic event persistence.
- `backend/core/qa_matching.py:366`: authoritative compact patch for affected photo links/items/counts rather than client-created approvals.
- `backend/core/qa_matching.py:390`: same-task/template/schema and unchanged photoID+SHA retention; prior snapshot integrity checked; only confirmed matching retained, original matching actor remains provenance.
- `backend/core/review_route_service.py:118`: fresh named role/project/stage/token check precedes Approve with comments normalization to canonical approve; existing evidence/revision/blocking-finding gates remain applied.
- `backend/core/review_route_views.py`: guided JSON return limited to assigned named reviewer and exact local site URL; authority remains in service.
- `backend/templates/dashboards/_review_route.html`: default autoescaping and linebreaksbr preserve comment text in history, no trusted HTML conversion.
- `backend/static/core/js/qa_evidence_review.js`: compact-patch identity validation and selection/draft preservation inspected and functionally browser-tested.

## Limits and recommendations

No native model was called; network/process/OS filesystem boundaries, dependency advisories and unrelated older vulnerabilities were not re-certified. Adversarial concurrency and exhaustive Cartesian role-by-endpoint fuzzing were not performed. Retained QA matching deliberately remains advisory association, not a new human approval; continue to preserve that distinction. Keep these negative cases as security regression evidence if the owner chooses to promote private probes into maintained tests. Any new security fix still requires explicit owner approval. No finding is being silently accepted or remediated.
