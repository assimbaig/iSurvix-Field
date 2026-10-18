# Roadmap application to iSurvix Field

Baseline date: 18 October 2026. Source: `Engineering_Intelligence_Product_Roadmap.pdf`, planning baseline1.0,36 pages. The unchanged source is retained in this directory.

## Scope and precedence

This is the local Django/SQLite/Ollama project at `F:\iSurvix\iSurvix-Field`, on branch `feat/local-photo-pilot`, source base `596c7c2385013d8712c46171b491edf1edb08568` with substantial existing local work. The PDF's React/Workers/D1/R2 repository and PR129 history describe a different source baseline. They do not prove that commercial, construction, asset or financial modules exist here. This implementation reuses the working local stack and evidence store rather than replacing them.

The roadmap explicitly prioritizes a bounded survey/inspection pilot before lifecycle expansion. This delivery applies that foundation. Original Stage0-9 numbers and requirement identifiers remain in this register; unavailable domains remain planned. Existing400-photo capacity and metadata-first processing supersede the PDF's historical200-photo reference. Existing activities retain their established review flow and saved approvals.

## Delivered local foundation

| Roadmap area | Applied behavior | Evidence and limits |
| --- | --- | --- |
| 0 baseline and recovery | Dated source/database/original backup, isolated restore, environment receipt | Private checkpoint and restore receipts in `.local`;78 original hashes verified. Local execution only. |
| 1 navigation | My work, Projects and sites, Review queue, Reports, Administration; scoped Telecom/Construction filter | Server filters records by current company/project/actor; Administration denied to non-admins. Site context remains on checklist, evidence, AI and review pages. |
| 1 roles and scope | Project Manager role plus explicit activity L2/L3/Client assignments; optional project-grant expiry | PM is invited as a non-admin role; project membership alone grants no independent activity access or signature. Expired/revoked grants defeat primary-project fallback. |
| SUR01 and TI01 context | Workflow type, asset/work location, coordinate source and datum/CRS | Three workflows: telecom survey, telecom inspection, construction inspection. Construction survey is not offered. Existing records are not reclassified. |
| SUR02 and TI02 templates | Published definitions frozen per activity; immutable technical applicability reviews tied to exact project/template/workflow/digest | Actual assigned PM records criteria source/edition/clauses, method, evidence and applicability. Publication alone is not technical qualification. No template is automatically technically approved. |
| SUR03-SUR05 and AI01-AI04 | Existing400-photo pipeline, preserved originals, authenticated retrieval, one cached observation per image, conservative suggestions and human confirmation | AI remains advisory; no invented measurements/pass/N/A. Labelled-dataset accuracy, physical-device throughput and hard400/30min maximum remain unqualified. Cancellation/cost accounting/provider expansion remain later work. |
| SUR06 and Stage2 governance | Opt-in independent L1 Engineer, L2 assigned TL, L3 assigned PM; immutable numbered submissions, digest checks and append-only decisions | Different actual people, current scope and ordered stages required. Admin/Super may configure access but cannot supply technical signatures. Existing legacy activity approvals remain unchanged. |
| TI04-TI05 and CON04 foundation | Finding/severity/blocking flag, source IDs, responsible Engineer, due date, remedy and independent retest events | Critical/blocking findings prevent validation/approval. Frozen inputs must first be returned. Upload alone does not close a finding. Detailed instrument/calibration/measurement-limit engine remains planned. |
| Customer release | Explicit applicability and named Client; C1 decisions against internally approved immutable revision | Rejection creates a linked correction repeating L1/L2/L3, preserving old internal approval and Client rejection. Approval checks the exact digest. Historic frozen JSON/HTML remains scoped to the named Client; current draft library access remains restricted. Legacy Client behavior is preserved. |
| Reporting | Scoped frozen HTML report and JSON export, original hash manifest, ordered decisions | Draft/submitted/approved/customer-rejected remain distinct. This is a traceable pilot report, not acceptance of every customer report format or professional certification. |
| 9 documentation | Separate end-user and internal Word/PDF guides, roadmap traceability and local handoff | Final documentation package contains only the end-user manual. Source PDF, internal guide, credentials and test evidence stay out of that package. |

## Governance and evidence rules

Independent mode is explicit. Its Engineer owner, TL validator and PM approver must be three distinct active project members; required Client release has another named actor. The creating TL may configure only the initial draft policy for the activity they actually created. Scoped Project Admin can configure draft policy; no reviewer can self-grant a foreign activity by knowing its ID. Super Admin is administration-only and cannot perform task/reviewer assignment or engineering execution. Policy cannot be rewritten after the first submission.

Super Admin has a dedicated global Dashboard, Industries, Clients, Projects and Sites console. IndustryCatalog removes the fixed two-industry administration limit; permanent codes and deactivation preserve existing project history. The current released engineering workflow types remain bounded separately. Direct content, file/export, template, photo/AI, task-intake and decision APIs reject Super Admin, including historical route aliases.

Submission freezes project/company/industry, workflow/asset/coordinate context, template/criteria qualification, source answers and attachments, original-photo hashes, confirmed locations, findings/events and assigned review identities. Validate/approve check the frozen digest. A reasoned return remains possible when inputs are stale; the next submission links its parent without rewriting the previous snapshot. Client rejection has a separate immutable C1 decision and correction branch.

No actual user is automatically made a PM. No new activity is fabricated, no existing activity is switched to independent mode, and no technical qualification or approval is manufactured as part of deployment. Admin must invite the real PM; the actual PM must qualify the intended template and the responsible people must perform acceptance.

## Remaining backlog in original stage order

| Original stage / requirement | Next bounded deliverable | Acceptance owner or prerequisite |
| --- | --- | --- |
| 0 / 9.4 | Record current source/configuration receipt and retain usable recovery package | Developer and owner; local checkpoint exists, external disaster recovery target needs agreement. |
| 1 / 9.3 | Actual desktop and Android/iPhone usability walkthrough, map/list and unsaved-context switching | Field users and UX; synthetic viewports are separate evidence. |
| 1 / 18 master data | Organisation/project catalogs with stable codes, deactivation and reviewed PM option authority | Owner-approved taxonomy and administration rules. Department/team/domain/level grants remain future extensions. |
| 2 SUR01-SUR06 | Real-device survey, linked evidence annotation, exact approved report and independent reviewer scenario | Engineer, TL, PM and customer where applicable. Existing11 sections/150 inspection items retained where appropriate. |
| TI01-TI06 | Qualified telecom inspection criteria, measured values/units/methods, instrument/calibration validity, retest and recurrence | Competent telecom reviewer. Numeric acceptance/calibration is not implemented by the current text criteria registry. |
| 5 CON01-CON06 | Approved design/method/readiness, receipts and lot reconciliation, ITP hold/witness points, tests/NCRs, commissioning, final quantities and dossier | Construction reviewer and real approved source records. This checkout has no accepted receiving/stock/serial/quantity engine. |
| 2 S06 / AI05-AI06 | Labelled authorised photo dataset, per-class precision/recall/critical misses, review effort and accepted capacity benchmark | Technical reviewer/data owner. External provider is optional and requires an explicit privacy/provider decision. |
| 3.1-3.5 | Source-governed design basis, discipline evidence, qualified calculations, coordination, customer design release | Accepted survey and competent engineering reviewers; full tower/CAD solver is not supplied. |
| 4.1-4.5 | Measured BOQ, dated rates/currency, sourcing, procurement authority, PO and variations | Procurement authority and reconciled project quantities. No technical signature implies spending authority. |
| 6.1-6.5 | Accepted asset register, hierarchy/custody, model/GIS provenance, receiver acceptance and retirement | Accepted construction dossier and asset owner; no automatic digital twin or receiver consent. |
| 7.1-7.5 | Contracts/SLA calendars, dispatch, preventive/corrective evidence, spares and measured service inputs | Accepted assets, service authority and operations reviewer. |
| 8.1-8.5 | Evidence-backed invoices, independent financial authority, reconciliation, retention/warranty and closeout | Contracts, eligible quantities and finance reviewer. No banking/tax integration or payment execution enabled. |
| 9.1-9.5 | Named field pilot, security/capacity/device checks, accepted reports, support owner and controlled release | Owner plus independent domain/customer acceptance. No production rollout or certification is inferred from passing tests. |
| ISO / business launch | Scope, risk/quality records, independent audit and actual commercial terms | Company management and external assessor. No certification, external spending or customer claim is made by this code delivery. |

## Verification and release status

Automated tests, browser fixtures, authenticated local checks, deployment and real-user acceptance are recorded separately in `../LOCAL_CODEX_HANDOFF.md`. The final full regression run passed236 tests in154.088seconds; the later15-case HTTP suite and focused missing-storage check passed after adding frozen-original retrieval. These overlap and must not be summed. Synthetic browser evidence covers39 navigation role/view/width cases and15 detailed roadmap view cases; actual field-device/customer acceptance remains open. Normal Engineer/TL/Client/Admin/Super sign-ins passed five destination checks, with Administration denied to non-admins. All legacy columns in7 business tables, all account identities/password hashes/roles and all78 original photo byte hashes match the preserved baseline.

The metadata benchmark remains about21-23minutes projected for400 similar photos, not a measured maximum including final review. Actual78-photo processing and saved metadata remain intact. The new pilot is local and requires real template qualification and named people before workflow acceptance. Future lifecycle modules remain explicitly unreleased.


## Current role and workflow amendment 18 October 2026

Super Admin creates industry-bound Admin invitations; only Super Admin changes the binding. Admin project access additionally requires company affiliation and effective explicit grants. Admin invites Client reviewers and assigns Engineer, Quality Engineer and Team Lead roles within its scope. New legacy submissions require named Quality Control before Team Lead approval. New independent policies use L1 Engineer, L2 Quality Engineer, L3 Team Lead and optional C1 Client; historical frozen TL/PM policies retain their recorded signatures. Returned historical activities must adopt the new policy before resubmission. No historic quality approval is fabricated. See ROLES_AND_INVITATIONS.md for current authority.


## Client ownership correction 18 October 2026

Only Project Admin creates Client organizations, issues Client reviewer invitations and adds Client project access within its assigned industry and company. Super Admin Clients is read-only. Migration 0032 introduces ClientOrganization and an optional Project link without changing existing Company tenancy, Client accounts or historical signatures. Old Super-issued Client invitations fail current issuer validation. Client context, when present, is included in new source digests; old snapshots are not rewritten.
