import subprocess
import sys
import tempfile
from pathlib import Path
from django.test import SimpleTestCase
from .test_invitation_mail_runtime import runtime_module, ROOT


class ExportRuntimeTests(SimpleTestCase):
    def test_export_worker_runs_without_email_and_stops_with_web(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.local',prefix='export-runtime-') as directory:
            marker=Path(directory)/'started';children=[]
            def spawn(*args,**kwargs):
                process=subprocess.Popen(*args,**kwargs);children.append(process);return process
            try:
                result=runtime_module().supervise(
                    [sys.executable,'-c','import time;time.sleep(0.5)'],mail_enabled=False,
                    export_command=[sys.executable,'-c',f'import time;from pathlib import Path;Path({str(marker)!r}).write_text("started");time.sleep(10)'],
                    export_enabled=True,readiness=lambda:True,poll_interval=0.02,
                    retry_interval=0.1,shutdown_timeout=0.5,spawn=spawn)
                self.assertEqual(result,0);self.assertTrue(marker.exists())
                self.assertEqual(len(children),2)
                self.assertTrue(all(p.poll() is not None for p in children))
            finally:
                for p in children:
                    if p.poll() is None:p.kill()
                    p.wait(timeout=3)

    def test_private_candidate_does_not_start_export_worker(self):
        spawned=[]
        def spawn(*args,**kwargs):
            process=subprocess.Popen(*args,**kwargs);spawned.append(process);return process
        runtime_module().supervise([sys.executable,'-c','import time;time.sleep(.1)'],
            export_command=[sys.executable,'-c','raise SystemExit(99)'],export_enabled=True,
            readiness=lambda:False,poll_interval=0.02,retry_interval=0.1,
            shutdown_timeout=.5,spawn=spawn)
        self.assertEqual(len(spawned),1)
