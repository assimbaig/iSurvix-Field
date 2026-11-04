# Verification environment and directory redirects

Use Python3.12 and the repository's ordinary test runner from the checkout root:

```powershell
.local\venv\Scripts\python.exe scripts\run_backend_tests.py --verbosity 1
```

The runner isolates the database, media and model caches and rejects external
service connections. Native-model verification remains separate. Use the reviewed
bootstrap installer requirements before installing application requirements in a
new environment; do not replace an operating installation's environment or data
as part of tests.

## Real directory-link coverage

Diagnostic-path security tests must use a genuine filesystem redirect and retain
their rejection/no-target-writes assertions. `directory_redirect()` first creates
a native directory symlink. On Windows only, an exact WinError1314 means that
the current token lacks the symbolic-link privilege; the fixture then creates a
real NTFS junction. It verifies the physical redirect and target identity and
removes only the link node during cleanup. Other errors are not suppressed.

Linux and Windows accounts with the required privilege still exercise native
symlinks. A Windows run that uses the junction fallback proves that redirect
boundary, **not native Windows-symlink execution**. The helper tests additionally
force the1314 creation error and verify a genuine junction, target preservation
and propagation of unrelated permission failures. No test is skipped and no
security assertion is replaced with a mock.

## Diagnostic watchdog limitation

Avoid wrapping a threaded development server in a repeated native
`faulthandler.dump_traceback_later()` watchdog. Asynchronous all-thread stack
traversal has documented interpreter hazards; unrelated application frames in a
crash dump do not establish that application's cause. Prefer bounded on-demand
captures from a normal Python thread, and retain exit codes, process identities
and raw logs. This diagnostic precaution does not repair CPython or prove that
every crash has the same cause.

See the [CPython maintainer discussion](https://github.com/python/cpython/issues/131580)
and its linked issue116008. Production/runtime and native-AI acceptance must remain
separate from a diagnostic experiment.
