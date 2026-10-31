# Customer-server package: independent component security review

31 October 2026. Independent Agency Application Security Engineer review of the
frozen customer-package component in `.local/b6`, branch
`feat/customer-server-readiness-20261031`, parent `e832def`. The initial component
review preceded the local/free PDF and OCR integration. A subsequent bounded
post-functional integration review is recorded in the addendum below; it does
not replace the actual-image/target-server release gates.

**Two Medium findings confirmed: CP1 and CP2. The owner subsequently approved
both repairs. Latest closure status: CP1 and CP2 passed independent re-review in
the reported/tested boundaries, including the subsequently discovered YAML/TOML
and quoted-header cases. Original and interim RED evidence remains preserved.
See final closure below. Customer release approval remains withheld because
earlier findings and external release gates are separate.**
No real Docker command, account creation, native/paid inference, external network
request or operational data modification occurred during this review.

## Scope and method

Read repository rules, latest handoff and the installed Agency
`security/security-appsec-engineer.md` profile. The lead requested this separate
review after component implementation tests and independent QA, while actual
disposable Docker CI was still pending. The reviewer inspected the installer,
manifest, runtime preparation, Compose private-file mounts, no-overwrite checks
and private-key handling, and authored only private review tests and this report.

Three component source SHA256 values were captured before/after review:
`deploy/customer/customer.py`, `deploy/customer/compose.yaml`, and
`scripts/build_customer_package.py`. No component source was edited. The owner's
rule is explicit: "Do not fix that security review's findings until the owner
approves those fixes." No previous security hold was interpreted as approved.

## CP1 — Medium: interactive owner provisioning skips the local Docker boundary

**Locations:** `deploy/customer/customer.py:109` defines `_docker`, which rejects
a non-Unix `DOCKER_HOST` and inspects the selected context before running ordinary
Docker operations. In contrast, `run_action`'s `create-owner` branch at line 397
calls `subprocess.run` directly at line 402 without that context preflight.

**Independent RED evidence:** two private tests supplied a valid synthetic
prepared runtime/database sentinel, then intercepted every subprocess call:

1. With `DOCKER_HOST=tcp://unrelated-daemon.example.test:2375`, the helper invoked
   the interactive `docker compose ... createsuperuser` command instead of refusing.
2. With no `DOCKER_HOST` but a selected-context probe returning an SSH daemon,
   the helper did not invoke context inspection and proceeded to the interactive
   command instead of refusing.

Both assertions requiring a preflight `ValueError` failed. Independent QA's
earlier `context-boundary-observation.json` records the same bypass. All subprocesses
were replaced by synthetic capture functions; **no daemon was contacted and zero
accounts were created**.

**Impact and prerequisites:** an authorised operator using an inherited remote
Docker environment/context can accidentally run owner provisioning against an
unrelated reachable daemon. If its runtime bind paths resolve there, the action
can create an administrator in an unintended installation. This requires the
operator's Docker access and a valid prepared local package/runtime; it is not an
anonymous web exploit or a demonstrated remote account creation.

**Recommendation:** extract one shared local-Unix-context validator and invoke it
before both captured Docker operations and the interactive owner-creation command.
Reject nonlocal `DOCKER_HOST`/selected contexts before the action. Preserve terminal
inheritance for Django's password prompt; do not capture, log, generate or pass
passwords as command arguments. Add failing-then-passing tests for both environment
and selected-context paths, including a supported local interactive path.

**Initial disposition:** confirmed, unremediated, pending explicit owner approval.
Later approval and re-review are recorded in the approved-repair addendum below.

## CP2 — Medium: tracked private-key files can enter a customer distributable

**Location:** `deploy/customer/customer.py:218` rejects tracked `.local`/`private`
paths, database suffixes, the exact `.env` basename and legacy media. It does not
reject other private-key names/content such as `deployment-signing.key`.

**Independent RED evidence:** a clean disposable Git repository contained the
required installer sources plus `deployment-signing.key`, with a clearly labelled
synthetic `BEGIN PRIVATE KEY` fixture (not a real key). Controlled Docker image
inspection/export responses were supplied. `build_package` returned a complete
`draft-for-review` candidate, exported the synthetic key into its `release/` tree
and inventoried it successfully. The exported bytes exactly matched the tracked
source. The assertion requiring rejection failed.

Private `CP2-observation.json` records `builder_returned_complete_candidate`,
`synthetic_private_key_exported` and `exported_bytes_equal_source` as true, with
`real_private_key_used` and `docker_executed` false.

**Impact and prerequisites:** an accidentally tracked secret under an unblocked
filename can be redistributed to customers even though the builder claims to
exclude private/runtime files. This review establishes a packaging-control gap,
**not an actual project secret leak**. It requires such material to be present in
the clean source selected by an authorised package builder.

**Recommendation:** extend the pre-export/distribution gate to cover private-key
artifacts and credential configuration variants, with a reviewed content-aware
secret scan and explicit handling for legitimate public certificates/synthetic
fixtures. Keep source, Docker and package logs free of secret contents. Retain
reviewed exception evidence rather than claiming a filename denylist proves that
all credentials are absent. Test that a tracked synthetic private key cannot
produce a complete distributable, while approved public assets still package.

**Initial disposition:** confirmed, unremediated, pending explicit owner approval.
Later approval and re-review are recorded in the approved-repair addendum below.

## Executed results

Using process-local `PYTHONPATH=.local/customer-server-20261031/security`:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py customer_security --verbosity 2
```

**7 tests run in 1.749 seconds: 4 passed, 3 failed, 0 errors, 0 skips.** The three
failures are the intentionally failing security-boundary tests establishing CP1
(two cases) and CP2 (one case). They were not skipped, weakened or fixed.

The four passing controls verified:

- Ordinary `_docker` operations reject an explicitly remote host before subprocess.
- Corrupt package inventory prevents owner provisioning and preserves DB sentinel.
- Supplied external TLS/private secret bytes are not copied into package/runtime.
- An existing runtime database cannot be reinitialized or overwritten.

A focused repeat of the CP2 case captured the exact exported-file observation:
**1 test, 1 expected failure in 1.359 seconds**. This is the same test, not another
unique test or a passing gate. Both runs recorded zero external network attempts
and zero fixture HTTP connections. The only actual subprocesses in the CP2 fixture
were bounded Git commands in its disposable synthetic repository; Docker remained
controlled throughout.

Private evidence directory: `.local/customer-server-20261031/security/`:
`customer_security.py`, `boundary-red.log`, `CP2-evidence-red.log`,
`CP2-observation.json`, `receipt.json`, and before/after source inventories.

## Limits and release disposition

- Actual Linux image build, clean install, permissions, Docker networking,
  second-device LAN/browser acceptance and target-server recovery are not proved
  by this review. The separate disposable CI and owner target gates must be
  evaluated against their actual results.
- The runtime preserves supplied key bytes outside the distribution and rejects
  missing/replaced manifest/configuration files in tested paths. Real certificate
  validity, Linux key ownership and readable mounts were not verified on this PC.
- Manifest SHA256 supports integrity checking against an independently trusted
  digest, not authenticity if an attacker can replace both the package and digest.
  Only trusted reviewed package code should execute.
- The local/free PDF/OCR integration, dependency licensing and final assembled
  release require their own completed verification and subsequent security review.
- Earlier A12/BR1/D1/D2/L1/CS1/CS2/AI1 holds remain unchanged. CP1/CP2 add to the
  approval queue; neither is implicitly approved by unrelated implementation work.

No merge, production/customer deployment, security repair or service change was
performed by this reviewer. A full release cannot be declared secure or complete
on the basis of these component tests.

## Post-functional local PDF/OCR integration addendum

The lead subsequently declared the assembled local PDF/OCR source functionally
frozen and requested a separate review of the new conversion/OCR callers,
offline model preflight and remote OCR trust boundary. The reviewer inspected
`pdf_tools.py`, `local_evidence_tools.py`, `survey_evidence.py`,
`survey_sketches.py`, `engineer_documents.py`, `remote_worker_service.py`, and
the current customer package/Compose. Eight source hashes were captured before
and after this addendum's checks. The addition of CP1/CP2 IDs to `HOLD_IDS` is
inventory only; it does not repair either finding.

Twelve additional private security cases were written and executed after this
functional freeze:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py pdf_ocr_security --verbosity 2
```

Process-local `PYTHONPATH` pointed at the private security directory.
**12 passed in 0.553 seconds**, zero failures/errors/skips, zero external network
attempts and zero fixture HTTP connections. These are new independent review
cases, separate from the component's seven cases above. No previous failing
security test was deleted, changed to pass or treated as resolved.

| Challenged boundary | Actual result |
| --- | --- |
| Encrypted PDF | Rejected before native PDFium document construction |
| PDF byte limit | Rejected before invoking either PDF parser |
| Raster pixel limit | Rejected before native bitmap allocation |
| Embedded PDF URI/OpenAction and JavaScript | Local text/raster conversion completed without following URLs or initializing the forms/JavaScript environment |
| Remote OCR attached to a photo or digital-text PDF | Rejected as not the permitted image-only PDF task |
| Foreign page ID, source hash or model | Rejected before retaining OCR evidence |
| Approval-like OCR keys or forged confirmed provenance | Strict canonicalizer rejected them |
| NaN, infinity, boolean/invalid confidence and oversized coordinates | Rejected by the OCR evidence bounds |
| Failed OCR report carrying successful readings | Rejected as contradictory evidence |
| High OCR confidence/top-level worker approval flag | Saved canonical result stayed `needs_review`; transcription stayed `unverified_source_text`; approval flag was not retained |
| Missing dependency-bundled OCR model files | Rejected before importing/constructing the native OCR engine or attempting a download |
| Instruction-like text inside OCR | Retained only inside `UNTRUSTED_EVIDENCE_JSON`; controlled inference produced no findings or approval |

Local PDF conversion used the installed PDF libraries on small synthetic PDFs.
No actual Ollama/native vision request was made. OCR inference was controlled;
the reviewer did not rerun native OCR or certify its transcription accuracy.
The remote validator checks were direct synthetic immutable-task contract tests,
not a newly executed authenticated machine-upload/browser workflow. Existing
workflow/role tests are separate evidence recorded by the implementation lead.

**No new exploitable defect was established in this bounded PDF/OCR scope.**
This does not prove arbitrary hostile PDF parsing has a hard CPU/memory sandbox,
native-library safety, comprehensive dependency clearance or accurate handwriting.
Existing byte/page/text/pixel limits were checked where stated; large hostile
native-parser stress tests were deliberately not run. No converter's local-only
behavior was inferred from a paid/cloud service mock.

The earlier CP1/CP2 RED receipts remain intact and both findings remain unfixed
pending owner approval, as do all previous security holds. The local/free PDF/OCR
change does not remediate the legacy drawing-engine licence dependency. Actual
Linux Docker CI, the final assembled image and customer/second-device acceptance
must be recorded separately against the resulting source. Future functional
repairs changing these reviewed boundaries require an affected re-review.

Private evidence: `security/pdf_ocr_security.py`, `pdf-ocr-review.log`,
`integration-source-before.json`, `integration-source-after.json` and
`integration-review-receipt.json`. No product/core tests were edited by the
reviewer, and no security repair, deployment or operational data change occurred.

## Owner-approved CP1/CP2 repair re-review: initial partial result

After the reviews above, the owner explicitly approved **CP1 and CP2 only**.
Earlier findings A12/BR1/D1/D2/L1/CS1/CS2/AI1 retain their original approval
status. The implementation lead then declared the two repairs functionally
frozen and requested this separate review. Reviewed hashes:

- `deploy/customer/customer.py`: `ece5e23ed39d943f2998a9e3b938826c3c3039e84a4b84e3eb52a08708b17de8`
- `backend/core/test_customer_package.py`: `5c124bcd3a43ff9981b29b9521a7182046e8d2f44b39970e5fb763be10bac1a0`

The reviewer reran the **original seven private security assertions unchanged**:
**7 passed in 1.463 seconds**, zero failures/errors/skips, zero external network
attempts and zero fixture HTTP connections. Their prior failing receipts and
synthetic exported-key observation remain preserved as historical RED evidence.

The shared local Docker-context preflight now runs before interactive owner
provisioning. Independent positive/failure tests verified that a supported local
context precedes `createsuperuser`, rejected contexts do not reach it, and stdin,
stdout and stderr remain inherited. No password input/output/argument was
captured. **CP1 is verified repaired in these tested boundaries.** Actual terminal
interaction with a Docker daemon remains a separate operator/CI acceptance step.

The source packaging gate now rejects the originally reported tracked key,
private-key PEM content and populated JSON credentials before Docker or output
directory creation. Public certificates and explicit environment references
still package successfully. However, the new format countercase below means
**CP2 cannot yet be marked completely closed**.

### Remaining CP2 countercase: YAML flow-map credentials

The additional private test created a clean synthetic Git source containing
`config/connection.yaml` with valid YAML flow-map content:

```yaml
{database: {password: SYNTHETIC_CREDENTIAL_NOT_REAL}}
```

The current `_private_source` line-oriented configuration regex did not recognize
that nested inline credential. The complete builder returned `draft-for-review`
and exported the exact YAML bytes. Private `CP2-yaml-observation.json` records
both `complete_candidate_returned` and `yaml_literal_credential_exported` true,
with `real_credential_used` and `docker_executed` false. The assertion requiring
rejection failed. This is the same Medium credential-artifact packaging issue
under another ordinary structured configuration representation, not a newly
observed operational secret leak.

Command for the additional cases:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py approved_repair_review --verbosity 2
```

**5 tests in 4.126 seconds: 4 passed, 1 failed**, zero errors/skips and no network
attempts/connections. The failing case is the remaining CP2 YAML countercase.
Do not label this re-review wholly green or count CP2 closed based only on the
original filename reproduction. These tests are private review cases and do not
inflate ordinary full-suite totals.

Recommendation: extend the approved credential-artifact gate to recognize
structured YAML flow-map credentials, preserving public/reference exceptions,
no secret echo and rejection before Docker/output. The reviewer did not implement
the fix. The lead must track its scope against the existing explicit CP2 approval,
then run the failing case and affected controls before requesting closure again.
No approval for unrelated earlier findings is inferred.

Private evidence: `approved-repair-original-green.log`,
`approved-repair-countercases.log`, `approved_repair_review.py`,
`CP2-yaml-observation.json`, and `approved-repair-review-receipt.json` under the
same security directory. No real Docker execution, account, customer data,
native model or paid/external request was used. New updater/Django-distribution
phase tasks are outside this bounded repair review and need their own review.

## Final owner-approved CP1/CP2 closure after credential-syntax repair

The lead confirmed the remaining YAML/TOML/quoted-header repairs are within the
owner's explicit **CP2** credential-artifact approval, rather than treating the
new phase tasks as unrelated security approval. The implementation agent then
completed functional RED/GREEN and froze the repair again. Reviewed final hashes:

- `deploy/customer/customer.py`: `97b623695354c49bf0184084afe6461e8da69ca332f67b553d4a7dae5354d60a`
- `backend/core/test_customer_package.py`: `6b9dbb7d8ff51e46aa362b7dfc6ed7f27b3e6304ded702c8bf0ce942310dafb3`

The reviewer reran the original seven private cases **and the additional five
cases unchanged**. **12 passed in 5.034 seconds**, zero failures/errors/skips.
The former YAML flow credential failure now rejects the artifact before a complete
candidate is produced. The shared local preflight, terminal inheritance, no
password capture, private-key/JSON rejection, and legitimate public certificate/
environment-reference controls remained passing.

Two additional existing private QA cases were independently executed by this
reviewer: quoted YAML Bearer headers and nested TOML inline access-token fields.
**2 passed in 2.106 seconds**, zero failures/errors/skips. These are repeated
independent executions of existing QA cases, not two new unique ordinary tests.
All commands used the isolated ordinary runner, recorded zero external attempts
and zero fixture HTTP connections, and never executed Docker or account creation.

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py customer_security approved_repair_review --verbosity 2
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py approved_package_repair_qa.IndependentApprovedPackageRepair.test_quoted_yaml_bearer_header_cannot_produce_complete_package approved_package_repair_qa.IndependentApprovedPackageRepair.test_nested_toml_inline_private_value_cannot_produce_complete_package --verbosity 2
```

**Disposition: CP1 and CP2 are verified repaired within the reported and executed
countercases.** No new exploitable finding was established in this bounded
closure review. The gate is a conservative artifact screen, not a guarantee that
every encoded/opaque secret or arbitrary source-code assignment can be detected.
Exact-release source/secret review and the independent package digest remain
necessary. No product edit was performed by the reviewer.

Earlier A12/BR1/D1/D2/L1/CS1/CS2/AI1 findings remain unchanged; neither this approval
nor this closure authorizes their repair. Original `boundary-red.log`, the
exported-key proof, the intermediate YAML RED receipt and all failing assertions
remain intact as history. New GREEN receipts are
`approved-final-unchanged-green.log`, `approved-final-quoted-toml-green.log` and
`approved-final-closure-receipt.json` in the private security directory.

This closes only these approved findings against the frozen hashes above.
The actual Linux customer package/upgrade CI, final image, target devices,
licensing and public/customer release authorization are separate gates. New
phase-6 optional updater/package configuration changes require their own later
post-functional review; this closure does not pre-approve those changes.
