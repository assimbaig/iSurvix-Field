# A12 native investigation on the target PC

28 October 2026. Baseline `fd365f107b75c370caa2b765837d2a23f907a80c`.
Installed Agency Backend Architect and Reality Checker profiles guided this
diagnosis. No application code, runtime installation, model, operational record
or approval was changed.

**Task03 remains Blocked.** The historical crash cause is not established, the
standard local runtime cannot start its runner, and the diagnostic runtime's
three completed image requests did not pass their source-backed text checks.

## Separate the three observations

| Observation | Actual evidence | Conclusion |
| --- | --- | --- |
| Historical A12 | Linux Python process exited139 during an805-test candidate run; the last announced test used mocked inference. That test passed alone and a later805-test run passed. | Last test name is not a native backtrace or proven cause. This is not established as an Ollama crash. |
| Current standard runtime | Loopback11434, Ollama0.40.10, `qwen3.5:4b` installed and reporting vision. A request containing actual PNG bytes returned HTTP500: `llama-server binary not found`. Expected runner files are absent. | Current generation is blocked by runner startup/package availability. Metadata success is not image-generation success. Why the package lacks its runner was not established. |
| Existing bundled diagnostic runtime | Already installed project Ollama0.40.5, temporarily started on owned loopback11436, completed three actual-image requests. Their exact printed labels were all read incorrectly. | Transport/generation completed3/3; source-backed label correctness passed0/3. This is not successful vision acceptance or a repair of the standard service. |

## Historical A12 provenance

The controlling record is `docs/audits/2026-10-23-post-sync-audit.md`, rowA12,
and `docs/audits/2026-10-23-evidence/verification.json` /
`test-results.txt`. They record Linux, Python3.12.14, Django6.1.2,
ONNX Runtime1.31.0, OpenCV5.0.0, PyMuPDF2.0 and Pillow10.4.0.
The recorded failing-log SHA256 is
`f31317b5bf97b2ba70ecb3ce22c36f378e1afa446b42d2d2b1c83a8dd3976b4a`.
That is a historical recorded hash, not a newly obtained crash dump.

The last announced test was
`core.test_photo_workflow.PhotoWorkflowTests.test_lost_lease_after_single_vision_call_prevents_metadata_cache`.
Its inference call is mocked. On the current target PC, five fresh isolated
process runs of that named regression passed, using the established backend
runner and fault-handler-enabled diagnostic execution. No model call or external
request occurred. The current named function's AST also matches the historical
base `d2a053b`; that comparison does not reconstruct the full failing candidate,
native dependency builds or Linux environment.

The original record says the case passed alone in0.271s and a later805-test
suite passed. None of those passes closes the original intermittent native
crash. Three relevant Windows Application events from the last14days were
`RADAR_PRE_LEAK_64` warnings, not a segmentation-fault backtrace explaining the
earlier Linux process.

## Actual target-PC evidence

- Windows11 build26300, Python3.12.10; NVIDIA GeForce RTX3060Ti,
 8192MiB, driver610.88.
- Installed model: `qwen3.5:4b`, digest
 `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
 Its vision capability was checked before sending images.
- Standard11434: one actual-image request failed HTTP500 in0.093s.
 Both expected standard runner locations were checked and absent; the existing
 project runtime had its runner. No binary was copied between runtime versions.
- Diagnostic11436: three different synthetic800x320 PNGs were sent as base64
 image content. Filenames did not contain the expected labels; the prompt asked
 the model to read the pixels. The first image was visually inspected and its
 printed label is clear and uncropped.

| Image | Expected visible label | Actual structured answer | Request elapsed | Result |
| --- | --- | --- | --- | --- |
| 1 | NATIVE 728 | HAT8 | 38.563s | Incorrect |
| 2 | PIXEL 314 | PXL14 | 0.516s | Incorrect |
| 3 | VISION 905 | WUS | 0.469s | Incorrect |

The first diagnostic request reported18.590s model loading. These are three
bounded label requests, not a site survey, real equipment benchmark, sustained
photo throughput or engineering-compliance test. Incorrect outputs were never
written into operational findings, checklist answers or approvals. The reason
for the diagnostic runtime/model's incorrect reading is not established by this
small probe; no common cause with A12 or the standard runner failure is claimed.

## Preservation and teardown

The standard listener on11434 stayed at its original PID14996 and version0.40.10.
Only the owned diagnostic server on11436 and its child were stopped after exact
executable-path, command and loopback-listener ownership checks. Its final owned
process IDs were32216 and32224;11436 no longer listens. No model was downloaded,
no runtime was installed/repaired/restarted, no app/worker was started and no
operational database, evidence original or source approval was changed.

Private evidence stays under `.local/baseline-20261028/native/`: standard and
bundled metadata/results, synthetic images and their SHA256, five isolated test
logs, Windows event summary, runner-file check, GPU receipt and `teardown.json`.
Raw logs and local user paths are not copied into this public report. Requests
that had already completed before the agent interruption were inspected rather
than repeated.

## Exact blockers and next evidence required

1. **A12 root cause:** obtain the original Linux native core/backtrace or a
 reproducible failing environment with exact candidate/dependency/native-binary
 builds. Reproduce with `PYTHONFAULTHANDLER=1`, retaining exit signal, all-thread
 stack/core, command and native module/build identities. A Windows pass cannot
 supply a missing Linux faulting stack.
2. **Standard runtime:** a complete, compatible installation including its
 `llama-server` runner is needed before the standard endpoint can pass an actual
 image request. Runtime repair was outside this diagnostic change and was not
 performed; model metadata alone must not mark the connection healthy.
3. **Vision correctness:** after a supported runtime/model pairing is available,
 rerun source-checked image tests and investigate wrong answers before any
 operational survey benchmark. HTTP200 is insufficient. Do not approve work or
 invent findings from these responses.

No new security remediation was performed. This diagnosis does not authorize
fixing unrelated approval-held findings. The original crash, current missing
runner and current incorrect image answers remain separate issues until causal
evidence connects them.
