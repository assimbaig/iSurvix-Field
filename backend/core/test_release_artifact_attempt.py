"""Attempt-bound artifacts; IDs are opaque and old rerun artifacts stay intact."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen
from unittest.mock import patch
from django.test import SimpleTestCase
from .test_release_gate import module, SHA, REPO

class AttemptArtifactsTests(SimpleTestCase):
    def setUp(self):
        self.g=module()
        self.run={'id':123,'run_attempt':2,'head_sha':SHA,'path':'.github/workflows/customer-server-verification.yml','status':'completed','conclusion':'success','repository':{'full_name':REPO,'id':9},'head_repository':{'full_name':REPO,'id':9}}
        self.jobs=[{'id':77,'run_id':123,'run_attempt':2,'head_sha':SHA,'name':'disposable-linux','status':'completed','conclusion':'success','started_at':'2026-11-07T13:40:00Z','completed_at':'2026-11-07T13:50:00Z'}]
        def artifact(i,name,time):
            return {'id':i,'name':name,'expired':False,'created_at':time,'workflow_run':{'id':123,'head_sha':SHA,'repository_id':9,'head_repository_id':9}}
        self.artifacts=[artifact(13576260462,'customer-server-DRAFT-candidate','2026-11-07T13:23:00Z'),artifact(13576228539,'customer-server-DRAFT-candidate','2026-11-07T13:44:00Z'),artifact(2,'customer-server-verification','2026-11-07T13:43:00Z')]

    def select(self):
        return self.g.select_attempt_artifacts(self.run,self.jobs,self.artifacts,repository=REPO,release_id=SHA,run_id=123,run_attempt=2)

    def test_rerun_selects_newer_time_despite_smaller_id(self):
        self.assertEqual(self.select(),{'candidate_artifact_id':13576228539,'verification_artifact_id':2})

    def test_missing_duplicate_expired_foreign_and_wrong_attempt_fail_closed(self):
        original=copy.deepcopy((self.run,self.jobs,self.artifacts))
        for kind in ('missing','duplicate','expired','foreign','mixed','attempt','jobtime','pending','repository'):
            with self.subTest(kind=kind):
                self.run,self.jobs,self.artifacts=copy.deepcopy(original)
                if kind=='missing':self.artifacts.pop()
                if kind=='duplicate':self.artifacts.append(dict(self.artifacts[-1],id=3))
                if kind=='expired':self.artifacts[-1]['expired']=True
                if kind=='foreign':self.artifacts[-1]['workflow_run']['repository_id']=10
                if kind=='mixed':self.artifacts[-1]['created_at']='2026-11-07T13:23:00Z'
                if kind=='attempt':self.jobs[0]['run_attempt']=1
                if kind=='jobtime':self.jobs[0]['completed_at']=None
                if kind=='pending':self.run['status']='in_progress'
                if kind=='repository':self.run['head_repository']['full_name']='foreign/repo'
                with self.assertRaises(ValueError):self.select()

    def test_fetch_uses_exact_attempt_jobs_and_paginated_run_artifacts(self):
        paths=[]
        def api(path,token):
            paths.append(path)
            if path.endswith('/attempts/2'):return self.run
            if '/attempts/2/jobs?' in path:return {'jobs':self.jobs}
            if '/artifacts?' in path:return {'artifacts':self.artifacts}
            self.fail(path)
        with patch.object(self.g,'_api',side_effect=api):
            value=self.g.fetch_attempt_artifacts(REPO,SHA,123,2,'synthetic')
        self.assertEqual(value['candidate_artifact_id'],13576228539)
        self.assertEqual(len(paths),3)
        self.assertIn('/attempts/2/jobs?',paths[1])

    def test_duplicate_jobs_and_artifact_ids_and_invalid_windows_are_rejected(self):
        original=copy.deepcopy((self.jobs,self.artifacts))
        for kind in ('jobs','id','reverse','naive','head'):
            with self.subTest(kind=kind):
                self.jobs,self.artifacts=copy.deepcopy(original)
                if kind=='jobs':self.jobs.append(dict(self.jobs[0],id=78))
                if kind=='id':self.artifacts[-1]['id']=self.artifacts[1]['id']
                if kind=='reverse':self.jobs[0]['completed_at']='2026-11-07T13:30:00Z'
                if kind=='naive':self.artifacts[-1]['created_at']='2026-11-07T13:43:00'
                if kind=='head':self.jobs[0]['head_sha']='b'*40
                with self.assertRaises(ValueError):self.select()

    def test_created_timestamp_not_updated_and_inclusive_job_bounds(self):
        self.artifacts[0]['updated_at']='2026-11-07T13:45:00Z'
        self.artifacts[1]['created_at']=self.jobs[0]['started_at']
        self.artifacts[-1]['created_at']=self.jobs[0]['completed_at']
        self.assertEqual(self.select()['candidate_artifact_id'],13576228539)

    def test_http_paginated_cli_selects_exact_ids_without_exposing_credential(self):
        outer=self;paths=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                paths.append(self.path)
                if self.path.endswith('/attempts/2'):data=outer.run
                elif '/attempts/2/jobs?' in self.path:data={'jobs':outer.jobs}
                elif '/artifacts?' in self.path and '&page=1' in self.path:
                    data={'artifacts':[dict(outer.artifacts[0],id=100+i) for i in range(100)]}
                elif '/artifacts?' in self.path and '&page=2' in self.path:data={'artifacts':outer.artifacts[1:]}
                else:self.send_error(404);return
                raw=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(thread.join,3);self.addCleanup(server.shutdown)
        def api(path,token):
            self.assertEqual(token,'synthetic-only')
            with urlopen(f'http://127.0.0.1:{server.server_port}'+path,timeout=3) as response:return json.load(response)
        root=Path(__file__).resolve().parents[2]/'.local';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary,patch.object(self.g,'_api',side_effect=api),patch.dict(os.environ,{'GITHUB_TOKEN':'synthetic-only'}):
            temp=Path(temporary);gate=temp/'gate.json';output=temp/'artifacts.json'
            checks={name:{'source_commit':SHA,'status':'completed','conclusion':'success','run_id':i+121,'run_attempt':2} for i,name in enumerate(self.g.REQUIRED_WORKFLOWS)}
            gate.write_text(json.dumps({'source_commit':SHA,'customer_run_id':123,'required_checks':checks}))
            self.g.main(['artifacts','--repository',REPO,'--gate',str(gate),'--output',str(output)])
            self.assertEqual(json.loads(output.read_text()),{'candidate_artifact_id':13576228539,'verification_artifact_id':2,'run_id':123})
            self.assertNotIn('synthetic-only',output.read_text())
            self.assertEqual(len(paths),4)
            outer.jobs[0]['run_attempt']=1
            with self.assertRaises(SystemExit):self.g.main(['artifacts','--repository',REPO,'--gate',str(gate),'--output',str(temp/'denied.json')])
            self.assertFalse((temp/'denied.json').exists())
