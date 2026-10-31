# Approved customer-package repairs CP1 and CP2

Owner explicitly approved both findings with **"Approve both fixes"**. Only CP1
and CP2 are repaired here. Earlier A12/BR1/D1/D2/L1/CS1/CS2/AI1 holds are unchanged.
The implementation used the installed Agency DevOps profile and repository TDD
rules. Independent QA/AppSec closure and actual Linux Docker verification remain
separate gates; this report does not approve a customer release.

## CP1: shared local-Docker validation

`deploy/customer/customer.py` now uses one `_local_docker_context` preflight for
captured Docker operations and the interactive `create-owner` operation. An
explicit non-Unix `DOCKER_HOST` fails before any subprocess. A nonlocal selected
context fails after local context inspection and before `createsuperuser`.

The supported local path still inherits the operator's terminal. It supplies no
password argument, stdin input, generated account credentials or captured
interactive stdout/stderr. The context probe alone captures nonsecret context
metadata. No Docker socket is added to the application container.

## CP2: pre-export source artifact gate

Before Docker inspection, target-directory creation or release export, the builder
checks the exact tracked Git archive for private artifacts. Known key/container
filenames, non-template `.env` variants, standalone PEM/OpenSSH/PGP private-key
headers, populated credential fields in JSON, and credential assignments in
supported configuration data are rejected. Restricted lexical handling also checks
nested YAML flow mappings and TOML inline tables without executing any YAML tag
or constructor. Quoted description strings and YAML literal script bodies remain
strings; explicit environment references remain references. Errors expose neither file contents
nor potentially sensitive filenames. An unsafe source leaves no candidate output.

Public `.crt`/`.pem` certificates and `.pub` keys remain allowed. Python marker
references are not mistaken for an actual armored header line. Labelled example
templates may contain conventional `REPLACE_...`/`replace-...` instructions and
environment references; populated real credentials are still rejected. Historical
workflow receipts may describe human `authorization`; actual Bearer/Basic/Token
credential headers remain blocked.

This is a conservative artifact gate, not universal DLP. It does not prove that
arbitrarily encoded secrets or opaque supplied Docker images contain no private
material. Images, dependencies and licensing still require their recorded review.
SHA256 integrity remains distinct from authenticated artifact provenance.

## Executed TDD and focused verification

Commands ran from `.local/b6` with the existing absolute project interpreter:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py core.test_customer_package.ApprovedCustomerPackageRepairs --verbosity 2
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py core.test_customer_package --verbosity 2
```

- Before product repair: five new tracked tests ran with eight failing assertions
  (including subcases). Seven established the two CP1 paths and five CP2 artifact
  variants; one positive public-certificate assertion exposed a fixture Git
  line-ending setting. That fixture now explicitly preserves its committed bytes
  without changing global Git settings or loosening the byte comparison.
- Final focused result: **28 tests passed in 13.918 seconds**, no failures, errors
  or skips; zero external network attempts and zero HTTP fixture connections.
  Docker was controlled in these tests; no daemon or real account was touched.
- The new preflight was also run against the actual tracked source commit
  `dfbd55758f4c5612edc24119f4d76e27093778ca`: passed with no Docker operation and
  no candidate output. Initial preflight exposed two legitimate example-template
  placeholders and a historical human-authorization receipt; focused positive and
  negative assertions preserve those cases without exempting actual credentials.
- A post-repair check reproduced a remaining YAML flow mapping bypass and a
  nested TOML inline-table case. The tracked RED recorded two failing assertions
  plus a legitimate source-reference error. Restricted structured scanning fixed
  these cases; a further explicit environment-reference RED protected legitimate
  template use. All RED receipts are retained, including
  `approved-cp2-structured-red.log` and `approved-reference-red.log`.
- Independent QA then reproduced quoted Authorization-header syntax in YAML.
  Tracked YAML/TOML and escaped-quote scheme cases ran RED (six tests, eight
  failing assertions). The repaired gate normalizes actual quoted scalar values
  before credential-scheme checks, while retaining human-authorization narrative
  positives. `approved-quoted-header-red.log` preserves the failing evidence.
- Existing exact Git/image identities, vendor byte preservation, offline/no-pull
  behavior, source/backup preservation and explicit initialization tests passed.

Private raw evidence is under `.local/customer-server-20261031/package/`:
`approved-cp1-cp2-red.log`, `approved-cp1-cp2-final-quoted-green.log`,
`approved-source-preflight.json` and `approved-fix-source-hashes.json`.

Functional freeze hashes:

| File | SHA256 |
| --- | --- |
| `deploy/customer/customer.py` | `97b623695354c49bf0184084afe6461e8da69ca332f67b553d4a7dae5354d60a` |
| `backend/core/test_customer_package.py` | `6b9dbb7d8ff51e46aa362b7dfc6ed7f27b3e6304ded702c8bf0ce942310dafb3` |

These hashes identify the functional freeze before independent closure. No commit,
push, operational migration, native-model call, customer deployment or engineering
approval was performed by the implementing agent.
