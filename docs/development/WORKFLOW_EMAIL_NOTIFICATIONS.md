# iField workflow email

iField sends workflow notifications from **ifield.notify@isurvix.com** through
the existing Microsoft 365 connection. Invitation delivery remains supported.
Notifications use the recipient's current registered account email.

## Events and recipients

|Event|Recipients and content|
|---|---|
|Task/site assignment|The assigned Engineer, including a newly created site whose checklist has not been opened. Genuine reassignment creates a new notification.|
|Reviewer assignment|The newly assigned, authorized reviewer.|
|Submission or resubmission|The reviewers required by the saved task's current workflow. QA handoff does not wait for AI analysis.|
|Approval or rejection|The submitting Engineer, applicable reviewers and project administration, subject to current access. The email links to the saved task.|
|Client review request|The authorized Client reviewers for that project when the workflow requests their review.|
|Draft or released report|Users allowed to access that particular report. Client report access follows the existing release rules.|
|Daily summary|An active participant's permitted project scope, including assigned sites without an opened checklist and without counting linked tasks twice.|

Full reports are provided as authenticated download links. Recipients sign in to
download the permitted revision. Emails exclude photo originals, internal review
remarks, AI findings and private storage paths. Email delivery never changes an
engineering decision or releases a report.

## Delivery and recovery

Saved workflow events queue durable notifications within the action's database
transaction. Network requests run in the background. Repeated processing of the same saved event
does not create another delivery for that recipient.

Before sending, iField rechecks the registered email, active account, company,
project, role and relevant assignment/report access. It checks again after OAuth
authentication. Revoked or stale access cancels the message.

Microsoft's **Accepted** response means accepted for processing; it does not
prove that the recipient received it. Use Microsoft message trace or the actual
inbox to verify delivery. Definite temporary failures have bounded retries.
Interrupted or ambiguous sends remain **Uncertain** and are not automatically
sent again. Inspect Sent Items/message trace before issuing a replacement.

## Operator configuration

The existing mail switch enables invitations and workflow notifications:

```text
ISURVIX_NOTIFICATION_EMAIL_ENABLED=True
ISURVIX_NOTIFICATION_PUBLIC_ORIGIN=https://app.isurvix.com
ISURVIX_NOTIFICATION_CREDENTIALS_FILE=/run/private/ifield-notification.json
```

Optional controls:

```text
ISURVIX_WORKFLOW_NOTIFICATION_EMAIL_ENABLED=True
ISURVIX_WORKFLOW_EMAIL_DAILY_ENABLED=True
ISURVIX_WORKFLOW_EMAIL_DAILY_HOUR_UTC=15
```

Daily summaries become eligible from 15:00 UTC by default: 18:00 in Saudi Arabia
and 20:00 in Pakistan. The configured hour must be an integer from 0 to 23. The
worker checks eligibility once per minute and deduplicates each project's
recipient/date. Existing application timestamps and timezone settings are unchanged.
The worker must be running for scheduled mail to be processed.

Use the same supervised worker as invitations; no additional public service is
required. From the project directory, with the approved private configuration:

```powershell
.local\venv\Scripts\python.exe backend/manage.py check_notification_email --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend/manage.py run_invitation_email_worker --settings=checklist.settings_local
```

The check command validates configuration without sending email. The worker
alternates eligible invitation and workflow messages. `--once` processes at most
one message; `--retry-failed --once` explicitly retries eligible definite failures,
while retaining uncertain outcomes for investigation.

Migration0061 adds the workflow outbox. Apply it through the reviewed upgrade
process, retaining existing records and the strict retention helper. Do not copy
the local development database into the VPS or replay historical actions to
generate emails. Keep credentials outside source, media, release packages and
managed data copies. See [invitation setup](INVITATION_EMAIL.md) and
[guarded delivery](HOSTINGER_DELIVERY.md).

## Verification boundary

Saved-record and controlled HTTP tests establish application behavior. Actual
Microsoft mailbox scoping, production activation and inbox delivery require
separate live evidence. Current results and any remaining gates are recorded in
the development handoff; this guide is not a claim that a release is live.
