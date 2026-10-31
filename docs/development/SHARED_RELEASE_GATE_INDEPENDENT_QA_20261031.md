# Independent shared-release gate QA — 31 October 2026

Scope: task19's existing-source candidate gate in `.local/b6`, branch
`feat/customer-server-readiness-20261031`. Read repository rules/handoff and used
installed Agency Reality Checker/API Tester definitions. The reviewer did not
implement or edit `deploy/release_gate.py`, CI workflows or tracked gate tests.
Only the private independent test module and this report were authored.

## Findings reproduced and repaired during functional QA

Initial independent execution ran six cases in **0.606 seconds**: two passed,
three failed and one errored. No external network attempts occurred; two requests
reached the in-process HTTP fixture. The RED receipt is preserved.

1. **Recent failed rerun ignored:** a later failed attempt of an older workflow
   run number could be hidden by an earlier success with a higher run number.
   The repaired selector uses reliable timezone-aware update chronology before
   attempt/run ordering; it does not let the older successful observation win.
2. **Proof did not bind artifact identity:** a same-source proof naming different
   image IDs or a different manifest digest was accepted. The repaired record
   constructor requires the verified package's exact images and manifest SHA256
   in the actual installation/upgrade proof.
3. **Deleted/absent repository metadata:** a record with `head_repository=null`
   raised `AttributeError`. It now produces a controlled fail-closed outcome.

The reviewer additionally identified a gap between the first API check and
artifact transfer. The lead added a fresh API check after download and before
record assembly. The constructor requires matching source/run IDs/attempts, with
a final observation no older than120seconds. A newer successful run with different
identities requires obtaining its artifacts again. Failed/pending required runs
cannot supply a fresh successful gate.

These were functional integration findings repaired by the lead before separate
security review. They did not authorize repairs to any older held finding.

## Independent retest

The independent valid proof fixture was updated to include the new mandatory
image IDs and manifest hash. This is important: negative checks were not allowed
to pass merely because an otherwise valid proof lacked a new required field.
A separate positive case verifies candidate persistence and no overwrite.

With process-local `PYTHONPATH=.local/customer-server-20261031/qa`:

```text
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts\run_backend_tests.py release_gate_independent.IndependentSharedReleaseGateTests core.test_release_gate --verbosity 1
```

**19 passed in 1.259 seconds**: eight independently written private cases plus
eleven tracked cases. Zero failures/errors/skips and zero external network
attempts; four HTTP requests reached controlled in-process fixtures. These tests
overlap focused/full-suite execution; do not add them to a unique suite total.

Independently exercised behaviors:

- Recent failed reruns block eligibility, including a rerun of an older run ID.
- Proof images/manifest must match a fully valid same-source package identity.
- Missing repository metadata fails without an unhandled attribute error.
- Pagination actually reads a second HTTP page before accepting required checks.
- A full bounded ten-page result set fails rather than assuming provenance is
  complete.
- A valid record retains exact immutable image/digest/support identities, stays
  explicitly unapproved and cannot overwrite an existing record.
- The final gate accepts the same fresh run/attempt set and rejects changed IDs,
  changed attempts, missing timestamps, observations180seconds old and observations
  in the future.

Private files: `qa/release_gate_independent.py`,
`qa/release-gate-independent-red.log`, `qa/release-gate-independent-green.log`
and `qa/release-gate-independent-final.log` under
`.local/customer-server-20261031`.

## Workflow inspection and limits

The shared workflow checks out the explicit PR-head/source SHA, requires the
application/staging/customer workflows for that SHA, and downloads the existing
customer bundle and proof from the selected customer run. It does not rebuild a
different edition image. It rechecks after download, assembles a draft record,
and uploads an unapproved review artifact. No merge, production release or
deployment is performed by this gate.

This is **point-in-time CI evidence**, not a guarantee against later future
workflow failures or authenticated publication provenance beyond the trusted
GitHub run/artifact channel. Artifact/manifest SHA256 checks do not independently
authenticate an attacker replacing both data and every trust record.

Actual GitHub execution, artifact retrieval, final image archives and a real
supported-version upgrade/recovery proof remain separate required evidence.
At this review stage, the customer rehearsal had not yet produced the required
`upgrade_recovery_verified`/`supported_from` proof; the actual shared candidate
must therefore remain blocked rather than treating fixture booleans as proof.
No real token, external API, native Ollama, paid service, customer record or
operational approval was used by the independent tests. Separate security review
and final integrated/target acceptance remain outstanding gates.
