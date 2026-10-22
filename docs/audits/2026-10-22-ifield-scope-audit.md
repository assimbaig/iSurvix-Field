# Isurvix iField application scope audit

22 October 2026 • Initial source baseline • For Muhammad Assim Baig

## Decision and scope

Isurvix-iField, formerly Field, has a substantial survey and inspection implementation, but a production-ready or engineering-accepted release cannot be established from the available evidence. Keep release approval open. Reconcile the current main branch, correct the numerical unit defect, then complete deployment and independent field acceptance before making operational completion claims.

This audit covers repository assimbaig/iSurvix-Field, the existing software manual, roadmap, release and verification registers, security and workflow source, isolated regressions and the historical Sites preview. It is today's requested initial baseline, not a claim that five qualifying production updates have occurred. Engineering Intelligence is a separate product; its version44 baseline, manual identity, seven-package implementation claims and 17-finding backlog are not transferred into iField.

The audit did not merge, deploy, restart the operational application, enable AI engines, alter real accounts or data, or execute purchases. Test records and files were synthetic and isolated. Recommended owners are proposed responsibilities, not assigned commitments. No target completion dates have been agreed.

## Source and release ledger

Two source states are material. Fresh GitHub branch reads and a full clone agree that main is 2d9440cf22770521abc17a2b35c659c79aea0b36. The later development branch feat/secure-outbound-survey-workers is b907601b8cac59cc111cb02f37489cc25073c866. Its predecessor d523a49429ff343b7b7a15a6f662d41ba51113eb is the recorded PR8 merge. PR records mark PR3–8 merged, yet those commits are not ancestors of the currently returned main. No cause is inferred. Main-to-development differs by 454 files, 82080 insertions and 1009 deletions. Audit conclusions explicitly identify which state they concern.

| PR | Recorded change and source | Ledger classification |
| --- | --- | --- |
| 1 | Initial application history, merged before PR2; main ancestor 1911122 | Source history only; no functional production receipt established |
| 2 | Local photo pilot, head 596c7c2385013d8712c46171b491edf1edb08568; merge 2d9440c on 19 October 2026 at 16:48:59 UTC | Current main; source change, not proof of deployment |
| 3 | AI survey and drawing workflow; head 5e1482901c9db84f258b51def00c01e9e28db7ae; merge b0cc818 on 21 October at 17:32:43 UTC | Later development history; production unverified |
| 4 | Guided checklist wizard and lifecycle library; head 6f9dea6289c52f02123fe7600a3bd45a92166f30; merge aeca905 at 17:32:56 UTC | Later development history; production unverified |
| 5 | Checklist revision selection and compact tree editor; head ba69c0d3ddc3e56fc1c7013d0411147ea7c40ab6; merge 90b4301 at 17:33:10 UTC | Later development history; production unverified |
| 6 | Single and bulk task intake; head 4ce27bd91e463de3a40a457ef2cec4dfd7afb2e5; merge 682174a at 17:33:32 UTC | Later development history; production unverified |
| 7 | Integrated survey verification, exports and review; head 79d977227e88db0ddab437aca3ffd3a6da5c60fb; merge 0651cff at 18:25:14 UTC | Later development history; production unverified |
| 8 | Private evidence and outbound AI worker; head d00fe9cbbfe0302639398d5289fd546f6eb0cdf4; merge d523a49 at 19:27:56 UTC | Later development history; production unverified |
| After PR8 | b907601b8cac59cc111cb02f37489cc25073c866 at 19:51:07 UTC on 21 October, role and workflow guide | Documentation only; excluded from functional release counting |

All seven intervening published versions of Site appgprj_6acff557885c8191b6d7219ee82099d1 were inspected with individual version/deployment receipts. All succeeded as publish operations. Repository documentation identifies this site as a historical static sample, not the current operational Django service. Its hosting publishes therefore do not establish qualifying iField production updates. Their source IDs are separate from the Django source history.

| Preview | Published UTC | Source ID | Deployment ID suffix |
| --- | --- | --- | --- |
| v1 | 14 October 2026 21:44:29.531152 | 6ecd1a362c13938e3449db191660105f7de835e4 | 6acff77a4f0c8191896360c7f0df633e |
| v2 | 16 October 2026 10:27:28.727800 | 0b84aa745e285c5faa3b10a8e6bd9911d6fffd65 | 6ad1fbdddec881918d68ee937c77a324 |
| v3 | 16 October 2026 11:59:10.803843 | a7b4bbbe5771e29e2370bf3aae03c13464539f23 | 6ad2114e952c81918cfd8ed6a8b8cf5a |
| v4 | 16 October 2026 12:14:37.797428 | d9815169dcbbd19f31a5c8c796719140e53599dc | 6ad214ec851c8191a0954a384df44e33 |
| v5 | 16 October 2026 12:17:13.211183 | 012229a919dbba8f31f3a3342c465f37ad738419 | 6ad215793eec8191bbce1da03ab6f6d8 |
| v6 | 16 October 2026 12:58:13.759259 | 6d3bdc82cebd5ab8ccf061b07a90cb9118a54ff2 | 6ad21f29921c8191bd002d8eeda43711 |
| v7 | 16 October 2026 13:14:09.864927 | 2e3e77d6acf21724e30c72167a1138413462654b | 6ad222e5eca8819190ddfdc4d42628c4 |

Each deployment suffix above is prefixed appgdep_. Preview URL: https://isurvix-survey-redesign.mirza-assim.chatgpt.site. The GitHub releases collection was empty when checked; the connector rejected deployment endpoint access, which is not evidence of no deployment. The actual local Windows installation and any VPS deployment receipts were unavailable here. Production baseline and qualifying-release count remain UNVERIFIED, not an assumed zero. No five-update batch is closed or counter advanced. Preserve extra qualifying releases for the next batch once real receipts become available.

## Purpose compared with current application

The documented near-term purpose is governed telecom survey and inspection, with a bounded construction inspection pilot. The roadmap's full lifecycle is a planning framework. The implementation must not be presented as an accepted design, procurement, asset, maintenance, invoicing or payment platform.

| Area | Status | Reason and evidence |
| --- | --- | --- |
| Purpose and scope drift | OK for source boundary | README and roadmap distinguish the local pilot from static preview and later lifecycle packages. Checklist and drawing expansion supports survey delivery. No completed financial lifecycle claim is substantiated. |
| Survey and inspection package | OK for source implementation; field acceptance unverified | Versioned templates, task intake, preserved evidence, findings, review and reports exist on b907. Native full-site performance and engineering accuracy remain open. |
| Design and engineering package | Unverified | Draft vector PDF/DXF output is implemented; approved dimensional references, design calculations and competent engineering acceptance are absent. Draft output is not a certified design. |
| BOQ procurement package | Not applicable to released pilot | Roadmap marks measured BOQ, rates, procurement authority, PO and variations as future. No accepted receiving or spending engine is claimed. |
| Construction delivery package | Unverified | Inspection pilot exists. Approved design/readiness, materials/lot reconciliation, ITP hold points, commissioning and final quantities remain planned. |
| Asset and digital twin package | Not applicable to released pilot | Accepted hierarchy, custody, GIS provenance, receiver acceptance and retirement remain roadmap dependencies. |
| Maintenance package | Not applicable to released pilot | Contracts, SLA calendars, dispatch, spares and service acceptance remain planned. |
| Finance and payment package | Not applicable to released pilot | Invoices, independent finance authority, reconciliation, retention and actual payment integrations remain planned. No SAQ-to-payment completion is inferred. |
| Modules and integrations | OK for source separation; integration acceptance unverified | Legacy photo/critical review and opt-in survey processing serve different functions. Local/outbound worker paths are documented. Automatic invitation email and external provider expansion are not delivered. |
| Company project and role scope | OK in later-source checks; defect in main | access.py checks company, active accounts and effective grants. Independent activity decisions require assigned actors. Main AppAdmin sign-in escalates to global Django superuser, finding F02. |
| L1 L2 L3 and Client independence | OK for source control; actual signers unverified | Current policy is Engineer, Quality Engineer, Team Lead, optional named Client. Frozen historical TL/PM policies remain historical. Administrators cannot replace technical signatures. L4 terminology must not imply an extra implemented technical stage. |
| Builder catalogs and branding | OK for source tests | Guided selection, full FDED definition, published revision locks, exact template selection, required fields and left/right client branding have dedicated passing regression suites. Customer-approved checklist content and export layout remain independent acceptance. |
| Project and site hierarchy | OK for inspected scope; subprojects unverified | Company, project, assigned activity and protected Site ID are represented. A complete separately governed subproject hierarchy was not established in this audit; do not claim it from a display filter. |
| Evidence integrity and Site ID | OK for scoped source controls; audit hardening gap | Frozen revision digests, source hashes, original manifests and exact-record file routes exist. EXIF GPS/time is source metadata and missing values are not invented; duplicate/corrupt upload behavior has passing tests. Site ID is protected in task preloads. General governance audit rows are mutable through ORM, F07. |
| Workflow rejection and archive | OK for inspected transitions; retention unverified | Legacy Client rejection preserves internal locks; independent rejection creates correction lineage and repeats preparation/review. Historic snapshots remain scoped. No independently accepted archive/purge policy was available. |
| Calculations and unsupported inputs | Defect | Finite Decimal values and dimensional checks exist, but case-folding silently changes SI meaning, F03. Measurements need independent source references; no structural solver acceptance exists. |
| Labels dates and completion claims | Defect | Manual v1.6 dated 18 October still says 400 photos; later local setting is 500 and guides include newer features. Roadmap earlier role descriptions need their later amendments read in precedence order. F08. |
| UX accessibility and mobile | Unverified overall | Prior synthetic viewport checks exist. Today's browser attempt was blocked by missing Chromium and failed browser download; no fresh browser layout result is claimed. Physical Android/iPhone, screen reader, keyboard, zoom and complete WCAG2.2 checks remain open, F11. |
| Security and private files | OK for later-source checks; production unverified | Exact attachment allowlists, auth/project scope, traversal rejection, no-store and nosniff, blanket Nginx media denial and bearer machine endpoints exist. Human routes use CSRF middleware; machine CSRF exemptions require bounded bearer authentication. Main has the older privilege defect. Live TLS/proxy/configuration is unverified. |
| Privacy | Unverified | Local inference and hashed scoped worker tokens reduce exposure. Data retention, export disposal, PC cache custody, incident owner and deletion obligations need owner-approved operating evidence, F12. |
| Performance and capacity | Unverified | Limits and local progress optimization are implemented; 500 is a permitted count, not a verified end-to-end service target. Prior 378-photo plus workbook/full-site benchmark remains blocked, F05. |
| Deployment and CI | Defect in release traceability; deployment unverified | Main/merged-PR mismatch, no GitHub workflow directory and no reproducible dependency lock found. Source tests do not establish installed runtime. F01 F04 F09. |
| Migrations | OK for fresh synthetic database; upgrade unverified | Today's scratch database migrated and model drift check is recorded below. Historical real-data migration/preservation receipts exist but were not independently replayed against private operational data. |
| Recovery and backups | Unverified operationally | Durable jobs, upload sessions, leases and retry checks exist; prior backup/preservation claims cover 53 core tables, 806 media files and 12 private files. Off-machine recoverability and actual RPO/RTO drill remain open, F10. |
| Remaining defects and closure | Defect and unverified items retained | This report adds F01–F12 and preserves the repository acceptance blockers and roadmap backlog. No previous test pass, reviewer signature or unsupported acceptance claim is closed by this audit. |

## Findings and regression requirements

Severity refers to potential impact if the affected code or operating claim is used. P1 is high priority before the relevant release; P2 is medium priority. Unverified items are evidence gaps, not proof that the deployed service is defective. Every finding below is OPEN. Satisfactory source controls above are not production acceptance.

### F01 Current main disagrees with merged development history

P1 • Defect in source and release traceability. Evidence: fresh branch and PR reads, clone ancestry and the source ledger. PR3–8 are recorded merged, but current main remains PR2. Owners: repository maintainer and release owner. Impact: a main-based installation can omit later access protections, workflow and drawing features while documentation implies they exist. Reconcile the intended protected release ref and explain the divergent history without rewriting evidence. Completion: one reviewed canonical commit, ancestry/PR manifest, installed source fingerprint and successful runtime receipt agree. Regression: a release check compares the deployed source and required security commits with the approved manifest. Do not fix this by blindly moving main or merging all development files in a documentation PR.

### F02 Legacy main grants AppAdmin global superuser privileges

P1 • Confirmed source defect on 2d9440c, conditional critical impact if exposed with tenant Admin accounts. Evidence: backend/core/views.py lines 74–108 on main authenticates an AppAdmin profile and saves is_staff=True and is_superuser=True. This bypasses the intended distinction between scoped Project Admin and global administration. Later b907 retires those handlers and uses separate scoped account routes. Owners: backend/security maintainer and release owner; depends on F01. Completion: the intended installation uses the corrected route set and no login path grants global privileges to project administrators. Regression: scoped Admin login preserves privilege flags; cross-company administration, exports, actor signatures and retired aliases are denied. Do not assume old privilege flags on real accounts have been remediated; inspect them through a separately authorized access review.

### F03 Unit case folding silently changes engineering values

P1 • Confirmed numerical defect on b907. Evidence: survey_processing.py numeric_evidence_value casefolds expected and observed units before checking conversions. Independent calls returned 1 MV as 0.001 V, and 1 mHz as 1000000 Hz. BIPM defines M as 10^6 and m as 10^-3. The nine-order magnitude discrepancy is material even if these forms were intended to be unsupported: unsupported input should be rejected rather than reinterpreted. Owner: backend calculation maintainer plus independent engineering reviewer. Recommendation: preserve SI symbol case, define explicit supported aliases, validate both sides before equality shortcuts and require human confirmation of ambiguous OCR units. Completion: approved unit vocabulary and dimensional contract reject unsupported/ambiguous forms and retain raw units. Regression: mV/MV, MHz/mHz, A/mA, m/mm, blank/unknown/same unknown units, cross-dimension, NaN/infinity and long exact decimals. Expected valid cases include 1200 mm = 1.2 m and 0.1 kV = 100 V; no unsupported case may silently change scale.

### F04 Operational deployment and release counter are unverified

P1 • Verification gap. Evidence: historical preview receipts, README local-only boundary, inaccessible operational source/process/VPS receipts, and F01. Hosting publication, merge and local tests are distinct events. Owner: deployment operator; depends on F01 F02 and approved environment. Completion: dated successful production receipt with exact source, included PRs, runtime settings fingerprint, migration result, private-file denial, TLS/proxy checks, authenticated role smoke and rollback reference. Follow Django's production deployment checklist and run check --deploy against actual production settings. Regression: failed deployments, retries, documentation-only changes and unchanged-runtime redeployments never advance the release counter. Establish a real baseline before counting five distinct functional releases. This audit reports the material blocker once; repeat only if materially changed.

### F05 Engineering accuracy dimensional basis and full capacity remain unaccepted

P1 • Verification gap carried from the existing release ledger. Evidence: RELEASE_HARDENING_REQUIREMENTS.json retains blocked live installation, approved manufacturer/CAD references and full-site accuracy/throughput. Prior native checks processed small photo/document samples; prior progress endpoint benchmarks and synthetic uploads do not prove 500-photo inference completion, accuracy or maximum time. Owners: competent telecom/construction reviewer, field pilot lead and performance engineer. Completion: authorized labelled dataset, per-class precision/recall and critical misses, approved real measurements and references, measured target hardware, full supported site/workbook batch, recovery and reviewer effort. Agree limits before testing. Regression: missing/unsupported measurements remain visible, drawings remain Draft for review/Not to scale where applicable, no AI pass/N/A/certification is manufactured, and retry/capacity results are reported with actual hardware/model/dataset and elapsed time. Do not transfer a projected 400-photo/30-minute estimate into a 500-photo guarantee.

### F06 Drawing text loses Arabic and other non ASCII labels

P2 • Confirmed source defect on b907. Evidence: survey_drawings.py _text encodes ASCII with replacement; an independent Arabic site-label probe produced question marks. Impact: site names, customer text or measured annotations can lose meaning in drawing output. Owner: drawing/export maintainer; depends on approved language coverage. Recommendation: preserve Unicode through data normalization, choose PDF fonts with required glyphs and set DXF text encoding/font strategy explicitly. Completion: independently read PDF and DXF retain the exact site and measurement labels. Regression: Arabic, mixed Arabic/Latin, accents, RTL layout, degree symbols, long names and export/import round trips. If output is deliberately restricted, reject and explain unsupported characters before release rather than silently replacing them.

### F07 General governance audit records are not append only

P2 • Confirmed model hardening gap on b907, with privileged ORM access as the threat boundary. Evidence: GovernanceAudit inherits models.Model without the immutable protections used by technical processing records. A synthetic record could be rewritten and deleted through ordinary ORM methods. No remote user edit endpoint was demonstrated. Impact: durability claims alone do not establish tamper resistance for account/grant audit history. Owner: security/backend maintainer. Recommendation: define retention/tamper threat model, restrict update/delete paths and database privileges, preserve an independent audit stream where required. Completion: documented trusted-operator boundary and tests proving prohibited mutation through supported application/admin paths; external tamper evidence if required. Regression: actor/action history survives deactivation, grant revocation and approved retention handling; distinguish technical append-only events from general audit durability.

### F08 Manual and roadmap precedence lag the implemented source

P2 • Confirmed documentation defect. Evidence: existing end-user manual v1.6, 18 October, says up to400 photos while settings_local and later UI use500. The core manual predates newer processing, drawing, worker and recovery instructions. Earlier roadmap paragraphs describe TL/PM before the current QA/TL amendment. Owner: documentation owner with workflow reviewer. Today's amendment updates the existing manual in place, preserves historical-flow explanations and adds dated operational boundaries. Completion still requires human review against the canonical release from F01. Regression: manual version, dates, role names, limits and feature availability are checked against the approved source; historical policies remain explicitly labelled. The user's product name changes presentation, not repository paths or proof of installed capabilities.

### F09 Reproducible release and CI enforcement are not established

P2 • Source/process gap. Evidence: no .github workflow directory in the audited trees; requirements mix version ranges and selected pins without a complete lock/hash manifest. Today's Python3.12/Django6.1.2 isolated environment differs from earlier Windows receipts; native OCR/embedding dependencies were not installed or enabled. Owner: build/release maintainer. Recommendation: pin and review a supported runtime, retain dependency/build manifests, and run isolated tests, migration drift, frontend checks and security checks as required PR gates. Completion: reproducible clean build from an approved commit plus review-enforced CI evidence. Regression: dependency upgrades and missing native prerequisites fail clearly; tests cannot read operational databases, download models or call external inference unexpectedly. Absence of repository workflows does not prove that all external CI is absent.

### F10 Operational recovery and backups need an independent restore drill

P2 • Verification gap. Evidence: prior source checkpoint and preservation receipts exist, but their private archives, database/media/configuration and restore target were unavailable. Fresh synthetic migrations do not prove upgrade or disaster recovery. Owner: operations/data custodian. Completion: encrypted recoverable off-machine backup, documented keys and retention, agreed RPO/RTO, isolated restore with database integrity, original-file hashes, role boundaries and resumed jobs, followed by a rollback rehearsal. Regression: interrupted upload, worker crash, expired lease, disk full, missing/corrupt original, migration failure and cache/model loss preserve original records and do not duplicate decisions. Never overwrite newer operational data during a restore check.

### F11 Full accessibility and physical field-device usability remain unverified

P2 • Verification gap. Evidence: prior synthetic browser receipts and today's blocked browser attempt are narrower than an end-to-end real-user evaluation. Owner: UX/QA with actual Engineers and reviewers. Completion: real Android/iPhone and desktop walkthrough of capture, interrupted upload, scope switching, editing, rejection/correction and exports, plus keyboard, focus, error announcements, contrast, 200 percent zoom/reflow and screen-reader checks against WCAG2.2. Regression: no unexpected page overflow, hidden save/error state, inaccessible controls or stale-source action after network interruption. Keep camera/offline/external-phone setup explicitly unaccepted until exercised.

### F12 Privacy retention and worker cache operating controls need approval

P2 • Verification gap. Evidence: source contains scoped hashed worker tokens, HTTPS checks, no credential forwarding on redirects and local inference boundaries; operating evidence for retention/deletion, PC cache custody, incident handling and accepted customer data use was not available. Owner: data owner and deployment/security operator. Completion: approved data inventory, retention/export disposal, authorized worker custody, token rotation/revocation drill and incident/recovery owner. Regression: expired/revoked/out-of-scope tokens fail, private evidence never appears under public media URLs, stale grants cannot retrieve files, and logs exclude secrets. No cloud-provider consent or customer acceptance is inferred from a local test.

## Verification performed today

| Check | Actual result today | Interpretation |
| --- | --- | --- |
| Main isolated Django suite | 36 tests passed in75.686seconds | Old-source regression only; does not cover newer security/workflow claims |
| Later-source isolated suite | 729 tests passed in757.451seconds; zero skips/failures/errors; system check clean | Python3.12 and Django6.1.2; synthetic database/media/model cache; no real inference |
| Network isolation | Zero external attempts;32 allowed connections to test-created local HTTP fixtures | No operational Ollama, cloud AI or private service used |
| Frontend checks | All four scripts passed from frontend directory;13,61,12 and39 synthetic screens reported separately | Script rendering checks, explicitly browser_layout_QA=false; counts overlap and are not added |
| JavaScript syntax | 32 backend static JavaScript files passed node --check | Syntax only, not interactive acceptance |
| Fresh migrations and model drift | Scratch database migrated; makemigrations --check --dry-run returned No changes detected | Does not replay a private populated operational upgrade |
| Independent probes | Compatible conversions, long Decimal, NaN/dimension rejection satisfactory; SI case, Unicode and audit mutability reproduced | See independent-probes.json; these defects are outside passing regressions |
| Authenticated source render | Synthetic photo workspace returned200 and28196bytes; home returned302 | Django test client only; no browser or real device |
| Browser and accessibility | Chromium absent; installation failed with invalid/truncated download; no browser session obtained | Today's browser layout/mobile/accessibility checks unverified |
| Actual deployment engineering and recovery | Not executed; unavailable operational receipts, references and restore assets | Open acceptance blockers remain |

The four frontend checks were first invoked from the repository root and failed on relative fixture paths; rerunning from their documented frontend working directory passed. The first syntax command used an empty top-level glob; the corrected recursive file list checked32 files successfully. These harness corrections did not change product source. The supplemental probe script used a corrected fixture method and route name before its successful isolated results. No failed preliminary browser attempt is counted as acceptance.

Independent numerical checks exercised compatible and incompatible dimensions, finite-number rejection, long Decimal preservation, case-sensitive SI hazards and Unicode drawing text. They use the application functions directly, not screenshots or expected values copied from the implementation. A synthetic GovernanceAudit update/delete reproduced F07. Valid conversions and invalid dimension/NaN rejection were satisfactory; the case and Unicode probes failed the intended engineering contract.

Source inspection covered access.py, account_views.py, legacy_routes.py, private_files.py, governance_models.py, survey_processing.py, survey_processing_models.py, survey_evidence.py, survey_drawings.py, remote_worker_service.py, remote_worker_views.py, remote_worker_client.py, production/local URLs/settings and Nginx configuration. Supporting tests cover actor/scope denial, immutable revisions, stale decisions, upload recovery, document limits, worker leases/tokens, drawings and client release. The isolated full suite is the source-regression gate, not an assertion that every production route or engineering input has been accepted.

The existing 21 October hardening ledger reports64 verified and3 blocked rows. Prior evidence includes729 ordinary tests, native Nginx denial checks, local browser and parallel-upload recovery, small native qwen3.5:4b runs, vector PDF/DXF comparisons and preservation hashes. These are attributed historical claims. Private original logs and operational backups were not independently rehashed today. Earlier counts overlap and must not be added together. No actual model inference, engineering site acceptance, live VPS check or operational restore was executed here.

## Ranked action plan

| Rank | Action and proposed owner | Dependency and completion criterion |
| --- | --- | --- |
| 1 | Reconcile release source and legacy privilege exposure — maintainer and security owner | F01 F02; approved canonical commit and installed fingerprint agree, scoped Admin remains non-superuser, required security commits present |
| 2 | Correct and independently review SI unit handling — backend and engineering reviewer | F03; supported symbols/aliases approved, ambiguous and unsupported units rejected, nine-order scale regressions pass |
| 3 | Complete controlled deployment evidence — deployment operator | Rank1, approved environment and backup; TLS/proxy/private-media, migration, role smoke and rollback receipts; establish production baseline |
| 4 | Run engineering and capacity acceptance — field lead and competent domain reviewers | Ranks1–3 and authorized dataset/references; accepted precision/critical misses, actual full-site benchmark, measurements and signed criteria |
| 5 | Repair Unicode export and harden governance audit — export and security maintainers | F06 F07; independent PDF/DXF round trip and documented tamper boundary/tests |
| 6 | Add repeatable build and CI gates — build maintainer | F09 and approved source; reproducible environment and required review checks with retained results |
| 7 | Prove backup recovery and privacy operations — operations and data owner | F10 F12; off-machine restore, RPO/RTO, revocation, retention and incident ownership accepted |
| 8 | Complete device accessibility and manual review — QA UX documentation and field users | F08 F11; actual-device scenarios, WCAG evidence and manual matched to accepted runtime |

Keep the existing roadmap backlog in original order: source/recovery; real-device survey; catalogs and grants; qualified telecom criteria/instrument calibration; construction readiness/materials/ITP/commissioning; labelled AI accuracy; design basis/calculations; BOQ/procurement; asset/GIS custody; maintenance/SLA; invoices/reconciliation; support/release and business certification. These are not newly completed modules. Retain the three hardening blockers and all earlier local runtime-refresh limitations until independently resolved with evidence.

## Evidence index and continuation policy

Repository: https://github.com/assimbaig/iSurvix-Field

Exact later source: https://github.com/assimbaig/iSurvix-Field/tree/b907601b8cac59cc111cb02f37489cc25073c866

Exact main source: https://github.com/assimbaig/iSurvix-Field/tree/2d9440cf22770521abc17a2b35c659c79aea0b36

Primary repository records at later source: README.md; docs/README.md; docs/roadmap/APPLICATION_PLAN.md; docs/ROLES_AND_INVITATIONS.md; docs/LOCAL_CODEX_HANDOFF.md; docs/RELEASE_HARDENING.md; docs/REMOTE_SURVEY_WORKER.md; docs/WORKFLOW_CRASH_RECOVERY.md; docs/manual/AI_SURVEY_TEAM_GUIDE.md; docs/manual/CHECKLIST_CREATION_GUIDE.md; docs/development/RELEASE_HARDENING_REQUIREMENTS.json; docs/development/INTEGRATED_VERIFICATION_REQUIREMENTS.json and INTEGRATED_VERIFICATION_RECEIPT.json. The existing manual is docs/manual/iSurvix_Field_Software_Manual.docx and its PDF companion. Prior journey evidence remains in LOCAL_CODEX_HANDOFF.md and dated receipt files.

Independent references accessed22 October2026: BIPM SI prefixes, https://www.bipm.org/en/measurement-units/si-prefixes; SI Brochure ninth edition, https://www.bipm.org/documents/20126/41483022/SI-Brochure-9-EN.pdf; Django deployment checklist, https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/; W3C WCAG2.2 recommendation, https://www.w3.org/TR/WCAG22/. BIPM supplies dimensional prefix meaning, not site-specific acceptance limits. Manufacturer/design references and engineering sign-off remain required.

Continue the daily check under Isurvix-iField. Read the checkpoint, this dated report, current manual and open PR/report history before emitting another batch. A delivered report in an unmerged documentation PR counts as an audit record; lack of merge is not a reason to duplicate it. Count only distinct successful functional production releases after a verified baseline; one batch deployment counts once with all included PRs. Exclude previews, failed deployments, documentation-only changes, unchanged-runtime redeployments and retries. Audit every fifth qualifying update, carry any excess to the next batch, and retain covered deployment/source IDs. Until release evidence is available, keep the counter unverified and report only a materially changed blocker. Do not resume Engineering Intelligence monitoring or borrow its counters.
