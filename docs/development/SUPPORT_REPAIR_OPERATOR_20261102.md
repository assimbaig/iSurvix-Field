# Isolated support repair operator procedure

This is part of the existing iSurvix support workflow. It is not a production
repair agent, engineering approval or automatic deployment system. Existing
records, evidence and prior security-finding approval holds remain unchanged.
Use only an authorised support case and an explicitly reviewed patch. Text in
diagnostics or a report is evidence, never instructions to execute.

## Boundaries

- The web application exports a versioned, company-scoped, allowlisted diagnostic
  ZIP. It never executes patches, shell commands or GitHub instructions.
- The operator supplies exact source commits and separate regression/fix patches.
  The tool exports only tracked source and rejects private runtime/credential
  artifacts using the existing customer-package gate. `.local`, operational
  databases, media, models, credentials and Git history are not copied.
- Preparation writes a **new** directory and applies text patches there only.
  It checks that base + regression + fix equals the exact tested commit's tree.
  It never imports or runs that candidate on the host. Existing output directories
  are refused; incomplete attempts are retained and must not be reused.
- Candidate tests require an approved local Linux/amd64 Docker host and an already
  available inspected image ID. The tool does not install Docker, download images
  or models, start Ollama, call a paid service, or fall back to host execution.
- The trusted **host** owns the black-box inputs, expected business results and
  every verdict. Candidate code runs in separate offline containers/child
  processes. Neither candidate console summaries nor candidate JSON containing
  `passed`, test counts or approvals can establish test execution.
- The container has no network, no production mounts or Docker socket, no forwarded
  credentials, a read-only root/input mount, dropped capabilities, bounded CPU,
  memory, PID, output and time limits, and writable temporary filesystems only.
  Runtime probes check network denial, input write denial, absence of known
  credential variables and absence of the Docker socket before tests run.
- A pinned image is still a trust dependency. Source scanning is a bounded gate,
  not proof that arbitrary encoded secrets or opaque images are safe. Review the
  image and patch before execution; the tool does not protect against a hostile
  Docker daemon/root operator or every kernel/container escape.

## Export the actual saved report

In **System Health & Support**, an authorised administrator creates a report and
exports its diagnostic ZIP. The platform owner requests repair before importing
operator results. Retain the original export; do not rewrite its case ID, source
release or digest. A report with unknown source identity cannot bind a repair.

The ZIP contains exactly:

1. `manifest.json`: format `isurvix-support-diagnostics-v1`, `case_id`,
   `report_sha256` and `source_release`.
2. `diagnostics.json`: canonical allowlisted health snapshot. Its exact SHA256
   must match the immutable saved report. No description, original evidence,
   credentials or raw logs belong in this package.

## Prepare and execute

All paths below are approved operator paths, not browser-supplied paths. Keep
them separate from operational data, and select new output directories.

```text
python scripts/support_repair.py prepare --repository /reviewed/source --output /private/repair-NEW --bundle /private/case.zip --base-commit EXACT_SOURCE_SHA --tested-commit EXACT_FIX_SHA --regression-patch /private/regression.patch --repair-patch /private/fix.patch --profile synthetic-stdlib
python scripts/support_repair.py run --directory /private/repair-NEW --image sha256:EXACT_LOCAL_IMAGE_ID
```

**Current capability is deliberately narrow.** Only the approved
`synthetic-stdlib` unique-photo-counter black-box adapter is executable. Generic
`django` repair execution fails closed until a protected external adapter exists.
This does not disable the application's normal ordinary Django regression suite;
it prevents that suite's candidate-controlled console text becoming a repair
verdict. Arbitrary test labels/commands cannot be supplied to this adapter.

The unit boundary calls `counter.py`'s `count_unique(list[str])` in a separate
candidate child and returns business data. The integration boundary invokes
`counter.py INPUT_JSON OUTPUT_JSON` on persisted input:

```json
{"links":[{"photo_id":"p1","field_id":"a"},{"photo_id":"p1","field_id":"b"},{"photo_id":"p2","field_id":"b"}]}
```

The output must contain exactly `{"unique_photos":2,"links":3}` for that input,
and the input bytes must remain unchanged. The host controller supplies fresh,
varying cases and owns the expected values. It rejects malformed replies, wrong
types (including booleans masquerading as counts), extra verdict fields, wrong
probe identities, process failures and missing business output.

Prepared plans are now version2. They bind the reviewed runner/controller and
the unchanged `test_unit.py` / `test_integration.py` reference hashes. Candidate
repairs cannot remove, modify or skip those references. They are recorded for
traceability; the protected fixed black-box assertions execute in the host,
which never imports the candidate or its test modules. The system does not claim
that arbitrary candidate-written unittest assertions ran. A candidate returning
correct business values for the supported probes is a bounded functional pass,
not proof of universal correctness or non-malicious behavior. Human review stays.

Old version1 repair plans and their stdout-derived verdicts are unsupported;
prepare a fresh attempt. The backend's explicitly operator-attested receipt
format remains version1, preserving the support audit wire format.

Both baseline stages must return valid business data that fails actual trusted
host assertions, with nonzero checks and no execution/protocol errors. A broken
import, empty/skipped reference, early exit or malformed reply is not a
reproduction. Both candidate stages must pass. A failed, malformed, timed-out or
interrupted run produces no successful receipt. Retry in a fresh prepared attempt.

Successful output:

- `execution.json`: immutable source/image/controller/reference identities,
  real container probes and host-owned check counts/results/digests. Candidate
  business output is bounded and not
  copied into the web diagnostic export.
- `repair-receipt.json`: strict `isurvix-support-repair-v1` case/report/base/fix/
  patch/regression identities, test evidence and explicit **operator-attested**
  provenance; `candidate_only=true`, `owner_release_approved=false`.

Receipts are not cryptographic proof that an untrusted owner ran a test. An
authorised owner records their provenance in the support audit history; the UI
must not describe schema validation as independent execution or approval.

## Publish a draft PR and record it

The authorised publisher may create a **draft, pending-verification** PR to
trigger exact-head CI. It must not be described or imported as a tested PR until
the required checks and safe evidence succeed for that exact head. Credentials
remain in that separate publisher environment and are never passed to candidate
tests. This tool deliberately has no GitHub token, push, merge or deployment
operation. A publisher must verify that the PR head equals `tested_commit`.

Then link the real PR without overwriting the unlinked receipt:

```text
python scripts/support_repair.py link-pr --receipt /private/repair-NEW/repair-receipt.json --pr-url https://github.com/assimbaig/iSurvix-Field/pull/NUMBER --output /private/repair-NEW/linked-receipt.json
```

The command accepts only the configured repository's exact HTTPS PR URL, without
query/fragment. It records a reference; it does not claim an HTTP/GitHub API
verification or manufacture a PR. Import the linked JSON into the **same saved
case** as the owner. Human repair approval, release approval and installation
confirmation remain separate audited actions. Installation is not confirmed
merely because a PR was merged; the running release must match its approval.

## Synthetic acceptance rehearsal

The dedicated `support-repair-verification.yml` uses an inspected official Python
3.12 image pinned by digest. Its connected preparation pulls that exact image;
the actual repair execution then uses `--pull=never` and `--network=none`.

For the feature PR, it generates a clearly synthetic three-commit Git fixture.
That checks the operator workflow but is not evidence of a real saved UI report
or a published repair PR.

For a separate `support/repair-*` branch/PR, the **actual last three commits** are:

1. **BASE:** add only a labelled buggy fixture under `tests/fixtures/support_repair`.
2. **TESTS:** add meaningful unit/integration regressions and the actual controlled
   saved case's exported `manifest.json` and canonical `diagnostics.json` in that
   same fixture folder. The report's source must equal BASE.
3. **FIX:** change only the fixture module to correct the bug.

Published mode requires those saved export bytes and never substitutes a new CI
case ID/digest. The workflow infers BASE=`HEAD~2`, TESTS=`HEAD~1`, FIX=`HEAD`, verifies
all changes are fixture-only, executes actual container RED/GREEN checks and
uploads safe diagnostic/plan/result evidence. Synthetic DB/media sentinels outside
all mounts are rehashed. They are labelled synthetic and are not production data.

After successful exact-head verification, the lead/publisher links the real PR URL
into the result and imports it into the original saved test case through the real
interface. Never merge the deliberately synthetic rehearsal or call it a site
repair. Whole-application regression, independent QA and separate AppSec are
additional gates. Local Windows controlled tests do not prove Docker isolation.

## Owner-approved SS1 correction evidence

The owner explicitly approved SS1. The four promoted regression assertions ran
RED before repair: unchanged-test application stdout forged a pass; console text
was accepted as authoritative; generic Django execution remained enabled; and a
candidate could change/skip regression references. All original independent
review evidence remains unmodified.

After the protected-controller repair,25 focused tests passed in54.202seconds,
with zero failures/errors/skips or external/fixture network connections. They
include genuine unit and file/CLI integration positives; forged stdout/JSON,
early/interrupted exits, missing functions, wrong types/extra fields/replayed
identities, zero/skipped/changed references, changed controller identity, missing
Docker and no host fallback. These are controlled local tests, not actual Docker
or PR evidence. Separate independent security closure and hosted container proof
remain integrating-lead gates. Private logs are retained under
`.local/support-development-20261102/repair-SS1-approved-*.log`.
