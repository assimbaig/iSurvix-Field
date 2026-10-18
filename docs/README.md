# iSurvix Field documentation

## End-user documentation

Use [Software Manual](manual/iSurvix_Field_Software_Manual.pdf) for operating instructions, role responsibilities, project grants, checklist work, AI review visibility and approvals. The editable Word version is in the same folder.

## Internal development documentation

Use [Development Guide](development/iSurvix_Field_Development_Guide.pdf) for architecture, migration, authorization, test evidence and release preparation. The editable Word version is in the same folder. The [implementation plan](COMPANY_ACCESS_AND_AI_REVIEW_PLAN.md) and [local handoff](LOCAL_CODEX_HANDOFF.md) are also internal references.

The18October2026 [roadmap application register](roadmap/APPLICATION_PLAN.md) maps the retained source roadmap to the local Django implementation, delivered pilot controls, remaining Stage0-9 backlog and acceptance limits. Version1.6 manuals include independent review and a separate administration-only Super Admin console with a dynamic industry catalog.

## Final release policy

Distribute only the end-user Software Manual with the final software release. Development guides, superseded combined guides, test results, source references, local credential files and logs are excluded from the user documentation package. Keep internal engineering history separately; removing it from release contents does not delete the application's data or audit trail.

Run `scripts/package_user_manual.py` using the project Python environment to build `.local/release-documentation/iSurvix_Field_User_Documentation.zip`. Its explicit allowlist contains only the Software Manual PDF and DOCX.

The earlier combined Application Guide is superseded. An internal copy is retained under `development/archive`. A previously opened PDF may remain at its original path for compatibility; it is excluded from release packaging.

Industry-specific Admin invitations and mandatory Quality Engineer review are described in ROLES_AND_INVITATIONS.md. New internal review order is Engineer -> Quality Engineer -> Team Lead, then Client when required. Historical signed reviews are preserved.

Client creation and Client access grants belong to scoped Project Admins only. Super Admin views Clients read-only. Client organizations are separate from employer Company access boundaries.
