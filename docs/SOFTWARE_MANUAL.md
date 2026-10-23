# Isurvix iField manual and audit policy

Current end-user manual: [Word](manual/iSurvix_Field_Software_Manual.docx) and [PDF](manual/iSurvix_Field_Software_Manual.pdf), version1.7 dated22 October2026. Existing paths and original history are preserved. Read the operational amendment on pages18–19 before relying on later features.

The current main source2d9440c and audited later developmentb907601 are different states. This documentation PR targets feat/secure-outbound-survey-workers deliberately; it does not promote runtime code into main or prove what is installed. Human review is required. Current roles and historical policy precedence are explained in ROLES_AND_INVITATIONS.md and the manual. The roadmap APPLICATION_PLAN.md retains future modules as planned.

The [22 October report](audits/2026-10-22-ifield-scope-audit.md) is the initial source baseline. Its persistent report identity, exact source coverage, excluded preview releases, open findings and preserved acceptance blockers are recorded in AUDIT_CHECKPOINT.json. There is no verified production counting baseline. Do not interpret null counters as zero or import Engineering Intelligence version44 or its findings.

After a verified production baseline, count only distinct successful production releases containing functional runtime changes. Count a combined batch once and record all included PRs. Exclude previews, documentation changes, failures, retries and unchanged-runtime redeployments. Inspect every intervening release. Audit the whole application each five qualifying updates; carry extras forward. A source commit, merge, saved version, deployment and acceptance are different events.

Before reporting, check existing reports and open PRs. An unmerged documentation PR with a delivered report is valid audit evidence. Advance only after report delivery and retain source/release IDs and history. Repeated checks below threshold remain quiet unless a material new blocker or critical defect appears. Report the unchanged F04 production-evidence blocker only once. Keep successive monitoring active.

Source tests and synthetic browser fixtures never replace actual model, field-device, engineering, production or recovery acceptance. Preserve existing iField roadmap backlog and the three hardening blockers hosting.vps-live, drawings.references and drawings.z-benchmark. No merge, deployment, account/access change, operational data mutation, engine enablement, purchase or unsupported claim closure is authorized by this policy.
