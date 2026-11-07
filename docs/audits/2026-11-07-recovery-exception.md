# Isurvix-iField — urgent recovery exception, 7 November 2026

This is a targeted audit supplement, not a repeated initial audit or a completed five-production-release audit. Tracking issue: https://github.com/assimbaig/iSurvix-Field/issues/41. Human review required. No runtime code, production data, access, engines or deployments were changed by this audit.

## Decision and scope

**New High-severity evidence-loss risk R01; P0 review priority.** The current repository controller can select automatic rollback after a journal interruption following possible public writes. No actual loss was observed. Installed root-owned controller bytes could not be inspected; application artifact identity does not establish the installed host controller identity.

The delivered 22 October whole-application source audit remains the baseline. Its source coverage, F01–F12 findings, manual v1.7 and acceptance/revalidation requirements are preserved. This supplement does not close them or extend whole-application coverage. Production baseline and qualifying count remain null/unverified. The protected-beta delivery policy explicitly withholds unrestricted production release and engineering approval; beta receipts are retained separately, without counting merges/retries as production updates.

Repository identity 1422193579 remains assimbaig/iSurvix-Field. Main remains 2d9440cf22770521abc17a2b35c659c79aea0b36; current release integration is 7414975dc8a9afe6549a13a51e9a21a11fcde1ae. Main still lacks the audit policy/manual files. No GitHub releases exist. Static preview versions 1–7 are unchanged and excluded.

## Intervening beta delivery ledger

All times UTC, 6 November 2026. These are five protected-beta transitions, NOT five qualifying production releases. Metadata history was inspected at each commit, with actual Actions jobs/attempts checked. Earlier 4 November beta provenance and PR34/35 transitions remain historical evidence.

|PR|Exact application source|Schema|Delivery run|Attempt/result|Metadata commit/time|
|---|---|---|---|---|---|
|36|972a71d141b86d8bc04f49d2154fd708dbbc344e|0061_workflow_email_delivery|42207475930|1 failed; 2 success|58665d950c48d3e416bc15523553be82e8f36817, 11:21:24|
|37|12d46ae805ab41bd53268da67772a512ffb4100f|0062_release_notice_acknowledgement|42228353040|1 failed; 2 success|c10beb55eb3d5e7f3b845c71a0344f8f8feb01e2, 14:06:51|
|38|d45db7a1dfe385b39a15ee1adf0c62c8937b6f3e|0062_release_notice_acknowledgement|42238879614|1 success|208c2a63c1340696d1bba2fedbc39f9c24a1cd50, 15:04:59|
|39|8b39decc28638f19fc7ab584e6ebbe97238fb46a|0063_checklist_template_company_scope|42250996899|1 failed; 2 success|ae52484900b558a9fdfee84c5653b51676437ec6, 16:28:15|
|40|17a699a98a9925b1095172b787af7ebedbd60919|0064_company_notification_settings|42274462978|1 failed; 2 success|df2166721b26d258ad040496d4e3e295c64cd616, 19:01:19|

PR36 adds invitations/workflow mail; PR37 scoped company administration/release notices; PR38 host diagnostics; PR39 company checklist ownership; PR40 company desk/custom notifications/combined daily reports. PR38 is a host delivery change, not evidence of an additional application functional production update. Failed attempts/retries and disposable CI are excluded independently.

Metadata channel files bind each exact source, merge, manifest, artifact and app/nginx image. Current app image: sha256:abc6d8ac40509cc4c57ac54307bbede610322682b8b27bb6d62d5885f870353b; artifact 13531370643. Current successful job 128089868539 reports “Server confirmed completed.” Earlier failed jobs 127857699387, 127927602081, 128005820946 and 128087184796 report delivery failed with records not reset. Private operator journals are unavailable: exact private failure causes are not independently established by these public logs. PR37/39 notes attribute rollbacks to old trusted retention helpers, subsequently reviewed and retried.

## R01 — diagnostic phase can erase the public-write recovery boundary

**Status: Defect (source verified); installed-controller applicability Unverified. Severity: High. Impact: potentially unavailable newly accepted records in the active application, deployment outage and manual reconciliation.**

Source: deploy/hostinger/controller.py at 17a699a, introduced by PR38 and retained in PR40. Engine.run lines 346–350 freeze only when saved phase equals public_opening; other incomplete phases invoke rollback. The exception handler at lines 377–385 saves failure_phase, then persists phase=failure_recorded before freezing for public_opening/completed. An interruption between that persisted write and freeze leaves a durable journal whose safety boundary is recorded only in failure_phase. On restart that field is ignored.

Sequence:
1. Candidate listener opens, so a human/API write may be accepted.
2. A caught health/activation exception triggers diagnostic journaling.
3. failure_recorded is persisted with failure_phase=public_opening (or completed).
4. Process/host interruption occurs before operator_recovery_required is persisted.
5. Restart selects rollback instead of freeze.

Engine.rollback (lines 321–335) validates/restores the earlier backup to a new directory and makes it active. Keeping the failed target on disk avoids claiming byte deletion, but does not preserve newer accepted records in the active application. This differs from PR38's separately mentioned pre-existing unexpected-exception finding: R01 specifically concerns the newly persisted diagnostic phase and loss of the monotonic public-write boundary.

Evidence: the actual AST-extracted Engine.run was executed locally against two synthetic journal records. For phase=public_opening it invoked freeze and returned operator_recovery_required. For phase=failure_recorded with failure_phase=public_opening it invoked rollback and returned recovered. The attached reproducible dispatch check is stdlib-only and uses no operational database, services or network. It proves branch selection, not actual on-server data loss or a complete restore test.

Recommendation: preserve an irreversible public-write marker across every journal update, and recognize prior diagnostic records carrying public_opening/completed as recovery-required. Do not automatically restore an older backup after possible public writes. Keep target, backup and journal for operator reconciliation. Any fix requires owner approval, independent fault-injection review and exact installed-controller verification.

## Satisfactory and limited checks

|Area|Status|Evidence/limit|
|---|---|---|
|Identity and baseline deduplication|OK|Stable repository ID; unchanged 22/23 October audit blobs, checkpoint and manual hashes; no duplicate whole-app report.|
|Exact-source CI|OK for CI only|All four PR40 required workflows succeeded at exact17a699a: 42269705198, 42269705203, 42269705339, 42269705199. Earlier failed/superseded checks do not establish acceptance.|
|Rollback attempts surfaced|OK / Unverified causes|Actual failed and successful retry jobs inspected; private failure journals unavailable.|
|Current protected-beta provenance|OK for recorded delivery|Exact source/schema/artifact/image bindings and successful delivery job; not unrestricted production or field acceptance.|
|TLS and public identity|Partially verified|Read-only proxied HTTPS HEAD /login/ returned405 with Allow GET,POST and security headers on7Nov; /healthz/ yielded no useful identity. A subsequent proxied HTTPS GET /ops/health/ready/ returned status=ready and exact release17a699a98a9925b1095172b787af7ebedbd60919 on7Nov. Web retrieval unavailable. PR38's expired-certificate note is not independently confirmed as a current expiry; no direct certificate-chain or authenticated browser acceptance claimed. Successful controller code uses default verified TLS, not an insecure bypass.|
|Mail activation|Unverified independently|Latest handoff records owner-enabled mail, positive/negative mailbox scope checks, controlled inbox confirmation and one supervised worker. Private activation receipts unavailable; do not reopen admin login, recreate grants or send audit email.|
|Migration retention|Unverified independently on actual server|PR40 reports0064 retained-data verification, strict schema checks and reviewed helper; isolated/CI evidence differs from direct server acceptance.|
|Recovery after diagnostic journal write|Defect|R01 actual-method synthetic dispatch reproduction; installed root helper applicability not verified.|
|Whole-application engineering/mobile/native AI/capacity/backup acceptance|Unverified by this supplement|Existing gaps and earlier findings remain; no new whole-application retest or claim closure.|

## Ranked action plan and completion criteria

1. **P0 — Owner + deployment maintainer:** review R01 before any further delivery or automatic recovery retry. Dependency: read-only installed controller hash/bytes and private journal phase. Completion: determine exact applicability and preserve every target/backup; no blind rewind after possible writes. This is a recommendation, not an access or deployment change performed by the audit.
2. **P0 — Assigned implementer after owner approval + independent QA:** repair monotonic public-write handling. Completion: real disposable SQLite/media fault injection immediately after diagnostic journal persistence for public_opening AND completed; insert a synthetic accepted row after opening, restart actual controller and prove freeze/no backup activation/retained row and originals. Also inject journal-write and freeze failures. Pre-opening failure recovery must continue passing. Synthetic dispatch alone cannot close R01.
3. **P1 — Release maintainer:** retain per-attempt failure reasons and exact reviewed helper version before upgrades. Completion: independently verify approved host-controller hash, exact release/schema and non-destructive recovery proof, with all release gates preserved.
4. **P1 — Product owner + audit maintainer:** establish production classification and baseline only from approved operational scope and successful receipts. Completion: exact source/runtime/provider evidence; then count functional production updates. Beta labels, five merged PRs or version increments do not satisfy it.
5. **P2 — Documentation maintainer:** reconcile stale current/historical handoff sections and README after review; preserve history and manual edition identity. Existing engineering/native/capacity/licensing/security holds remain until their separate evidence is accepted.

## Source/check references

- PR38: https://github.com/assimbaig/iSurvix-Field/pull/38 (introduced diagnostic phase; separate unexpected-exception note).
- Current source: https://github.com/assimbaig/iSurvix-Field/blob/17a699a98a9925b1095172b787af7ebedbd60919/deploy/hostinger/controller.py
- Current delivery: https://github.com/assimbaig/iSurvix-Field/actions/runs/42274462978
- Metadata: https://github.com/assimbaig/iSurvix-Field/blob/df2166721b26d258ad040496d4e3e295c64cd616/channel.json
- Policy: docs/development/HOSTINGER_DELIVERY.md at17a699a; docs/AUDIT_CHECKPOINT.json blob e58b769f796f48c4fe42819ff5d926aa9ceb9caa.
- Baseline audit blob af6c4615262fb76c01561db68d724f34efc3e09f; manual DOCX407bc75b742cca6505567b96ba6a2ad807d19d85 and PDF769c59e0acc82c954dc32e614fef9aedfbd17894 unchanged.

No production checkpoint advances. No earlier findings are closed. This supplement is delivered separately because of a newly verified evidence-loss risk, not because an initial or five-update audit is due.
