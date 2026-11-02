# System Health & Support: separate security review

## Latest status: approved SS1 repair independently verified within the fixture scope

The owner explicitly approved SS1 on 2 November 2026. A separate DevOps
implementer repaired it; this AppSec reviewer changed no operator or application
code. **SS1 is repaired with independently verified bounded closure.** This
approval and closure do not change the eight earlier security holds.

The host controller now owns the business assertions and stage verdicts. It
never imports candidate code. Candidate code executes in child processes and
returns bounded business observations; console summaries and candidate-authored
test verdicts cannot prove success. Request identities, exact result schemas,
integer types, unchanged input files, controller identity and immutable regression
references are checked outside the candidate. The public operator supplies a
Docker executor only. No implicit host execution fallback remains. Generic
Django repair execution is explicitly unsupported until a protected external
business adapter is implemented and reviewed.

Independent closure executed at these frozen SHA256 identities, unchanged before
and after the review:

- `scripts/support_repair.py`:
  `54c478b58bd86a334bc44dfa807d7d259653a5f7651225fe587b34359c90ec00`.
- `scripts/support_repair_rehearsal.py`:
  `2541cc5dc3aeed8a2225c5bf0edf9d16bb224fc7aebab222e9a31e4653c0ce26`.

New independent `ss1_closure` probes: **15 passed, zero failures/errors/skips**,
10.583 seconds. These execute actual known synthetic candidate subprocesses for
both the unit interface and file/JSON CLI. They reject the original application
import stdout forgery while leaving regression references unchanged, counterfeit
verdict JSON, clean early exit, missing/import-failed interfaces, boolean answers,
altered input files, stale responses and changed controller/regression identities.
Correct fixture behavior passes; valid wrong answers reproduce a baseline
assertion failure, while crashes and malformed responses do not.

Retained independent scope/export/audit/approval/operator controls: **13 passed,
zero failures/errors/skips**, 0.516 seconds. Both executions used the ordinary
isolated backend runner and recorded zero external network attempts. They are
separate evidence sets, not an inflated unique repository-suite total.

Both original RED probe methods remain byte-for-byte unchanged by AST source
hash. Rerunning those legacy direct API calls gives **one pass and one error**:
the stronger old reproduction calls `run_suite` without the newly required
external executor and receives `ValueError` before candidate execution. It is
not reported as a green rerun. The new application-only forgery probe exercises
the supported explicit fixture boundary and passes independently.

Exact commands (private security directory added to `PYTHONPATH`):

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py ss1_closure --verbosity 2
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py security_support.IndependentSupportSecurity security_support.IndependentOperatorSecurity.test_archive_traversal_case_collision_and_file_prefix_are_rejected security_support.IndependentOperatorSecurity.test_no_credentials_or_application_settings_are_inherited security_support.IndependentOperatorSecurity.test_local_nonlinux_host_has_no_code_execution_fallback security_support.IndependentOperatorSecurity.test_plain_import_errors_and_skipped_runs_cannot_count_as_reproduction --verbosity 2
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py security_support.IndependentOperatorSecurity.test_candidate_process_must_not_forge_a_successful_test_run security_support.IndependentOperatorSecurity.test_candidate_application_import_must_not_forge_unchanged_regression_completion --verbosity 2
```

Private evidence: `SS1-approved-baseline.json`, `ss1_closure.py`,
`SS1-independent-closure.log`, `SS1-retained-controls.log`,
`SS1-original-probes-unchanged.log`, `SS1-closure-source-before.json`,
`SS1-closure-source-after.json` and `SS1-closure-executions.json`. Initial RED logs
and `SS1-observed.json` remain preserved. This reviewer did not execute Docker;
actual Linux Docker isolation and the synthetic draft-PR rehearsal remain
separate lead-owned CI gates. Bounded correct business behavior is not proof
that arbitrary proposed code is universally correct or nonmalicious.

## Historical initial review: confirmed finding before owner-approved repair

2 November 2026. Independent Agency Application Security Engineer review of
`.local/b7`, `feat/gpt-support-workflow-20261102`. Read `AGENTS.md`, development
rules, handoff, support requirements and the installed AppSec definition.
The reviewer owns only private probes/receipts and this report. No application,
core test, workflow, operational data, service or approval was changed.

**Initial disposition: SS1 / Medium is reproduced and UNFIXED, pending explicit owner
approval.** The bounded review has 13 passing controls and two failing security
assertions reproducing the same SS1 issue. No sandbox escape, cross-company
access or automatic engineering approval was established. This is not an
approval of deployment or universally secure operation.

## Scope and trust boundaries

Reviewed current administrator/company/project scope, immutable support reports
and events, diagnostic ZIP contents, owner-only receipt/approval transitions,
current-runtime installation binding, host source export/patch preparation,
fixed Docker profile, test evidence and the disposable rehearsal workflow.

The web process records explicitly **operator-attested** evidence and does not
execute patches or contact a model. The host must treat proposed candidate code
as less trusted than its controller. Docker protects the host boundary; it does
not make output produced by candidate code authoritative test evidence.

## SS1 — Medium: candidate code can counterfeit successful test execution

**Status:** confirmed, UNFIXED. Owner approval is required before remediation.

**Locations:** `scripts/support_repair.py`, `test_result` (around line399),
`run_suite` (around line413), `container_run` (around line484), and the receipt
assembly/returned-evidence validation. Exact line numbers may move after review.

`test_result` accepts a zero process exit together with text containing
`Ran 1 test in ...` and a separate `OK` line. `run_suite` obtains that text from
the interpreter importing the candidate. Candidate application code can print
those lines and call `os._exit(0)` during import, before the regression framework
executes any assertions. The controller records `passed=True` and `tests=1`.

The stronger independent reproduction leaves both regression test files
byte-identical between baseline and candidate. Baseline application code returns
the wrong duplicate count, producing a real assertion failure in both stages.
The proposed repair changes **only `counter.py`** to this safe synthetic payload:

```python
import os, sys
sys.stdout.write("Ran 1 test in 0.001s\n\nOK\n")
sys.stdout.flush()
os._exit(0)
```

Both unchanged test modules import that application module. Observed results:

| Stage | Actual behavior | Controller result |
| --- | --- | --- |
| Baseline unit | One actual assertion fails | tests1, failures1, exit1, passedFalse |
| Baseline integration | One actual assertion fails | tests1, failures1, exit1, passedFalse |
| Candidate unit | Import prints forged summary and exits before assertions | tests1, failures0, exit0, **passedTrue** |
| Candidate integration | Same early import exit; regression file unchanged | tests1, failures0, exit0, **passedTrue** |

This does not require changing the protected operator script, its input archive,
or the regression files. The related first reproduction uses an importing test
module with no test methods and obtains the same false success. Both expected
rejection assertions remain RED; the original source and logs are retained.

**Impact:** an untrusted proposed repair can manufacture the successful test
evidence presented to the operator and later recorded alongside a PR. Human
owner approval is still required and the website labels receipts as attested,
which limits impact. No host escape, production write or role escalation was
shown. The false test-execution claim nevertheless weakens the maintenance
approval decision and does not satisfy a trustworthy exact-tested-candidate
claim for adversarial code.

**Recommendation:** do not treat candidate-produced console text as proof that
trusted regression assertions executed. Keep regression/controller artifacts
immutable and outside candidate control; evaluate independent black-box checks
from a protected controller process, detect early/interpreter exits, and bind
structured controller results and expected test identities to the exact source.
Continue human patch review. A JSON report written by the same untrusted
interpreter, or a stronger regex alone, is insufficient. Reproduce this case
after an owner-approved design change and retain the original RED evidence.

## Executed independent controls

Command from B7, with `PYTHONPATH` set only to the private security harness:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py security_support --verbosity 2
```

Final expanded run: **15 tests, 13 passed, 2 failed (SS1), zero errors/skips**,
1.065 seconds of test execution. Zero external network attempts and zero
in-process HTTP-fixture connections. Both candidate probes use actual bounded
subprocesses and safe temporary files under the F: project. They are not actual
Docker execution or physical-server evidence.

Passing controls cover:

- Anonymous/operational-role denial; current active owner/Admin authority;
  profile-only owner forgery, cached profile and revoked membership rejection.
- Foreign-company and same-company/different-project access; company-level
  report restricted to creator and platform owner.
- Actual two-file ZIP, canonical digest, omitted secret canaries/free text/raw
  logs/model names/paths and escaped description output.
- CSRF, overposting, immutable report/event operations and transactional rollback
  when the existing governance audit fails.
- Owner-only receipt/approval, case/source/digest/type/PR-repository tampering,
  stale actions, idempotent replay and actual configured release matching.
- Engineering row unchanged through the support lifecycle.
- Archive traversal, case collision and file-prefix conflict rejection; clean
  child environment; unsupported local execution fails closed; empty/error/skipped
  test runs cannot serve as an ordinary regression reproduction.

The first run had one additional private-harness failure because it demanded
exact `Cache-Control: private, no-store`; Django added stronger no-cache
directives. Only that overstrict harness assertion was corrected to require the
security directives as a subset. No application behavior was changed or security
finding suppressed. Initial logs remain preserved.

## Evidence and limits

Private directory: `.local/support-development-20261102/security/`.
Artifacts include `source-before.json`, `source-after.json`,
`SS1-original-harness.py`, current `security_support.py`, `security-first.log`,
`security-final.log`, `security-final-expanded.log`, `SS1-observed.json` and
`review-receipt.json`. These are independent executions; their counts overlap
functional coverage and must not inflate the repository's unique test total.

Host functional freeze reviewed:

- `scripts/support_repair.py` SHA256
  `6513d6d9fcfe17362eeaef790990d40b7853454481dbb7cdc136800105db7ffb`.
- `scripts/support_repair_rehearsal.py` SHA256
  `44d48fb304a20d0f466bf1d99814a97a9732403bedd9a7d20b566971d3452931`.

Actual Docker CI, real synthetic draft PR, deployment/device/native AI and full
release acceptance remain separate lead-owned evidence gates. No Docker daemon
or production/model service was invoked by this reviewer. The existing eight
held findings A12/BR1/D1/D2/L1/CS1/CS2/AI1 retain their approval status; CP1/CP2/UP1
closures are not permission to repair SS1 or any earlier hold. No merge, push,
customer release or operational approval was performed.
