# iField invitation email

Sender: **iSurvix iField Notifications <ifield.notify@isurvix.com>**.
Transport: Microsoft Graph OAuth client credentials. No mailbox password,
Hostinger SMTP account, paid email API or DNS change is required by this code.
The owner has created the shared mailbox and single-tenant app registration.
Sending still requires valid application credentials and mailbox-scoped authorization.
Mailbox creation alone does not authorize sending.

## Microsoft 365 authorization

The tenant administrator must register a single-tenant application and authorize
its **Application Mail.Send** role for this mailbox using Exchange Online
Application RBAC. Verify that another mailbox is outside its scope. Do not also
grant an unrestricted Entra Mail.Send permission: Microsoft documents that these
permissions are additive, which would defeat the mailbox restriction.

- https://learn.microsoft.com/en-us/graph/auth-v2-service
- https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac
- https://learn.microsoft.com/en-us/graph/api/user-sendmail

Use a private JSON file with exactly these keys; the sample contains placeholders,
not usable credentials:

```json
{
  "tenant_id": "YOUR-TENANT-UUID",
  "client_id": "YOUR-APPLICATION-UUID",
  "client_secret": "YOUR-PRIVATE-APPLICATION-SECRET"
}
```

Keep the file outside source, media and static directories. On Windows use a
private ACL; on Linux use a regular file owned by the application service user,
mode 0400 or 0600. Symlinks/junctions and group/world-readable POSIX files are
rejected. Never paste the secret into chat or commit it. A shared mailbox's own
sign-in can remain blocked; the application authenticates as its registered app.

## Application configuration

New settings default to disabled, preserving manual invitations in existing
installations. After authorization, configure the web and worker environments:

```text
ISURVIX_NOTIFICATION_EMAIL_ENABLED=True
ISURVIX_NOTIFICATION_PUBLIC_ORIGIN=https://app.isurvix.com
ISURVIX_NOTIFICATION_CREDENTIALS_FILE=/run/private/ifield-notification.json
```

The origin must be HTTPS and match an explicit Django ALLOWED_HOSTS entry. Local
development records must not be emailed with a production URL: the cloud and
local databases are separate. For development use isolated tests below.

The web creates one outbox entry in the invitation transaction, without sending
over the network. Apply migration **0060_invitation_email_delivery** to the target
database through the reviewed deployment workflow. It adds an outbox table and
does not rewrite existing invitations, tokens, users, surveys or evidence.

Commands, using the configured deployment's interpreter/settings:

```text
python manage.py check_notification_email
python manage.py run_invitation_email_worker --once
python manage.py run_invitation_email_worker
python manage.py run_invitation_email_worker --retry-failed --once
```

The check validates local configuration only; it never requests a token or sends
mail. The worker needs outbound HTTPS to login.microsoftonline.com and
graph.microsoft.com. It must run as the existing application service user against
the same database/settings/secret, with no public listening port.

## Hosted activation gate

This change does not deploy or start a VPS worker. The implemented supervisor
starts Gunicorn and, when explicitly enabled, a separate email-worker process
inside the existing web container. Both stop at the same controlled writer
boundary. Email waits until trusted public HTTPS readiness reports the exact
running release, so a private verification candidate cannot send invitations.

`deploy/notification-email.override.yaml` provides an optional fixed read-only
mount from `/etc/isurvix-staging/ifield-notification.json` to
`/run/private/ifield-notification.json`, the public origin and outbound connectivity.
No third service or public port is added. Credentials stay outside managed data
copies: upgrade recovery retains database/media, not arbitrary secret files.

After owner review, install the reviewed trusted controller and merge these mail
settings into the existing trusted public override. Retain the controller's
two-file runtime policy and all other mount/port/user checks. Provide the private
credential as service UID10001 mode0400. Validate the composed configuration and
private configuration before enabling delivery. Do not launch an unmanaged third
writer or copy secrets into source, packages, media or static directories.
Owner-approved PR merge and exact-source checks remain required. No live runtime
or policy was changed during implementation.

The trusted host retention helper must also be updated from this reviewed source
before a 0060 deployment: the previous helper recognizes 0058 metadata only.
The new rule admits only the exact empty outbox table, recorded migration and
one content type/four default permissions with positive IDs. It grants no user
or group permissions. Do not waive retained-row checks or run a candidate's
unchecked installer as root to make an upgrade pass.

## Sending and recovery

- Onboarding and normal company/project invitations use the same outbox.
- When disabled, existing manual link generation works without an outbox entry.
- Existing invitation hashes and 72-hour, single-use acceptance rules remain.
- For new queued invitations, a random delivery UUID and a purpose-specific HMAC
  derive the token. Only its hash and the UUID persist. Protect the Django secret;
  retain SECRET_KEY_FALLBACKS when rotating it with unsent invitations.
- The worker rechecks issuer authority, company/project/industry and invitation
  availability immediately before sending. It cancels revoked, expired, accepted
  and unauthorized invitations.
- Requests happen outside short claim/finalization database transactions.
- OAuth and send requests each have a 20-second absolute deadline covering DNS,
  connection/TLS, headers and body. Public readiness has a five-second total
  deadline. DNS children are killed/reaped on timeout; HTTP cancellation does not
  leave background HTTP request threads running.
- Graph 202 is **accepted for processing**, never proof of inbox delivery.
  Check Microsoft Sent Items/message trace and the controlled recipient's inbox
  for real delivery acceptance.
- Definite transient rejections retry with bounded backoff, at most three attempts.
  Operator `--retry-failed` explicitly requeues definite failures.
- An interrupted/ambiguous POST becomes **uncertain**. It is not automatically
  sent again. Inspect Sent Items/message trace before explicitly issuing a new
  invitation through the existing authorized flow. An old link can be revoked.
- Error text/audits omit provider bodies, bearer links, credentials and tokens.
  Delivery status is visible beside the invitation and after refresh.

## Isolated verification

From F:\iSurvix\iSurvix-Field:

```powershell
.local\venv\Scripts\python.exe scripts\run_backend_tests.py core.test_notification_email_transport core.test_invitation_email core.test_invitation_email_independent --verbosity 1
```

The transport tests include real loopback HTTP requests with controlled responses.
These establish request formatting, failures and state handling, not live
Microsoft authorization or email delivery. No operational invitation is sent by
ordinary tests. Do not recover previously issued raw links from hashes or silently
replace them during activation.
