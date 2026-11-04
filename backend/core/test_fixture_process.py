"""Process-capture fixtures; no application/model/operational processes are run.

The launcher must finish within its process budget. Output may remain inherited
by a bounded fixture descendant, which must not keep a completed launcher alive.
"""
from pathlib import Path
import json
import locale
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid

from django.test import SimpleTestCase


class FixtureProcessTimeout(subprocess.TimeoutExpired):
    """Bounded, fixture-only diagnostics; never dumps the parent environment."""
    def __init__(self, command, timeout, pid, poll_at_deadline, poll_after_cleanup, stdout, stderr):
        super().__init__(Path(str(command[0])).name, timeout, output=stdout, stderr=stderr)
        self.pid = pid
        self.poll_at_deadline = poll_at_deadline
        self.poll_after_cleanup = poll_after_cleanup
        phases = re.findall(r'IFIELD_FIXTURE_PHASE=([a-z-]+)', stderr)
        self.last_phase = phases[-1] if phases else 'host-entry-not-observed'

    def __str__(self):
        return ('Fixture process exceeded its unchanged process budget: ' + json.dumps({
            'program': self.cmd, 'timeout_seconds': self.timeout, 'pid': self.pid,
            'poll_at_deadline': self.poll_at_deadline, 'poll_after_cleanup': self.poll_after_cleanup,
            'last_phase': self.last_phase, 'stdout_tail': self.output, 'stderr_tail': self.stderr}))


def _output_tail(path, maximum=8192):
    with path.open('rb') as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - maximum))
        return stream.read().decode(locale.getpreferredencoding(False), errors='replace')


def run_fixture_process(arguments, directory, *, timeout=30, env=None):
    """Wait for the actual fixture process, independently of inherited stream EOF.

    Files retain partial phase/output evidence on a deadline. The original30s
    launcher budget is preserved; exit codes and output assertions remain caller
    responsibilities. Only the process created here is terminated on a timeout.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = uuid.uuid4().hex
    stdout_path = directory / (stamp + '.stdout.log')
    stderr_path = directory / (stamp + '.stderr.log')
    environment = dict(os.environ if env is None else env)
    environment.update({name: str(directory) for name in ('TMP', 'TEMP', 'TMPDIR')})
    exceeded = None
    started = time.monotonic()
    with stdout_path.open('wb') as stdout, stderr_path.open('wb') as stderr:
        process = subprocess.Popen(arguments, stdout=stdout, stderr=stderr,
            env=environment, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            exceeded = process.poll()
            if exceeded is None:
                process.kill()
            process.wait(timeout=5)
            exceeded = (exceeded, process.poll())
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            raise
    captured_stdout = _output_tail(stdout_path)
    captured_stderr = _output_tail(stderr_path)
    if exceeded is not None:
        raise FixtureProcessTimeout(arguments, timeout, process.pid, exceeded[0], exceeded[1],
            captured_stdout, captured_stderr)
    result = subprocess.CompletedProcess(arguments, process.returncode, captured_stdout, captured_stderr)
    result.pid = process.pid
    result.elapsed = time.monotonic() - started
    return result


class FixtureProcessCaptureTests(SimpleTestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / '.local' / 'test-runs'
        root.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='process-capture-', dir=root)
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        # Plain stdlib fixtures use the real base interpreter, not a Windows
        # venv launcher that introduces another unrelated process boundary.
        self.python = getattr(sys, '_base_executable', sys.executable)

    def script(self, name, source):
        path = self.directory / name
        path.write_text(source, encoding='utf-8')
        return path

    def wait_for_file(self, path, seconds=5):
        deadline = time.monotonic() + seconds
        while not path.exists():
            if time.monotonic() >= deadline:
                self.fail('The bounded process fixture did not finish its cleanup.')
            time.sleep(.01)

    def wait_for_owned_child(self, pid, finished):
        self.wait_for_file(finished)
        if os.name == 'nt':
            import ctypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only
            if handle:
                try:
                    self.assertEqual(kernel.WaitForSingleObject(handle, 5000), 0,
                        'The test-owned stream holder must exit after release.')
                finally:
                    kernel.CloseHandle(handle)
            else:
                self.assertEqual(ctypes.get_last_error(), 87, 'Unexpected process-query failure')
        elif sys.platform.startswith('linux'):
            stat = Path('/proc') / str(pid) / 'stat'
            deadline = time.monotonic() + 5
            while stat.exists():
                try:
                    state = stat.read_text().split(') ', 1)[1][0]
                except FileNotFoundError:
                    break
                if state == 'Z':
                    break  # Exited; awaiting the OS reaper, not an active worker.
                if time.monotonic() >= deadline:
                    self.fail('The test-owned stream holder is still running.')
                time.sleep(.01)

    def test_completed_launcher_is_not_blocked_by_inherited_output_handles(self):
        release = self.directory / 'release'
        ready = self.directory / 'child-ready'
        finished = self.directory / 'child-finished'
        parent_done = self.directory / 'parent-done'
        child = self.script('stream_holder.py', '''from pathlib import Path
import os,sys,time
release,ready,finished=map(Path,sys.argv[1:])
ready.write_text(str(os.getpid()))
deadline=time.monotonic()+15
while not release.exists() and time.monotonic()<deadline:time.sleep(.01)
reason='released' if release.exists() else 'bounded-deadline'
sys.stdout.close();sys.stderr.close()
finished.write_text(reason)
''')
        launcher = self.script('completed_launcher.py', '''from pathlib import Path
import json,os,subprocess,sys,time
child,release,ready,finished,parent_done=sys.argv[1:]
holder=subprocess.Popen([sys.executable,child,release,ready,finished],
 stdin=subprocess.DEVNULL,stdout=sys.stdout,stderr=sys.stderr,
 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
deadline=time.monotonic()+8
while not Path(ready).exists():
 if holder.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Child fixture did not become ready')
 time.sleep(.01)
Path(parent_done).write_text(str(os.getpid()))
print(json.dumps({'completed':True}),flush=True)
''')
        try:
            try:
                result = run_fixture_process([self.python, str(launcher), str(child),
                    str(release), str(ready), str(finished), str(parent_done)], self.directory,
                    timeout=5)
            except subprocess.TimeoutExpired as error:
                self.fail('Completed launcher was blocked by inherited output handles: '
                    f'parent_done={parent_done.exists()}, poll_at_deadline={getattr(error,"poll_at_deadline",None)}')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {'completed': True})
            self.assertTrue(parent_done.exists())
            self.assertTrue(ready.exists())
            self.assertFalse(finished.exists(), 'The holder must actually retain streams until released.')
        finally:
            release.touch()
            if ready.exists():
                self.wait_for_owned_child(int(ready.read_text()), finished)

    def test_nonzero_exit_and_both_output_streams_are_retained(self):
        script = self.script('failure.py', '''import sys
print('fixture stdout',flush=True)
print('IFIELD_FIXTURE_PHASE=body',file=sys.stderr,flush=True)
sys.exit(7)
''')
        result = run_fixture_process([self.python, str(script)], self.directory)
        self.assertEqual(result.returncode, 7)
        self.assertIn('fixture stdout', result.stdout)
        self.assertIn('IFIELD_FIXTURE_PHASE=body', result.stderr)

    def test_live_process_still_times_out_with_phase_and_partial_output(self):
        script = self.script('bounded_hang.py', '''import sys,time
print('partial fixture stdout',flush=True)
print('IFIELD_FIXTURE_PHASE=body',file=sys.stderr,flush=True)
time.sleep(30)
''')
        environment = {**os.environ, 'ISURVIX_TEST_PRIVATE_ENV': 'synthetic-never-dump-environment'}
        with self.assertRaises(FixtureProcessTimeout) as raised:
            run_fixture_process([self.python, str(script)], self.directory, timeout=5, env=environment)
        error = raised.exception
        self.assertEqual(error.timeout, 5)
        self.assertIsNone(error.poll_at_deadline)
        self.assertIsNotNone(error.poll_after_cleanup)
        self.assertEqual(error.last_phase, 'body')
        self.assertIn('partial fixture stdout', error.output)
        self.assertIn('IFIELD_FIXTURE_PHASE=body', error.stderr)
        self.assertNotIn(environment['ISURVIX_TEST_PRIVATE_ENV'], str(error))
