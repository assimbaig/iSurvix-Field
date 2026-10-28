# Company boundaries

Task04, 28 October 2026. Product baseline: merged PR23 `fd365f1`; phase0
evidence parent: `89b55b1`. This definition uses the existing Django models and
permissions. It does not create a new tenant system or move operational data.

## Security boundary and existing role rules

The tenant is **Company**, the employer/company responsible for its Admins,
projects and operational staff. **ClientOrganization** is a separately scoped
customer record within a Company and industry; its name is not a tenant key.
Site IDs, industry names, filenames, URL parameters and matching display names
never establish company ownership.

A project's stored `company_id` controls the company boundary for its sites,
surveys, evidence, outputs and processing jobs. Operational access additionally
requires existing effective project membership and the applicable role/reviewer
or release rule. Same-company identity alone does not grant every project.
Admins retain their named project ownership/explicit legacy delegation and
industry restrictions. Client release rules, QA/Team Lead/Engineer assignments,
approved locks, immutable revisions and human decisions remain separate controls.

Super Admin retains the existing global **administration** exception. Global
project discovery for administration does not itself authorize engineering
evidence review or approval. Operational routes retain their separate role gates.
Published shared standard catalogs are intentional shared references; a shared
catalog does not convey access to another company's project records or branding.

## Current identity and legacy compatibility

Authority is read from the current persisted User/Profile and project relation,
not a previously cached Python object. A cached account cannot retain its former
company, unlocked state, active state or superuser bypass after a stored change.
`accessible_projects()` uses one fresh principal snapshot for this decision.
Standalone role/company helpers also read current persisted identity.

The explicit Profile company takes priority. Legacy accounts without an explicit
company retain the existing fallback to their current primary project's company.
An unclassified legacy company does **not** mean global access: existing explicit
effective grants or an eligible legacy primary pointer are still required, and
an expired/revoked explicit grant wins over primary fallback. No existing null
affiliations are silently reclassified by this work.

Inactive or locked accounts are not granted access. Their stored company remains
available when validating them as membership targets, so deactivation cannot
make a foreign-company user look like an unclassified new account. Grant services
refresh target/project objects before validation and retain existing role rules.

## Contradictory records and company changes

For a scoped Admin, invitation rows must belong to an accessible project and
have the same explicit company, or the supported legacy null-company snapshot.
A contradictory foreign-company invitation is not listed and cannot be revoked
through that Admin's project control. Invitation acceptance already rechecks its
project/company identity and issuer authority.

Changing an established non-null company cannot transfer retained project data
to a different tenant. The administrative classification endpoint rejects this
change when any checklist, assignment, invitation, membership history, governance
audit, site location, template qualification, evidence-rule release, bound
checklist template or project template file is retained. In
particular, even a project with no survey work cannot carry a private checklist
template and its branding into another company through classification.
Client-organization binding and active
affiliation restrictions also remain. Answers, files, approvals, history and
source IDs are left unchanged on rejection.

The existing explicit initial classification of a legacy null-company project
is preserved, subject to its existing setup guards. A genuinely unused project
without retained records may still be explicitly reclassified by the authorized
global administrator. This is not a general migration/transfer mechanism for
used projects; such a migration would require a separately reviewed plan.

## Implementation and verification scope

Central implementation: `core/access.py`, `core/company_service.py` and the
scoped invitation/company-classification controls in `core/governance_views.py`.
No central model migration or operational record rewrite is performed.

`core.test_company_boundaries_core` executes real HTTP and unit cases for cached
tenant/status/global-authority revocation, inconsistent grants, foreign invitation
snapshots, retained tenant history and legacy compatibility. The initial14-case
suite failed11 cases before implementation; the new14 and existing company /
governance tests subsequently passed40/40. An additional real-HTTP private-template
transfer regression was executed RED before its minimal retained-reference guard;
three additional standalone location/qualification/rule-release cases were also
executed RED before their retained-relation guards. The extended central suite
contains18 cases. Retained private RED/GREEN receipts
are under `.local/company-boundaries-20261028/core` in the feature worktree.
The final central and related Admin/Client/Super Admin/legacy integration run
passed82/82 in17.361s, with isolated database/media and zero external requests.

File delivery, job credentials, Django Admin, independent attack tests and final
integration results are recorded by their separate owners in this task's final
acceptance evidence. This definition alone is not proof those surfaces passed.

Earlier approval-held findings, including BR1, are not authorized fixes by this
definition. New findings from the separate post-functional security review are
reported with severity and recommendations and remain unfixed until approval.
