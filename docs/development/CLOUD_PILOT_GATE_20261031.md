# Limited company pilot, measurements and release gate

Prepared 31 October 2026 for delivery tasks 13–15. Owner: Dot. This is an
execution procedure and evidence worksheet, **not a completed pilot or approval
to deploy**. No pilot, customer approval, paid inference or server change was
performed while preparing it. Complete private records under the F: project and
the approved server's protected data area; publish redacted summaries only.

## Current disposition

| ID | Task | Status | Completed date | Required acceptance evidence |
| --- | --- | --- | --- | --- |
| 13 | One limited company pilot after approved staging deployment | Blocked | | Approved target and cohort; actual Engineer→QA→Team Lead→Client, if required→released report; originals and human decisions preserved |
| 14 | Measure capacity and cost | Blocked | | Actual target workload/resource/billing records; measured limits and costs accepted by owner |
| 15 | Complete cloud release gate | Blocked | | Owner approves exact source/image/configuration; authorised deployment and versioned smoke/rollback results |

Tasks 03 and 07–09 retain their recorded blockers. The latest independent
tasks 10–12 fixtures are additional development evidence; their final broad
regression repair is still in progress at preparation time. A green subset or
draft PR is not a release gate. The owner's task list does not select a server,
approve spending, fix security findings or approve an engineering decision.

## Prerequisites and exact missing inputs

| Gate | Evidence available | Still required before execution |
| --- | --- | --- |
| Approved target | Disposable Linux staging rehearsal passed; deployment runbook exists | Approved VPS/SSH identity reference, private access route, DNS/TLS and operator deployment approval; do not use legacy example addresses |
| Reviewed release | Draft PR28 and PR29; AI implementation `98092c2` is a candidate, not an approved release | Final repaired source and full checks; reviewed full commit and immutable image digest; compatible server/worker versions and migration plan |
| Security disposition | D1/D2 High and earlier A12/BR1/L1/CS1/CS2 holds; separate AI1 Low audit-detail finding recorded | Explicit owner-approved repairs/disposition, affected retests and release security review; no finding is silently waived here |
| Recovery | Same-drive copies/restore drills preserved originals and records | Actual target backup/restore/restart plus off-device restore and retained secret/config recovery proof |
| AI path | Controlled HTTP/HTTPS image and proposal/output tests | Approved actual provider or native PC path, private credential references, consent, model/vision proof, actual connectivity/accuracy and offline-worker recovery on the target |
| Pilot cohort | No approved company/site/user list recorded | Owner-approved company, project/site IDs, template revisions, authorised evidence and qualified human participants; physical phone and network/browser list |
| Capacity/cost envelope | No target invoice, usage series or accepted limits | Approved test duration/concurrency/data envelope; actual hosting/storage/egress/provider/electricity inputs and owner acceptance |

No agent review substitutes for owner deployment, cost or exact-release approval.
Approval to repair a security finding is separate from approval to deploy.

## Task 13: bounded Engineer-to-report pilot

Use the existing application and its configured workflow. Use authorised pilot
data only; use isolated synthetic records for disruptive negative cases. Agents
must not make operational engineering approvals. Assigned qualified users perform
the human decisions through their existing roles.

Before starting, complete the run record:

| Field | Recorded value |
| --- | --- |
| Pilot run ID / authorised date window | Not supplied |
| Company and approved project/site IDs | Not supplied |
| Participants and current role/project grants | Not supplied |
| Template ID, published revision and checklist-required setting | Not supplied |
| Three-/four-layer route and optional Client stage | Not supplied |
| Evidence authorisation and private source manifest reference | Not supplied |
| Original count/types/bytes/SHA256 and initial record/history manifest | Not measured |
| Source commit / image digest / configuration version / migration state | Not approved |
| Worker/provider identity, model and private credential reference | Not configured; never record credential values |
| Device/browser/network / timezone and clock-offset check | Not supplied |
| Allowed duration, concurrent users/jobs, storage and stop thresholds | Owner approval missing |

Execute and attach the named evidence after every step:

1. **Provision and isolation:** complete the existing Apply→Review→Provision→Invite
   path for the selected company. Verify current company/project grants. Check
   anonymous and foreign-company denial using controlled accounts and private file
   URLs. Retain request IDs and denial results without credentials or evidence URLs.
2. **Assign:** Admin/Team Lead creates the permitted task with the selected
   approved template and route. Capture task/site/revision IDs and prefilled site
   information; correct required site data through existing permitted controls.
3. **Engineer upload:** upload Civil/Electrical/Tower photos and permitted sketches/
   reports using the existing intake. General Info remains site data. Record
   completed/failed/retried uploads, unique original IDs, categories and hashes.
   No checklist-point matching is assigned to the Engineer.
4. **Submit:** submit once and replay the same request on controlled pilot data.
   Record the immutable submission and job IDs. QA must see the task before AI
   finishes. Verify no duplicate revision/job/original for an exact replay.
5. **Actual AI:** use the approved live path. Record queue/start/end timestamps,
   eligible unique photos and document pages, completed/cached/failed sources,
   policy/model identities and attempt outcomes. Verify sampled actual image
   content reached the provider. AI results remain proposals; unknown dimensions,
   readings and compliance conclusions must remain missing/uncertain.
6. **QA:** inspect linked and unassigned evidence against the exact published
   checkpoint IDs. Correct/confirm links and review work using existing controls.
   Record human actor/time, saved revision and reload persistence. Background AI
   must not erase QA corrections or unsaved input.
7. **Return/resubmit:** on a deliberately chosen authorised test task, QA returns
   one stage with a reason. Engineer receives the retained photos/categories and
   previous permitted links; resubmission preserves unchanged completed analysis.
   Changed inputs create the retained appropriate revision. Confirm audit history.
8. **Human route:** QA and Team Lead review; Client acts only if that route requires
   it. Prove rejection moves only through the existing permitted route. Matching
   must never become engineering acceptance automatically. Save decision actors,
   stage transitions, comments and immutable revision references.
9. **Outputs:** inspect the draft checklist/PDF/DXF and missing-information notes.
   Release only through the existing qualified human approvals. Verify project
   branding, readable labels, common geometry and source references; do not infer
   missing manufacturer/site dimensions. Client cannot download unapproved drafts.
10. **Recovery and close:** use an agreed safe pause/offline/restart window. Verify
    queued work waits and completed sources do not rerun or duplicate outputs.
    Compare original hashes, record/history manifests and output revisions before/
    after recovery. Complete authorised target and off-device restore proof into
    new destinations. Record defects and the owner's pilot acceptance separately.

Pause the pilot immediately for cross-company exposure, changed/lost originals,
overwritten human decisions, unauthorised releases, incompatible worker results,
unexplained duplicate accepted work or an unapproved spend/load envelope. Preserve
records and diagnostics; use existing pause/recovery controls. Do not delete jobs,
overwrite data or disable access controls to obtain a passing run.

## Task 14: measurement worksheet

Use UTC event timestamps and monotonic durations where available; record client/
server clock offsets. Keep raw samples and denominators. Separate cold model load,
queue delay, inference, retries, cache reuse, human correction and export time.
Do not report p95 from a single site as a reliable capacity claim.

| Metric | Required raw observations / calculation | Actual result |
| --- | --- | --- |
| Upload completion | Unique successfully persisted originals/bytes; start→last successful upload; failed/replayed requests separate | Not measured on target |
| Upload/request latency | Per request duration/status/bytes; sample count, p50/p95/range and device/network | Not measured |
| Queue delay | First actual worker start minus durable job enqueue | Not measured |
| Sustained first-pass photo throughput | Unique eligible photos first analysed ÷ measured sustained analysis wall time; exclude cached/duplicate photos; include failures separately | Not measured |
| Document processing | PDF/sketch/workbook page/image counts and durations separate from photos | Not measured |
| AI completion latency | Final proposal-ready timestamp minus enqueue; also record worker-busy time and cold load | Not measured |
| Review/correction time | Human review start/end, corrected versus checked points/links, breaks and sample count | Not measured |
| End-to-end delivery | Authorised report release minus Engineer submission; separate queue/AI/human/export portions | Not measured |
| Concurrency and saturation | Observed active users/uploads/jobs; request latency/errors, queue age and recovery after each approved load step | Not measured |
| Resources | Timestamped CPU/RAM/disk/IO/network; GPU utilisation/dedicated VRAM/model timings where actually available | Not measured |
| Integrity and outcomes | Original hash mismatches, lost decisions, duplicate accepted results, missing/unsupported/incorrect findings and human corrections | Not measured |
| Recovery | Detection→recoverable service, successful retry, source reuse, target restore/off-device restore duration and hashes | Not measured |

Increase load only within the agreed envelope and stop before an unapproved next
step. Record the **largest tested workload meeting owner-approved latency/error/
recovery limits**, not an estimated unlimited capacity. A small-image upload test
does not prove sustained native-AI throughput or an equipment-accuracy benchmark.

Cost inputs must come from the selected provider's actual invoice/rate schedule,
timestamped usage and a declared allocation period/currency. No account prices or
commercial promises are supplied by this worksheet.

| Cost input | Evidence required | Value |
| --- | --- | --- |
| Hosting/compute | Actual plan/invoice, billed period and pilot allocation method | Not supplied |
| Storage/backups | Measured GB-month and copies/retention; billed unit rate | Not supplied |
| Egress/network | Billable transferred GB and rate; include evidence/download/backup paths | Not supplied |
| External inference, if approved | Actual billable requests/tokens/images, model rates, currency and invoice; include failures/fallback/truncation requests as billed | Not supplied |
| Local PC electricity, if included | Measured kWh or measured watts×hours and actual tariff | Not supplied |
| Shared operations | Actual monitoring/support/licensing costs and allocation basis; state excluded labour/depreciation explicitly | Not supplied |

`Allocated pilot cost = allocated hosting + storage + backup + egress + actual API
charges + included local power + allocated operations.`

`Cost per accepted report = allocated pilot cost / number of human-released pilot
reports.` With zero accepted reports, this is **undefined**, not zero. Attribute
failed/retry work and idle hosting explicitly. A monthly projection must identify
its measured workload mix, utilisation/headroom, retention and rate assumptions.
Configured attempt quotas are not token counts or a hard currency budget.

Owner acceptance record: measured capacity, tested limits, all cost inputs,
exclusions, budget/alert thresholds, approver identity and UTC date remain blank
until the owner accepts the actual results. Agents cannot fill that approval.

## Task 15: exact release record and smoke gate

Complete this record only after target staging, pilot and measurement acceptance:

| Record | Required value |
| --- | --- |
| Exact full source commit and reviewed PRs | Not approved; a moving branch is insufficient |
| Immutable application image digest and trusted provenance | Not supplied; a disposable runner image ID cannot be pulled as a registry artifact |
| Configuration/worker protocol and compatible implementation versions | Not approved; secret references only |
| Migration plan, target schema and stopped-writer backup manifest | Not approved |
| Actual target/off-device restore proof and rollback artefact | Not verified |
| QA/security disposition and owner-approved limitations | Pending; existing holds remain open |
| Pilot and measured capacity/cost acceptance references | Not available |
| Owner approval of this exact release, actor/time/scope/window | Missing |
| Authorised operator, target identity and deployment record | Missing |
| Pre-/post-deploy release identity, smoke evidence and result | Not executed |

The operator must verify the built release identity matches the approved commit,
private environment and compatible worker. Quiesce all writers for the reviewed
backup/migration procedure; do not replace an active database/media directory.
Rollback must preserve new writes: stop/quiesce, retain the failed release's
records/evidence, restore into a new verified target and reconcile changes before
activation. An old code image alone is not a database rollback plan.

After authorised deployment, record timestamp/version/request IDs for: HTTPS
readiness/static assets; anonymous/raw-media/foreign-company denial; Engineer
upload/submit; QA availability during processing; safe matching/save/reload;
Team Lead/optional Client route; authorised report download; draft-output denial;
worker disconnect/restart/retry; original/result/hash persistence; minimal health
and owner-only diagnostics. Use designated smoke fixtures or the authorised pilot
scope; agents must not manufacture customer approvals. Website availability must
remain independent of the PC; do not expose port11434 or production DB access.

Any failed release identity, privacy, integrity, human-approval or recovery check
keeps the gate closed. Only the owner's recorded exact-release approval and
successful authorised deployment/smoke evidence can complete task15.

## Existing evidence is preparation, not a pilot

- [Cloud staging delivery](CLOUD_STAGING_DELIVERY_20261031.md): disposable Linux
  install/restart/restore and 39 HTTPS browser checks; actual target remains blocked.
- [Independent AI QA](AI_SETTINGS_INDEPENDENT_QA_20261031.md): 30 browser checks and
  five explicit HTTPS fixture cases, including synthetic saved-survey draft outputs.
- [AI security review](SECURITY_REVIEW_AI_SETTINGS_20261031.md): AI1 Low remains
  unfixed; earlier deployment/dependency/security holds are not closed.
- [AI operator guide](AI_SETTINGS_GUIDE_20261031.md): current provider/worker
  limitations, private aliases, attempt quotas and human-review boundaries.

No measured cloud capacity, real-provider accuracy, costs, production readiness or
pilot acceptance is claimed by these development receipts.

## Candidate verification update

After preparation, application CI passed on4c40d1d: Windows1465passed, Linux1463passed+2Windows-only skips and Chromiumpassed. Local1464passed+1existing WinError1314 error. This does not close any target-deployment, native/live-provider, pilot, cost or owner-release gate above.
