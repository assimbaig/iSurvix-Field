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
python scripts/support_repair.py prepare --repository /reviewed/source --output /private/repair-NEW --bundle /private/case.zip --base-commit EXACT_SOURCE_SHA --tested-commit EXACT_FIX_SHA --regression-patch /private/regression.patch --repair-patch /private/fix.patch --profile django --unit-label core.test_specific_unit --integration-label core.test_specific_integration
python scripts/support_repair.py run --directory /private/repair-NEW --image sha256:EXACT_LOCAL_IMAGE_ID
```

The fixed `django` profile invokes the existing ordinary runner, with temporary
database/media/model cache and its Python network guard. Use an approved image
containing the matching reviewed dependencies. It cannot install missing packages.
Unit and integration labels are bounded `core.test_*` identities, never arbitrary
commands. The fixed `synthetic-stdlib` profile instead discovers `test_unit.py`
and `test_integration.py` in `tests/fixtures/support_repair` with Python unittest.

Both baseline stages must fail through real assertions, with at least one test
and zero errors/skips. A broken import, empty suite or skipped test is not a
reproduction. Both candidate stages must pass. A failed, malformed, timed-out or
interrupted run produces no successful receipt. Retry in a fresh prepared attempt.

Successful output:

- `execution.json`: immutable source/image identity, real container probes,
  test counts, result and log digests. Test output itself is bounded and not
  copied into the web diagnostic export.
- `repair-receipt.json`: strict `isurvix-support-repair-v1` case/report/base/fix/
  patch/regression identities, test evidence and explicit **operator-attested**
  provenance; `candidate_only=true`, `owner_release_approved=false`.

Receipts are not cryptographic proof that an untrusted owner ran a test. An
authorised owner records their provenance in the support audit history; the UI
must not describe schema validation as independent execution or approval.

## Publish a draft PR and record it

After reviewing the exact tested commit and safe evidence, the authorised
publisher creates a **draft** PR through the existing GitHub tooling. Credentials
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

The lead/publisher creates the real draft PR only after success, links that URL
into the result and imports it into the original saved test case through the real
interface. Never merge the deliberately synthetic rehearsal or call it a site
repair. Whole-application regression, independent QA and separate AppSec are
additional gates. Local Windows controlled tests do not prove Docker isolation.
