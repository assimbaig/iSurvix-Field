# iSurvix Field customer-server service and maintenance offer

**DRAFT FOR OWNER REVIEW. No price, licence grant, service-level commitment,
customer deployment or release approval is created by this document.**

## Proposed scope

Supply an installable package of the existing approved iSurvix Field release for
one customer-operated Linux/amd64 Docker server. Preserve the application's
company/project boundaries, invitation roles, original evidence, revision history
and Engineer -> QA -> Team Lead -> optional Client approval route. AI observations
and generated drawings remain proposals or drafts until existing authorised human
reviews and release controls are satisfied.

Initial services proposed for approval:

- Prepare and verify the exact versioned installation package and inventories.
- Assist the authorised customer IT operator with private LAN, DNS/TLS, storage,
  backup configuration and supported worker connectivity.
- Verify the agreed operational modes, role access, uploads, review, outputs and
  recovery using an approved pilot cohort and evidence.
- Provide scheduled maintenance and incident investigation within a separately
  approved support window, access scope and change procedure.

A native Windows server installer, public hosting, new modules, unlimited users,
guaranteed AI accuracy and continuous on-site engineering support are not included
in this proposed initial scope. Additional scope requires a separate approved
change record and verification; it is not promised by the package being runnable.

## Responsibilities to approve

| Area | Software/support supplier | Customer IT/operator | Customer administrators and reviewers |
| --- | --- | --- | --- |
| Software version | Prepare reviewed package, exact source/image IDs and tests | Install only the approved package; retain rollback copy | Confirm the intended projects/workflows |
| Infrastructure | State supported requirements; diagnose agreed application issues | Own server, OS/Docker, power, storage, LAN, DNS, TLS and time synchronisation | Nominate authorised users and sites |
| Data and access | Use only explicitly authorised support access and evidence | Protect private keys, service credentials and backup destinations | Maintain memberships, assignments and company-specific access |
| Backups | Supply verification/recovery procedure and test evidence | Schedule protected backups, retain an off-device copy, rehearse recovery | Confirm records and original evidence after recovery |
| AI | Document supported adapters/models and traceable proposals | Keep approved worker/model dependencies available; monitor actual capacity | Review uncertain results; make all engineering decisions |
| Security | Report findings, propose tested repairs and preserve audit history | Coordinate approved hardening, account revocation and incident containment | Authorise sensitive operational actions within existing roles |
| Commercial acceptance | Present the completed offer and measured limits | Confirm infrastructure operating costs | Owner approves licence, price, support scope and exact release |

No support permission automatically grants a new application role, unrestricted
database access, a right to inspect unrelated company records or a right to make
engineering approvals. Customer data/evidence and branding remain under the
customer's agreed ownership and retention policy. Contract ownership terms require
owner approval; technical support must preserve the existing authorisation rules.

## Operating modes and dependencies

| Mode | Proposed supported claim | Limits that must remain visible |
| --- | --- | --- |
| Local/LAN server | Authorised browsers use the installed application and local persistent records | Customer LAN, DNS/TLS, server availability and actual second-device acceptance required |
| Connected | Explicitly configured online functions and approved worker/provider links may operate | Credentials, consent, provider availability, quotas and actual charges remain separate prerequisites |
| Offline | Verified core workflows and packaged UI assets work without internet | Remote search/maps/providers cannot be represented as working offline; unavailable AI work stays durable and visibly queued/failed |
| Offline local AI | Possible only with separately installed, licensed and verified local vision runtime/model | Ollama weights and GPU drivers are separate; dependency-bundled OCR weights are inventoried; native accuracy is not certified |

Owner requirement: PDF conversion and OCR use local free components, with no paid
PDF/OCR service API. Candidate intake/preview conversion uses pypdf and PDFium;
RapidOCR uses its already bundled local ONNX weights. Those dependency-bundled
weights are inventoried in the package. Separately installed Ollama vision weights
and GPU drivers remain outside the web bundle. The installed OCR benchmark covers
printed Latin text; exact spacing and handwriting/language accuracy require
review. Existing optional survey-AI provider settings are a separate capability
and do not make a PDF/OCR conversion service part of this offer.

The final verified mode matrix, rather than a generic "fully offline" claim,
must accompany the offered release. Local image archives avoid registry downloads
during package installation; OS/Docker bootstrap is a separate customer prerequisite.

## Licence and redistribution decision

No project-level licence file was located in the inspected tracked source. The
owner must choose and approve the application's distribution terms before a
customer release. Existing third-party notices and obligations remain in force;
an owner-selected iSurvix licence does not replace dependency licences.

The retained local drawing/Unicode PyMuPDF dependency is offered under AGPL and commercial licensing
routes. Artifex explicitly distinguishes the commercial route for proprietary
redistribution and describes source/notice obligations for the AGPL route. The
chosen package/deployment must have an approved route and retained evidence of
the applicable rights. No commercial-licence purchase, vendor contact or wholesale
removal of the retained library has been performed. [PyMuPDF's official licensing information](https://pymupdf.io/licensing).

Adding free PDF/OCR tools and excluding paid service APIs does not by itself
remove that remaining local drawing-library dependency or clear its licence.

Owner decision required:

| Item | Decision/evidence |
| --- | --- |
| iSurvix application licence and permitted customer use | Pending owner approval |
| Per-server/company/project/user scope; affiliates and subcontractors | Pending owner approval |
| AGPL-compliant distribution or applicable commercial Artifex rights | Pending owner/licensing review; no evidence supplied |
| Third-party notices, source offers and redistribution inventory | Package inventory and any unresolved entries require review |
| Model-weight/driver rights if separately supplied | Not included; verify before any later distribution |
| Upgrade entitlement, support renewal and termination | Pending owner approval |

This records a licensing dependency; it does not decide legal compliance or grant
third-party rights. Retain the exact dependency/image inventories for the offered
build, including unknown licence entries rather than inventing clearance.

## Maintenance and change procedure

1. Record the installed source SHA, application/proxy image IDs, schema version,
   operating mode, worker version and package digest.
2. Reproduce the reported issue using isolated records. Preserve originals and
   human decisions; obtain scoped support access only when needed.
3. Classify impact and report security findings with severity and evidence.
   Under current project rules, security-review fixes require explicit owner
   approval. New unrelated development does not provide that approval.
4. Prepare and test the proposed change. Record the backup, compatibility,
   migration, expected interruption and rollback plan before approval.
5. Present the exact release and change window for authorisation. Install only
   after approval, then run version-confirmed smoke, role and integrity checks.
6. Preserve the result, audit events and rollback evidence. Verify off-device
   recovery separately; checksums alone do not establish trusted provenance.

Existing A12/BR1/D1/D2/L1/CS1/CS2/AI1 issues remain subject to their recorded
status. This draft does not waive those gates or promise an unapproved repair.

## Support and commercial fields requiring owner decisions

| Field | Proposed treatment / value |
| --- | --- |
| Installation, onboarding and training fee | To be priced after agreed scope and pilot |
| Maintenance charge and billing basis | Owner selects fixed/per-server/other basis; amount not set |
| Support hours, time zone and contact channel | Owner/customer agreement required |
| Critical/major/minor response and recovery targets | Unset until agreed capacity, staffing and recovery evidence exist |
| Included updates and scheduled maintenance | Scope/cadence/window require approval; no automatic production upgrade |
| Emergency changes and permitted containment | Explicit authorised actions and approval path required |
| Server, storage, backup, connectivity and model runtime costs | Allocate from actual customer/supplier costs; no invented estimate |
| External API costs | Separately authorised, metered and reconciled to actual billing; attempt quota is not a currency budget |
| Data retention, backup frequency and restoration objectives | Agree and rehearse; no unverified RPO/RTO promise |
| Data handback and termination | Verify supported exports and agree retention/deletion process; no automatic evidence deletion |
| Warranty, liability, jurisdiction and contract wording | Owner/legal review required; no terms accepted by the development agent |

## Owner acceptance record

| Approval | Approved value / signer / date |
| --- | --- |
| Exact product/release/package | Pending |
| Supported mode and tested capacity envelope | Pending |
| Customer/supplier responsibilities | Pending |
| Application and dependency licence route | Pending |
| Pricing, support scope and service levels | Pending |
| Security disposition and remaining limitations | Pending |
| Customer deployment and pilot authorisation | Pending |

Task18 remains **Blocked for owner acceptance** after this draft is reviewed.
The development agent cannot sign this record on behalf of the owner/customer.
