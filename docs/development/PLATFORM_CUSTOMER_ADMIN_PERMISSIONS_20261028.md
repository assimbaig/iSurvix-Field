# Platform owner and customer administrator boundaries

Task 05 extends the Task 04 company boundary; it adds no roles or approval stages.
This policy describes the existing positive authority and the focused request and
audit hardening delivered on `feat/platform-customer-admin-20261028`.

| Operation | Platform owner (Super Admin) | Customer Admin |
| --- | --- | --- |
| Industry catalog and Admin industry binding | Global administration | Denied |
| Assign project owner / classify an eligible unowned project | Global administration; retained company records stay pinned | Denied |
| Invite Admin | Company and active industry required | Denied |
| Invite Engineer, Team Lead, QA | Existing non-Client administration supported | Managed projects, company and industry only |
| Invite Client / create Client organization | Denied | Managed company and industry only |
| Create company project | Denied | Bound company and active industry only |
| Grant/revoke project access | Administrative exception with existing company and Client restrictions | Operational accounts in managed company projects only |
| Change role, activity or lock state | Existing non-owner account controls | Only operational accounts whose entire active scope is managed |
| Promote existing account to Admin / Super Admin | Not available through member role changes | Denied |
| Access maintenance and global audit | Allowed | Managed-project audit only; maintenance denied |
| Engineering decisions | No authority granted by platform ownership | Existing frozen review policies only; no new approval authority |

All decisions use current persisted roles and company/project authorization. A
profile containing `SUPER_ADMIN` without the Django superuser flag gains no
platform authority. Existing company-boundary rules and historical review policies
remain controlling.

## Explicit account request boundaries

Account and invitation routes reject posted `is_superuser`, `is_staff`, `groups`
and `user_permissions` with HTTP 400 before making an otherwise valid change.
Member requests also reject company, industry and project authority fields;
membership requests reject role/company/industry authority fields. Their `_id`
aliases are also rejected. Invitation acceptance derives role, project, company
and industry from the stored invitation and rejects posted overrides without
consuming the invitation.

Platform invitation company/industry fields remain supported. Customer invitations
reject foreign company overrides. For compatibility, an operational invitation's
posted `admin_industry` is ignored: it cannot change the issuer's binding or grant
industry authority to the operational account. The server-selected project and
company remain authoritative. Existing CSRF and role guards remain in force.

## Audit and rollback

Successful member role/activity/unlock changes, membership grants/revocations,
Admin industry bindings, invitation creation/revocation/acceptance, project
creation/ownership/company/Client assignment, Client organization creation and
access maintenance retain their existing audit action and legacy details. A
versioned `privileged_change` envelope adds current actor, target, company/project
scope and allowlisted before/after state to the same event and transaction.

Snapshots query saved state; they omit passwords, token hashes, session contents
and raw requests. Existing legacy event fields are preserved. Membership snapshots
include effective primary-project context even when the legacy grant row is absent.
Admin invitation acceptance captures project ownership before profile-save and
membership side effects. Audit failure rolls back the corresponding mutation.

No operational database migration, customer-account action, engineering approval,
native AI call, merge or deployment is required by this change. Exact executed
checks and remaining review findings are recorded in the delivery evidence.
