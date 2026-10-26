# Follow-up requirements and evidence

Current candidate: `feat/qa-photo-candidate-ranking-20261024`, implementation
checkpoint `b1e49a1`. These statuses concern the requested follow-up, not every
historical project requirement or production acceptance.

| Requirement | Location | Executed evidence | Status |
| --- | --- | --- | --- |
| Compact QA source support with accessible tools | QA template, JS and CSS | Independent52 earlier browser checks at desktop/mobile; before/after screenshots | Verified |
| Restore legacy saved photo-match proposals | `qa_matching.py` | Exact prior/current endpoint regression; no GET mutation | Verified |
| Show durable proposals before final checklist result | `qa_matching.py` | Active-job fixture9 assertions; valid source IDs and immutable originals | Verified with separate C1 hold below |
| Preserve valid synonymous points in small catalogs | `survey_checklist_mapping.py` | Executed missing-candidate RED/GREEN and focused mapping tests | Verified in deterministic integration; native accuracy not established |
| Convert retained hand sketches into draft source-tracing sheets | `survey_sketches.py`, renderer hook | PDF/DXF inspection, upload/download integration, register repair; private6-page source rendered read-only | Verified as draft tracing |
| Highlight unsupported/missing sketch measurements | Shared geometry warning ledger | Source-backed3500mm synthetic transcription and explicit missing-dimension PDF notes | Verified |
| Public keyword responses with citations | `web_references.py`, QA AI-details form | Real Wikipedia service and actual authorized Django/browser request; empty/error/retry/race tests | Verified for encyclopedia references |
| General web search | Optional Brave adapter | Deterministic provider/auth/error tests; live503 explicitly not configured | Blocked: owner-provided provider key absent; no paid signup authorized |
| Compact findings with real site/photo context | QA table and completed-study renderer |12 frontend table checks plus saved-data browser checks, valid Pydantic defect case and zero-value handling | Verified |
| Separate truthful stage tracking | `qa_review_progress.py`, full QA state and UI | Scalar query tests, actual0→1 saved-batch browser checks; extraction explicitly shares analysis | Verified; planned batch denominator unavailable |
| One read-only study format across permitted roles | `completed_ai_study.py`, three entry links | Four internal roles at1920/1366/390, source hash, pagination, anonymous/foreign guards; released-client accepted-only integration | Verified within existing sharing/release policy |
| Repair owner-approved web-link bypass WS1 | Backend/frontend URL validation and cache namespace | Original5 plus26 unsafe forms blocked, legitimate links retained;13 private security probes and actual anchor-click tests | Verified for reproduced bypasses |
| Preserve records, originals and approvals | Existing storage, access, immutable revisions and audit controls |460 isolated originals/hash/row/revision preservation; no operational approvals or processing reset | Verified for measured evidence; not an exhaustive operational media rehash |
| Broad client disclosure of private AI proposals | Existing release and sharing rules | Client private-data exclusion remains enforced | Blocked by existing policy; no new disclosure permission assumed |
| Semantic/manufacturer-accurate CAD reconstruction | Draft tracing output | Full source reference retained; no approved manufacturer geometry inferred | Blocked: not established by pixel tracing or retained incomplete measurements |
| C1 stale retained mapping context | Separate AppSec report | Reproduced Low-severity read-preview advice issue | Failed, owner remediation approval pending |
| M1 and earlier recorded security findings | Prior review reports/handoff | Original evidence retained; not changed by WS1 repair | Open, separate owner approval pending |

Independent new-feature QA:155 browser assertions,9 HTTP guards and29 focused
backend tests. Native public lookup is separate from deterministic fixtures.
See `INDEPENDENT_QA_WEB_STUDY_20261026.md` for exact commands, limitations and
receipts. Final full-suite/source-fingerprint evidence is recorded in the final
delivery section of `WEB_REFERENCES_AND_STUDY_20261026.md`.
