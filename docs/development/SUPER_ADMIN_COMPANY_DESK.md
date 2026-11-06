# Super Admin Company Management Desk

Release: **V1.2 Beta**. Feature branch: `feat/superadmin-company-desk-20261106`.

- Reuses Django governance and onboarding routes and the existing Apply → Review
  → Provision → Invite services, with no model migration or approval-policy change.
- `core/superadmin_dashboard.py` supplies real paginated records and bounded,
  parent-scoped hierarchy selections. No raw frozen submission payload is exposed.
- Super Admin alone receives Dashboard / Companies / System navigation. Legacy
  tools remain reachable; other-role navigation remains unchanged.
- Onboarding dialogs fetch approved same-origin routes and preserve CSRF,
  submitter actions, validation errors and normal-page fallbacks. Frame-denial
  security headers remain in force. Return destinations use a fixed enum.
- Local source checkpoint: `.local/backups/superadmin-desk-20261106/`.
- Independent saved-record browser evidence:
  `.local/superadmin-desk-qa-20261106/` (isolated database/media).
- Independent security regressions: `core.test_superadmin_security_independent`.

Run isolated backend checks with the existing project Python environment and
`scripts/run_backend_tests.py`. Run the frontend suite with
`node frontend/run-checks.cjs`; it discovers `check-superadmin-desk.cjs`
automatically. Final results and hosted checks belong in the PR release notes.

The separate live-email activation is an operator configuration change. This
feature does not activate mail, alter mailbox permissions or change recipients.
