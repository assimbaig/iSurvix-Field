# QA General Info, linkage tree and category gallery

Verified follow-up after checkpoint `feb0649`, continuing the same feature branch.
Final evidence: `QA_GENERAL_GALLERY_NAV_ACCEPTANCE_20261026.json` and the
independent reports listed below. This is not a production-readiness certificate.

| Expected behaviour | Implementation area | Verification | Status |
|---|---|---|---|
| Left General Info opens real data in the centre evidence workspace | QA controller/template | Saved-data browser click; values0/false/missing; no task mutation | Verified |
| Site information remains separate with its existing guarded cell editing | Existing Site information step | Direct step navigation, readonly/reviewer cases | Verified |
| Left pane contains checklist categories/tree, with no bottom evidence lists | QA template/controller | DOM location and preserved Not Assigned/AI-suggestion actions elsewhere | Verified |
| Categories, groups and sections initially collapsed; deliberate choices persist | QA tree/view state | Fresh browser, reload, search reveal and keyboard expansion | Verified |
| Category/point counts show distinct linked photos, separate from review decisions | QA tree/controller | Real mapping POST, same photo linked twice, reload and failed-save tests | Verified |
| Photos dominate a two-pane workspace; point-review tools remain optional | QA drawer/CSS | Desktop/mobile geometry, keyboard focus, dirty draft retention | Verified |
| Whole-task rejection works without individual photo/point review or finished AI | Existing route service | New6 HTTP tests and33 combined regressions; Engineer original/resubmit preservation | Verified existing behaviour |
| Required engineering approval checks remain enforced | Existing approval service | Approve without required review still refused; explicit task rejection succeeds | Verified existing behaviour |
| Category click shows linked point/section photo groups and empty points | QA grouped gallery | Real category with linked and empty checkpoints; source categories preserved | Verified |
| Genuinely unlinked category photos appear at the bottom | QA grouped gallery | Photos linked elsewhere excluded from unassigned; unique totals | Verified |
| No gallery paging/Next button; bounded lazy thumbnail browsing continues | QA gallery loading |200 unique category uploads in the460-record fixture; bounded36+24 loading and protected thumbnails | Verified UI scale, not AI throughput |
| Mapping success updates linkage badges/pools, failure preserves prior state | Existing saved matching actions/UI | Actual authenticated save/reload plus explicit503 retry case | Verified |
| Source, project/revision and role boundaries stay intact | Existing APIs and guards | Isolated backend/browser negatives and separate AppSec after completion | Verified within tested scope |
| Photo mapping alone cannot become a human data correction | General Info provenance | G1 reproduced through actual legacy map API, owner-approved repair, negative and real human blank/None re-tests | Verified repaired |
| Shared header and role-specific navigation remain consistent across pages | Shared navigation template/CSS |12 related backend tests,76 CSS cases; authenticated header matrix and repaired tablet collision | Verified within tested routes |

No new service, role, template-editing system or approval policy is introduced.
Photo linkage is not engineering approval. Optional review tools must remain
available for existing required checklist assessments; moving them into a drawer
does not weaken those server rules. Backend verification details:
`QA_TASK_REJECTION_WITHOUT_PHOTO_REVIEW_20261026.md`.

Before screenshots and executed REDs are retained privately under
`.local/qa-general-info-tree-20261026/`. Independent QA owns its own fixtures and
report; implementation and QA use isolated records/media, not customer writes.

Current suite:1,124 backend tests passed in411.511s, zero failures/errors/skips
and external attempts. All13 frontend scripts, Django/migration/dependency/
syntax/static checks passed. Independent gallery QA passed70 browser assertions
plus6 rejection tests; final authenticated header recheck passed60 assertions
across10 visits after a visually discovered1024px control overlap was repaired.
See `INDEPENDENT_QA_GENERAL_INFO_TREE_20261026.md`,
`INDEPENDENT_QA_SHARED_NAVIGATION_20261026.md` and
`SECURITY_REVIEW_QA_GENERAL_GALLERY_20261026.md`.

The broad all-file consistency gate detected the tablet CSS, its frontend test
and an asset-version edit during server tests. Its original receipt is retained.
Component proof verifies all Python/server navigation logic stable and all final
UI checks run after the edits; only a CSS cache token changed in the shared base.
Final source fingerprint:
`3c65563adf2f5140ac3235f3604285650639216e0e6b092e1941de12c2b195ca`.
Earlier C1/M1/W1/S1/S2/S3/R1/R2 holds remain separate and unchanged.
