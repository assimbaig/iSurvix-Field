# Company access and Team Lead AI review

Implementation plan for the approved 17 October 2026 changes.

Status: implemented locally and migrated. All 145 combined tests passed, followed by
a focused Client cache/visibility check. Twenty-four responsive synthetic checks and
the native local-model critique probe passed. Database/media preservation and live
authenticated checks passed. See the handoff for exact evidence and remaining limits.

## Required behavior

1. A company groups projects. A Project Admin can manage multiple projects in that company. Super Admin controls company and administrator provisioning.
2. Team Leads, Engineers and Clients receive one primary project by default. An administrator can explicitly grant additional projects within the same company. Selecting a project establishes the working context; additional access never crosses company boundaries.
3. Existing accounts retain their current role, primary project, answers, photos, template snapshots and approval history. Additive migration converts existing project access into explicit memberships without expanding it across unrelated projects.
4. Assigned Engineer submission, actual Team Lead internal approval and authenticated Client approval remain distinct signatures. Final engineering records remain locked. Client routing considers the new project membership model without rewriting historical closure.
5. A Team Lead can request an AI checklist review that highlights critical issues, contradictions, missing evidence and questions for human review. Local Ollama remains the inference provider. The review cannot change answers or approve work.
6. AI checklist reviews are internal by default. A Team Lead explicitly controls whether a current review is shared with the Client. Client access still requires Final status and project authorization. Revoking sharing removes Client access; changed checklist content makes old reviews stale and ineligible for sharing.
7. Generic exports and text context must not accidentally disclose internal review content. Source references, uncertainty and audit provenance are retained.

## Delivery sequence

- Backend: company and membership schema, conservative migration, authorization/query audit, invitations, grant controls and Client routing.
- AI: persisted review, bounded structured local inference, validation, role gates, snapshot freshness and sharing audit.
- Interface: company/project controls, primary and extra grants, project context, Team Lead review and optional Client view.
- Verification: migration preservation, company isolation, multi-project authorization, strict stage signatures, private/shared/stale review cases, regression suite and responsive checks.
- Operations: consistent pre-upgrade backup, apply migrations, restart the existing local launcher and worker, authenticated read-only checks.
- Documentation: separate internal Development Guide and end-user Software Manual using the established brand palette. The final release distribution includes only the Software Manual; development notes remain internal.

## Acceptance limits

Synthetic automated/model tests do not establish real-site accuracy or production readiness. No automatic certification, fabricated measurements, approval bypass, cloud fallback or destructive factory reset is authorized.
