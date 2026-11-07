# Password recovery and notification email

## Reset your own password

1. Open the iField sign-in page and select **Forgot your password?**
2. Enter the email address registered to your account.
3. Open the password-reset email and use its private link. It expires after 30 minutes and works once.
4. Choose a new password, then return to sign in. Resetting the password does not sign you in automatically.

The confirmation is the same for registered and unregistered addresses. It does not confirm that an email was delivered. Check spam and contact your company administrator if the message does not arrive.

Requesting another link invalidates the previous link. An account email change, password change or sign-in can also invalidate an outstanding link. Disabled accounts and accounts deliberately locked by an administrator cannot use recovery to bypass that restriction. If more than one account has the same email address, contact your administrator to resolve the ambiguity.

iField never emails a password. Never reply with a password, verification code, invitation link or reset link.

## Invitations and action messages

- Company onboarding invitations explain how to activate the company administrator account.
- Project invitations identify the company, project and assigned role. Clients are invited by the authorised company administrator.
- Both use the existing invitation process and private, expiring links. Replaying the same onboarding step does not create another invitation delivery.
- Workflow notifications retain the existing company/project restrictions and human approval rules. Email acceptance is not engineering approval.
- Branded messages use the iField logo and an automated-message disclaimer. Custom company messages remain plain-text inputs and are safely formatted for email.

Messages are sent from **ifield.notify@isurvix.com**. This mailbox is not a support-reply channel; use your company administrator or the contact route agreed with iSurvix.

## When an email does not arrive

The application queues messages; the supervised email worker sends them. Microsoft 365 accepting a message does not prove that it reached an inbox. A message can be delayed, filtered or rejected after acceptance.

Ask the platform administrator to check email activation, worker health and the saved delivery status. An uncertain send is retained for investigation rather than automatically resent. Do not repeatedly request invitations or reset links while a delivery is being investigated.

Recovery requests are bounded to three per account, ten per source IP and one hundred overall per hour. These controls protect sending capacity; they do not change your account's permissions.
