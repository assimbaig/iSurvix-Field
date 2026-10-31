# Company onboarding

This feature is on a review branch. It is not installed on the operational
database automatically. The reviewed deployment needs migrations through0055;
back up and rehearse them before applying to the operational installation.
Reversing0055 drops the new application table. Preserve its history in a verified
backup and assess rollback separately before reversing an operational database.

## Platform owner

1. Sign in as the existing platform owner. Open **Administration → Company
   onboarding → Record application** (`/governance/onboarding/apply/`).
2. Enter the received company name, its Admin email and an active industry.
   Recording an application creates neither a company account nor a project.
3. Review the saved details. Choose **Approve application** or **Reject
   application**. Rejection needs a reason and preserves the application history.
4. For an approved application, choose **Provision company**. This creates its
   distinct company record, without projects or operational access grants.
5. Choose **Invite company Admin**. Copy the private invitation link from the
   confirmation and share it through the approved private channel. The application
   does not send email. The link expires after72 hours and is accepted once.

The original bearer link is shown only in its creation response. Refresh or replay
does not issue a second invitation or regenerate the token. If lost, expired or
revoked, use existing **People and invitations** to explicitly revoke/reissue a
company-level Admin invitation for the same company and industry. The onboarding
record retains its original invitation reference; it does not pretend that an
explicit replacement is the original invitation.

An existing company or account is not claimed through a matching name/email.
Manage its existing access instead. Invalid transitions, duplicate conflicting
details and deactivated industries produce an error rather than a success state.
An interrupted action may be retried; repeated successful requests retain the
same records. If the database is busy, retry the action after the indicated delay.

## Invited company Admin

Open the private link and create the account using the existing invitation
acceptance form. Role, company and industry come from the saved invitation.
The account is a company Admin, not a platform owner. Its projects, operational
invites and decisions continue to follow existing project/company permissions.
There is no public company self-registration or automatic project creation here.

## Boundaries

Customer Admin, Engineer, QA, Team Lead and Client accounts cannot manage the
platform onboarding queue. Recording, reviewing, provisioning and inviting are
administrative actions, never engineering acceptance. Historical surveys, originals
and approval controls are preserved.
