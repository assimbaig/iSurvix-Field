# Custom notifications and combined daily reports

Company Admins can edit their own company's messages. The platform owner can choose a company; other companies and operational roles cannot read or change these settings.

1. Open **Notification settings** from the company administration tools.
2. Choose an action above the editor. Leave **Use the standard message** checked for the existing wording, or enter a custom subject and plain-text message.
3. Use only the displayed placeholders. A practical message is `Hello {recipient_name}` followed by `{default_body}`. Combined reports must contain `{summary}` or `{default_body}` so their counts cannot be removed.
4. To replace the old per-project daily task summaries, enable **Send one combined daily notification report across projects**. Choose the business-day cut-off and IANA time zone. The suggested settings are **18:00 / Asia/Riyadh**; **Asia/Karachi** is supported.
5. Save. This settings request sends no email. The existing background mail worker delivers subsequent notifications.

A business day runs from the previous day's cut-off up to today's cut-off in the saved zone. Daylight-saving transitions use the real 23/25-hour interval. The combined report counts that recipient's still-authorized notification events across company projects. It includes action and email-state totals, with project groups; it does not include private evidence, AI findings, internal review comments or invitation bearer links.

**Accepted by mail server** means Microsoft accepted the message, not that the recipient opened it or that inbox delivery was proved. Failed and uncertain sends remain distinct. The report includes registered users' own account-invitation notifications; unregistered invitees receive the normal private invitation email.

Without the combined option enabled, existing per-project daily summaries continue. Existing settings are not silently activated during upgrade. After an outage, each worker tick catches up at most three completed business days per company, then resumes from its saved cursor on the next tick. Empty days advance the cursor without sending empty messages. Queued days retain their original time window even if settings are edited later. Repeated ticks or retries do not create a second report for the same company, recipient and business day.

The combined report is bounded to the existing email transport limit. Every authorized event remains in the action/status totals. If project detail groups do not fit, the message states exactly how many groups are displayed and provides an authenticated application link. It never silently claims the shortened list contains every group.

Subjects must remain single-line and fit 200 characters after maximum placeholder expansion. Long-body, summary and URL placeholders belong only in the message. Body expansion is validated against the 64 KiB UTF-8 transport budget. Do not paste passwords, API secrets or private evidence into templates.

For invitation customization, the actual current private, expiring, single-use invitation URL is always retained in the invitation email. That URL is never included in daily reports, saved template text or audit records.
