# Roles industries and approval workflow

Open `http://127.0.0.1:8000/governance/`. Keep the project and all local data under `F:\iSurvix\iSurvix-Field`. The local test app accepts loopback connections only.

## Administration and industry scope

Super Admin has exactly five primary destinations: Dashboard, Industries, Clients, Projects and Sites. This role administers accounts, industries, projects, access, audits and maintenance. It cannot view engineering answers or photos, assign engineering tasks, change templates, request AI review or sign operational decisions. These restrictions apply to direct URLs, old aliases and registered operational Django admin models.

Super Admin invites Project Admin with an explicit active industry matching the initial project. Invitation acceptance preserves that binding. Only Super Admin can change an Admin industry. Admins cannot alter it through their own account, project selector, grants or forged form fields. Industry changes immediately restrict accessible projects without deleting historical grants. Existing Admins with an unambiguous industry are bound during migration; ambiguous accounts await Super Admin assignment and have no project access until resolved.

A company groups related projects. An industry binding does not itself grant all projects in that industry: explicit active, unexpired project membership and company affiliation are also required. Admin can manage multiple such projects, invite Client reviewers and create or assign Engineer, Quality Engineer and Team Lead accounts. Existing people receive additional project grants rather than duplicate identities. The same Team Lead, Engineer, Quality Engineer or Client can receive multiple project grants from an authorized Admin. Revocation or expiry overrides legacy primary-project fallback.

The Super Admin Clients tab is read-only. Only Project Admin creates Client organizations and Client reviewer accounts. ClientOrganization belongs to the Admin company and industry; Company remains the employer/access boundary. Admin can link a Client organization to managed projects in the same company and industry. Super Admin cannot issue Client invitations or add Client project grants. Previous Super-issued Client invitation links cannot be accepted. Existing Client accounts and records are preserved.

## Roles

| Role | Permission |
| --- | --- |
| Engineer | Prepare and submit own assigned work; edit eligible site information; upload grouped photos; confirm or correct AI proposals; accept answer drafts explicitly. |
| Quality Engineer | Read explicitly assigned work and evidence; request internal AI critique; approve Quality Control or reject with a reason. Cannot edit Engineer answers, upload evidence, share with Client or perform Team Lead approval. |
| Team Lead | Assign project work and explicit Quality Engineer; review only after Quality Control; approve internally or return work; decide whether to share AI critique with Client. |
| Client | Review authorized internally approved deliverables and current explicitly shared AI critique; approve or reject where Client review is required. |
| Admin / Project Manager | One canonical Admin role. Manage invitations, eligible roles and project grants, tasks, checklist versions and scoped audit within the Super Admin assigned industry and company. Cannot substitute an Engineer, Quality Engineer, Team Lead or Client signature. |
| Super Admin | Global administration only, including industry-specific Admin creation and binding. |

These are six current selectable roles. Migration0051 consolidates eligible legacy `project_manager` accounts into `ADMIN` using revocable, expiry-aware transition memberships, without transferring an existing project owner or changing global privilege flags. Frozen v1 snapshots/signatures keep their original role labels and named reviewers. Only the named, appropriately scoped migrated Admin can finish that historical v1 step; v2 remains Engineer → Quality Engineer → Team Lead → optional Client. New technical template qualification belongs to Team Lead; Admin does not inherit a technical signature by consolidation.

Profiles with pending/conflicting industry bindings remain `REQUIRE_ADMIN_SETUP` in bounded legacy compatibility until an authorized operator resolves the binding. This is not a seventh selectable role or a new dashboard. Pending legacy PM invitations are retired with audit records for authorized canonical reissue. Use the read-only `audit_project_manager_migration` command and follow [the migration instructions](audits/2026-10-23-post-sync-audit.md#migration-and-release-instructions). Historical deliberate/uncertain locks are preserved; new password failures use a configurable temporary throttle, default five failures for15 minutes.

## Current workflow for all new submissions

With Client review: Engineer submission -> assigned Quality Engineer -> Team Lead -> Client -> Closed.

Without Client review: Engineer submission -> assigned Quality Engineer -> Team Lead -> Closed.

An explicit active project Quality Engineer is required. No signer is chosen silently. Old tasks can receive a Quality Engineer through their checklist's assignment control, with a recorded reason and stale-version check. Quality Engineer approval is bound to the submitted evidence digest. Changes to answers, remarks, photos, confirmed locations, schema or relevant site context require fresh Quality Control before Team Lead approval. Rejection requires a reason and returns the work to Engineer correction; resubmission clears the current Quality Control gate while retaining history.

Team Lead approval does not bypass a configured Client requirement. Client requirement and closure controls remain intact: required authenticated Client approval closes the activity, while no configured Client closes after Team Lead approval. Administrative correspondence cannot satisfy a required authenticated Client decision. Closed historical activities are not reopened by this upgrade.

## Independent inspection revisions

New independent policies use L1 Engineer, L2 Quality Engineer and L3 Team Lead, with optional named Client C1. Each technical stage uses a different appropriately scoped person. Criteria, inspection method, exact published template qualification, asset context and coordinate provenance remain required. A project Team Lead can qualify the published template; historical Project Manager qualifications remain recorded.

Submission freezes a numbered source snapshot and digest. Decisions refer to that exact revision; out-of-order, substituted, revoked or stale decisions are denied. A reasoned return creates an editable correction and resubmission produces a linked revision without rewriting previous sources or signatures. The scoped Project Admin can configure draft or returned policies; the creating Team Lead can configure its initial draft. Frozen policies cannot be reassigned.

Already frozen version 1 TL/PM reviews retain their original identities and decision sequence. They are not relabeled as Quality Control. New submissions and corrections require version 2 QE/TL policy; a returned historical activity must be explicitly reconfigured first. Historical approved/rejected reports and manifest-bound originals remain available to authorized named Clients, subject to current access and expiry. Corrupt or missing originals do not silently download as valid frozen evidence.

Open critical or blocking findings prevent internal release. Remedy and an independent assigned reviewer's retest are separate recorded events. AI suggestions and uploaded photos never close a finding automatically.

## Invitations access and AI

Invitation links are shown once for manual distribution, expire after 72 hours and are single-use and email-bound; only their token hashes are stored. Acceptance rechecks issuer authority and project scope. No automatic email delivery or independent email-ownership challenge exists.

Account-wide activation, unlock and eligible role changes require authority over all of the person's active project grants. Client role conversion is blocked. Industry codes are permanent; names and active status can change without losing historical project meaning. Adding an industry does not automatically implement engineering workflows for it.

Engineer, assigned Quality Engineer and Team Lead can request critical AI review after photo processing finishes. Engineer sees its own requested reviews; assigned reviewers can inspect internal critique. Only Team Lead can explicitly share or withdraw a report for Client. Client reads require appropriate project/activity authority, internally approved status and a completed report matching current evidence. Super Admin has no engineering AI access. AI never approves, rejects, signs, edits answers or closes work. Installed model vision support is verified before analyzing photographs.

The 400-photo capacity remains supported. The full checklist and 400-photo 30-minute target is not an accepted benchmark; cached timings and projections do not prove that service level.


## Professional profiles and shared-project visibility

Every active, unlocked user can open **My profile** from the user menu, edit a professional display name, headline and introduction, and preview their profile. These fields never change the account role or project grants. Publication is off by default. Publishing allows eligible people on currently shared projects to read professional information; unpublishing immediately removes that access.

Engineers and Quality Engineers can add, edit and delete their own experience entries: employer/organization, role, start/end dates or current role, relevant work and self-reported qualifications. Experience appears on the published professional profile; it is not a verified certification or an approval signature. Other roles have a general profile but cannot create or modify Engineer/QA experience entries.

Clients use **Work profiles** in the user menu to browse published Engineer, QA, Team Lead and Admin professional profiles on actively shared projects. Every list and detail request rechecks both parties' current project grants, company boundaries, active account state and account locks. Expired/revoked access or withdrawn publication removes visibility. Other Client accounts and Super Admin are excluded from Client discovery. Super Admin can maintain its own profile and continues using administrative account controls rather than the operational people directory. Login names, email, passwords and private account metadata are not part of another person's professional profile.

Routes: `/governance/profile/` (self), `/governance/people/` (eligible directory), `/governance/people/<user_id>/` (published professional detail). Existing CSRF protection applies to editing and experience actions. Audit events record publication state and experience IDs without copying private profile text into the log. Migration0034 adds separate professional-profile/experience tables; the authorization Profile model is unchanged.


## Appearance

Open **Appearance** at the bottom left. Choose System, Light or Dark mode and one of10 color schemes. The layout remains fixed, including the Super Admin Tabbed desk. Your choice is saved for your account in this browser; it does not change permissions or another user's preferences. If browser storage is unavailable, colors still apply for the current session and the menu explains that the choice cannot be saved.
