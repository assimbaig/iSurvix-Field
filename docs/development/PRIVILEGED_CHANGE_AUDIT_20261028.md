# Privileged-change audit evidence

Task 05 adds structured privilege snapshots to the existing `GovernanceAudit`
events. It does not add an approval mechanism, a second audit stream, a new
database table, or a platform-owner route into customer projects.

## Contract

`core.privileged_audit` provides persisted snapshots for users, projects,
project memberships, invitations, client organizations and maintenance counts.
`change_details(...)` returns one `privileged_change` details entry:

```json
{
  "version": 1,
  "actor": {"id": 12, "role": "ADMIN", "company_id": 3},
  "target": {"kind": "user", "id": 21},
  "scope": {"company_id": 3, "project_id": 8},
  "before": {"id": 21, "role": "ENGINEER"},
  "after": {"id": 21, "role": "QUALITY_ENGINEER"}
}
```

This is an abbreviated shape illustration, not a live account or a complete
snapshot. Actual helper output contains the allowlisted authority fields.
The existing event retains its action, timestamp, actor name, project reference
and legacy top-level details. Callers merge the envelope into that event rather
than creating an additional event. Authorization remains the caller's duty.

The privileged mutation and audit insertion must remain in the same
`transaction.atomic()` block. If insertion fails, the mutation rolls back.
Creation uses `before: null`; deletion may use `after: null`. A missing explicit
membership is represented with `exists: false`, not null: the user's current
primary project, role and company remain visible because legacy affiliation can
confer authority even without a membership row.

## Allowed information

- User: ID, current persisted role, effective company and primary project IDs,
  administrator industry ID/pending flag, active/staff/superuser flags, lock
  state and failed-login count/time.
- Project: ID/name, company, administrator, client organization, industry,
  checklist revision and review-layer configuration.
- Membership: ID/existence, user/project/company IDs, user's effective company,
  primary project, role, grant active/primary flags and expiry.
- Invitation: ID, company/project/industry, role, creator and acceptor IDs,
  expiry/acceptance/revocation times.
- Client organization: ID/name, company/industry and creator IDs.
- Maintenance: counts of sessions, locked profiles and open invitations only.

Password values or hashes, invitation secrets/hashes, email addresses, session
contents/keys, worker credentials, request bodies and arbitrary model fields are
excluded. Unknown fields and values with invalid types raise validation errors.
Snapshots query persisted records, including the object's database alias,
rather than trusting cached related objects or unsaved attributes. JSON-ready
snapshots are detached from caller dictionaries, so later in-memory mutations
cannot rewrite them.

## Integrity boundary

The existing audit model prevents application ORM updates, replacement upserts
and deletion of event content. Actor/project references can become null under
their existing lifecycle policy; snapshots and `actor_name` remain. No schema
change is needed. These controls are not database-administrator tamper proof:
raw SQL, database credentials, backup access and retention require separate
operational protection. No unbounded denied-request logger was introduced.

## Verification receipts

Private execution logs are under
`.local/platform-customer-admin-20261028/audit/` in the feature worktree.

- `red.log` / `red.json`: executed pre-implementation regression run. The real
  role-change HTTP event lacked before/after evidence; helper behaviors were
  absent. Existing audit-failure rollback already worked.
- `helper-green.log` / `helper-green.json`: eight isolated tests pass, including
  persisted-role freshness, secret exclusion, detached snapshots, membership
  existence/revocation, invitation redaction, maintenance counts, nondefault
  database reads and actual HTTP audit-failure rollback. The runner reported
  zero external network attempts.
- `integrated-green.json`: the complete nine-test module passes after the
  endpoint owner integrated snapshots, including the successful real HTTP role
  change, exactly one event, unchanged legacy details and before/after scope.
- Existing `core.test_governance_audit_integrity`: seven tests pass; event
  updates/deletes/upserts remain rejected and supported lifecycle nulling
  preserves snapshot content.

Full endpoint integration and independent security review are recorded by the
Task 05 delivery ledger; helper-only checks do not establish complete endpoint
coverage. Do not infer release readiness from this contract document.
