# Separate post-functional platform/customer security review

28 October 2026. This phase followed the frozen13-test independent functional
suite and35-check actual browser verification. The reviewer used the installed
Agency Application Security Engineer definition and attacked actual Django
authorization and audit services using isolated records. No product edits or
new security repairs were made during this phase.

## Attempts and observed result

`security_assault.PlatformSecurityAttacks`: **9/9 passed**, zero external network
attempts. Private receipt:
`.local/platform-customer-admin-20261028/qa/separate-security.log`.

1. Cached Python superuser/staff flags did not survive stored flag revocation;
   actual platform mutation remained403.
2. Cached Admin roles and a newly locked Admin could not retain mutation or
   project authority.
3. A profile claiming `SUPER_ADMIN` without the stored superuser flag, forged
   Python flags and forged session role/dev-admin flags did not elevate a Client.
4. Foreign Engineer/Admin memberships, foreign project IDs and platform-owner
   membership targets were denied with no grant or target-state change.
5. A valid authenticated customer-Admin without a CSRF token received403 for an
   otherwise-valid mutation; existing active state remained intact.
6. Forged account company, platform role and staff fields could not move a user
   across company boundaries or grant global authority.
7. Audit snapshot injection of password, token hash, email, nested role objects,
   string booleans and contradictory company/project scope was rejected.
8. Audit actors were read from persisted state, ignoring forged cached Python
   staff/superuser/profile values.
9. Existing events resisted application ORM save/update/delete/bulk-update;
   stored content remained unchanged.

Independent functional checks additionally verify valid-CSRF invitation
acceptance, role changes, audit rollback, project Admin assignment and scoped log
visibility. Supplemental positive tests confirm legitimate owner industry
binding and all four customer operational invite roles remain usable.

## Findings, severity and recommendations

**No new exploitable authorization or privileged-audit issue was established in
the executed scenarios.** This is a bounded result, not a universal security
claim. No new remediation was applied after review.

**Informational - audit trust boundary.** Append-only guards protect ordinary
application ORM operations, not a compromised database administrator, raw SQL or
filesystem access. Before production, retain independent database access control,
backups and log-retention controls. Cryptographic/WORM audit storage would be a
separate requirement, not an implied property of this change.

**Informational - supported legacy invitation field.** Customer operational
invites safely ignore the historic `admin_industry` POST value and derive saved
authority from the approved project/issuer. The value cannot rebind the Admin or
mint platform authority. Preserve its regression coverage rather than describing
the compatibility path as a demonstrated privilege escalation.

**Verification limit.** This is not exhaustive concurrency testing, production
DAST, deployed proxy/storage validation, host compromise testing or native AI
verification. Existing approved exceptions for owner administration of non-Client
accounts were preserved; no narrower role policy was invented. Existing held
security findings remain held. Any subsequently discovered defect requires the
owner's separate approval before repair under the repository rules.
