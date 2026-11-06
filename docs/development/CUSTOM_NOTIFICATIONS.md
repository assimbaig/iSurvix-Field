# Custom notification implementation and release gate

## Existing integration and coverage

The implementation extends `workflow_email.py` and `invitation_email.py`; it does not add another mail provider or worker. `run_invitation_email_worker` already services both durable queues and calls the daily scheduler. Graph remains the existing server-managed transport; no credentials are exposed by these controls.

| Business action | Saved source | Recipients/control |
|---|---|---|
| Initial/reassigned task | WorkAssignment transition audit | Current assigned Engineer, source binding rechecked |
| QA reviewer assignment | quality_assigned audit | Assigned QA and site permission |
| Engineer submission/resubmission | Category/survey/revision/review-route audits | Current next-stage reviewer; duplicate emitted workflow events suppressed |
| QA/Team Lead/Client approval, rejection, return | Existing workflow/revision/processing events | Existing stakeholder and current-stage rules |
| Client review request | Existing routing audit | Designated, authorized Client |
| Draft/released reports | Saved drawing set | Existing authorized roles; current release/download gates rechecked |
| Project creation, Admin/company/client assignment, access grant/revoke, account role/activation/unlock | Explicit allowlisted governance audits | Current project Admin and relevant authorized target |
| Company-only client creation, Admin industry binding and account changes | Explicit company-bound audits | Current company Admin or the subject of their own account change |
| Account invitation | Existing InvitationEmailDelivery | Private invitation's existing validity/recipient rules; mandatory link retained |
| Combined report | Authorized durable notification rows within frozen business-day window | One current registered user, one company, all still-authorized project events; own authorized invitation events included |

Platform-global catalog/maintenance/settings changes remain available in the application's audit tools; they do not broadcast customer information. No notifications are emitted for keystrokes, gallery browsing, per-photo upload progress, AI polling, failed validation, or rolled-back business actions. Unregistered applicants do not acquire accounts or operational access from notification delivery. A submission, photo link, email or digest never accepts engineering work.

## Settings and rendering

`CompanyNotificationSettings` is company-owned, optimistic-versioned, and updated through an Admin-only service/view. The owner may manage any company's policy; customer Admins can manage only their current company and must retain active industry authority. Unknown fields, cross-company requests, stale versions and CSRF failures reject. Audit records retain configuration version, nonsecret schedule changes, template kinds and content digest, not custom body text.

The placeholder formatter accepts fixed names only, with no attribute/index lookups, conversions, format specifications, HTML or header injection. Custom subjects are validated for worst-case 200-character expansion. Body templates are validated for UTF-8 expansion and must preserve the mandatory combined summary. Runtime checks retain the existing transport limits.

The shared outbox keeps its existing unique event/recipient key, current-role/company/project rechecks, leases, retry limits and uncertain-outcome rules. Uncertain sends are not retried automatically. Before-send rendering builds a fresh authorization cache; repeated notifications on the same task do not repeatedly load large evidence JSON. Combined jobs save their exact business window in `event_key` while deduplication remains bound to company/day/recipient.

The nullable `digest_started_at` and `last_digest_day` settings fields implement opt-in activation and resumable catch-up. Queueing one completed day and advancing its cursor are one transaction. Three days per company per scheduler tick bounds catch-up work. Enabling after a disabled interval starts at the new activation date; template edits retain the cursor. Time-zone/time edits apply to future unqueued days, and already-queued windows remain frozen.

## Migration and deployment prerequisite

**0064_company_notification_settings** adds one empty table only. Existing outbox rows, evidence, accounts, approvals and permission assignments remain untouched. There are no operational data changes or automatic company opt-ins.

The supported-upgrade target advances to0064. The reviewed `upgrade_fixture.py` explicitly validates the new table's exact columns/types/nullability, empty initial state, two foreign keys, company uniqueness/user index, positive-version/JSON constraints,0064 marker, one content type and four correct default permission rows. Unknown/removed old data, privilege changes, triggers and unrelated retained-table indexes remain rejected. Actual isolated0057→0064 and0063→0064 migrations are tested.

**Install the reviewed0064 trusted retention helper on the VPS/customer update controller before authorizing the candidate deployment.** The installed0063 helper is intentionally insufficient and would safely reject the new permission metadata; do not bypass that gate. The controller/worker must use the same reviewed release. Run the disposable customer-server and staging pipelines against the final integrated commit, then obtain the release's normal human approval.

Root integration: add `notification_settings_index` to the new Super Admin System tools and the Company Admin's existing administration/settings area. Customer Admin requests automatically redirect to `notification_settings_company(company_id)`; owner gets a paginated company selector. No shared header templates are changed by this feature branch.

## Verification evidence

- Isolated unit/integration tests cover malformed placeholders/headers, multi-byte size limits, cross-company and role/CSRF boundaries, stale saves, customized invitation link preservation, per-day/event deduplication, source revocation, outage/cursor recovery and actual migrations.
- A representative1000-distinct-saved-event fixture retained all1000 counts, used39 SQL queries and produced a616-byte body in about0.07seconds in the isolated Windows test environment. This is a message-rendering check, not100K-user or native-mail throughput evidence.
- A2000-project-group/multibyte fixture verifies explicit shortening and all-event totals below40KiB.
- Browser settings verification uses an isolated database and media, disabled mail transport, and real saved settings at1920/1366/390 widths. No operational emails are sent by development tests.

Separate AppSec review reported NU1 (Low): an additional restrictive SQLite CHECK could pass the old presence-based new-table validation. The owner approved the fix. The0064 helper now compares the entire canonical CREATE TABLE constraint contract as well as PRAGMA fields/FKs/indexes and metadata. Independent retest passed9/9; no further findings in that bounded review.

