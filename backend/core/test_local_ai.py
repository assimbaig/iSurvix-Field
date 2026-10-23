import json
import ast
from io import BytesIO
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from urllib.error import HTTPError
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings
from .models import Checklist, ChecklistTemplate, Profile, Project


@override_settings(ROOT_URLCONF='checklist.urls_local', LOCAL_AI_ENABLED=True, OLLAMA_BASE_URL='http://127.0.0.1:11434', OLLAMA_MODEL='qwen3.5:4b', OLLAMA_TIMEOUT=5)
class LocalAITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('local_engineer', password='Local-test-pass-726!')
        self.project = Project.objects.create(name='Local project')
        self.user.profile.role, self.user.profile.project = Profile.Roles.ENGINEER, self.project
        self.user.profile.save()
        self.client.force_login(self.user)
        schema = {'title': 'Local fixture', 'sections': [{'id': 'general', 'title': 'Site details', 'fields': [{'id': 'height', 'type': 'number', 'label': 'Height', 'required': True}]}]}
        self.template = ChecklistTemplate.objects.create(name='Local fixture', definition=schema, published=True)
        self.project.checklist_template = self.template
        self.project.save()
        self.survey = Checklist.objects.create(project=self.project, user=self.user, site_id='LOCAL-001')

    def post(self, data, client=None):
        return (client or self.client).post('/local-ai/chat/', json.dumps(data), content_type='application/json')

    def test_authentication_and_csrf_required(self):
        anonymous = Client()
        self.assertEqual(anonymous.get('/local-ai/status/').status_code, 401)
        self.assertEqual(self.post({'question': 'Hello'}, anonymous).status_code, 401)
        self.assertEqual(anonymous.get('/app/').status_code, 410)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(self.post({'question': 'Hello'}, strict).status_code, 403)

    @patch('core.local_ai.ollama')
    def test_status_lists_only_local_models(self, call):
        call.return_value = {'models': [{'name': 'qwen3.5:4b'}, {'name': 'remote-cloud'}, {'name': 'remote:cloud'}, {'name': 'remote-custom', 'remote_host': 'https://ollama.com'}]}
        data = self.client.get('/local-ai/status/').json()
        self.assertEqual(data['models'], ['qwen3.5:4b'])
        self.assertTrue(data['model_installed'])

    @patch('core.local_ai.ollama')
    def test_context_is_read_only(self, call):
        call.side_effect = [{'models': [{'name': 'qwen3.5:4b'}]}, {'message': {'content': 'Height is missing.'}}]
        response = self.post({'question': 'What is missing?', 'checklist_id': self.survey.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['answer'], 'Height is missing.')
        payload = call.call_args.args[1]
        self.assertIn('LOCAL-001', payload['messages'][1]['content'])
        self.assertIn('Height', payload['messages'][1]['content'])
        self.assertFalse(payload['stream'])
        self.assertNotIn('tools', payload)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.answer_data, {})
        self.assertEqual(self.survey.status, Checklist.Status.DRAFT)

    @patch('core.local_ai.ollama')
    def test_other_project_and_engineer_denied(self, call):
        other = User.objects.create_user('other_engineer')
        same = Checklist.objects.create(project=self.project, user=other, site_id='OTHER-001')
        foreign = Project.objects.create(name='Other project', checklist_template=self.template)
        cross = Checklist.objects.create(project=foreign, user=other, site_id='OTHER-002')
        for c in [same, cross]:
            self.assertEqual(self.post({'question': 'Read this', 'checklist_id': c.pk}).status_code, 404)
        call.assert_not_called()
        page = self.client.get('/local/assistant/')
        self.assertContains(page, 'LOCAL-001')
        self.assertNotContains(page, 'OTHER-001')

    @patch('core.local_ai.ollama')
    def test_input_and_model_validation(self, call):
        call.return_value = {'models': [{'name': 'qwen3.5:4b'}]}
        for model in ['unknown', 'qwen-cloud']:
            self.assertEqual(self.post({'question': 'Hello', 'model': model}).status_code, 400)
        for question in ['', [], 'x' * 8001]:
            self.assertEqual(self.post({'question': question}).status_code, 400)
        self.assertEqual(self.post({'question': 'x' * 31000}).status_code, 413)
        self.assertEqual(self.post({'question': 'Hello', 'checklist_id': '../bad'}).status_code, 400)

    @patch('core.local_ai.ollama', side_effect=OSError('offline'))
    def test_disconnected_error(self, call):
        self.assertEqual(self.client.get('/local-ai/status/').status_code, 503)
        self.assertEqual(self.post({'question': 'Hello'}).status_code, 503)

    def test_busy_model(self):
        from .photo_queue import inference_lease
        with inference_lease():
            self.assertEqual(self.post({'question': 'Hello'}).status_code, 429)

    def test_sample_preview_retired_and_path_traversal_blocked(self):
        self.assertEqual(self.client.get('/app/').status_code, 410)
        self.assertIn(self.client.get('/app/../../backend/checklist/settings.py').status_code, (404, 410))
        self.assertEqual(self.client.get('/app/assets/site-routing.js').status_code, 410)
        self.assertEqual(self.client.get('/media/custom_evidence/test.png').status_code, 404)

    def test_loopback_and_redirect_controls(self):
        from django.test import RequestFactory
        from .local_ai import LoopbackOnlyMiddleware, NoRedirect, ollama
        from django.http import HttpResponse
        guard = LoopbackOnlyMiddleware(lambda request: HttpResponse('ok'))
        f = RequestFactory()
        self.assertEqual(guard(f.get('/', REMOTE_ADDR='192.168.1.20')).status_code, 403)
        self.assertEqual(guard(f.get('/', REMOTE_ADDR='127.0.0.1')).status_code, 200)
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com'))
        for base in ['https://ollama.com', 'http://192.168.1.2:11434', 'http://user:pass@localhost:11434', 'http://localhost:11434/path']:
            with override_settings(OLLAMA_BASE_URL=base), self.assertRaises(ValueError):
                ollama('/api/tags')

    def test_native_ollama_http_roundtrip(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                calls.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'models': [{'name': 'qwen3.5:4b'}]}).encode())
            def do_POST(self):
                calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'message': {'content': 'Local transport verified.'}}).encode())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with override_settings(OLLAMA_BASE_URL=f'http://127.0.0.1:{server.server_port}'):
                response = self.post({'question': 'Check local connection'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['answer'], 'Local transport verified.')
            self.assertEqual(calls[0], '/api/tags')
            self.assertEqual(calls[1]['model'], 'qwen3.5:4b')
            self.assertFalse(calls[1]['stream'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_local_settings_use_configured_photo_runtime_unless_text_is_explicit(self):
        settings_path=Path(__file__).resolve().parents[1]/'checklist'/'settings_local.py'
        tree=ast.parse(settings_path.read_text())
        names={'OLLAMA_BASE_URL','PHOTO_OLLAMA_BASE_URL'}
        selected=[statement for statement in tree.body if isinstance(statement,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id in names for target in statement.targets)]
        code=compile(ast.Module(body=selected,type_ignores=[]),str(settings_path),'exec')
        cases=[({},('http://127.0.0.1:11434','http://127.0.0.1:11434')),
            ({'ISURVIX_PHOTO_OLLAMA_URL':'http://127.0.0.1:11435'},('http://127.0.0.1:11435','http://127.0.0.1:11435')),
            ({'ISURVIX_OLLAMA_URL':'http://127.0.0.1:11436','ISURVIX_PHOTO_OLLAMA_URL':'http://127.0.0.1:11435'},
             ('http://127.0.0.1:11436','http://127.0.0.1:11435'))]
        for environment,expected in cases:
            with self.subTest(environment=environment):
                # Evaluate actual configuration assignments without importing
                # settings again or touching secrets, media or operational DBs.
                namespace={'os':SimpleNamespace(environ=environment)}
                exec(code,namespace)
                self.assertEqual(tuple(namespace[name] for name in ('OLLAMA_BASE_URL','PHOTO_OLLAMA_BASE_URL')),expected)

    def test_windows_launcher_aligns_text_after_verified_photo_startup(self):
        root=Path(__file__).resolve().parents[2]
        temporary_root=root/'.local'/'test-runs';temporary_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='launcher-selection-',dir=temporary_root) as temporary:
            fixture=Path(temporary);(fixture/'scripts').mkdir()
            (fixture/'scripts'/'Start-PhotoAI.ps1').write_text("param($Model)\n$env:ISURVIX_PHOTO_OLLAMA_URL='http://127.0.0.1:11435'\n")
            harness=fixture/'harness.ps1'
            harness.write_text('''param([string]$RealLauncher,[string]$FixtureRoot)
$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
$tree=[System.Management.Automation.Language.Parser]::ParseFile($RealLauncher,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'Launcher syntax is invalid.' }
$blocks=$tree.FindAll({param($node) $node -is [System.Management.Automation.Language.TryStatementAst] -and $node.Body.Extent.Text.Contains('Start-PhotoAI.ps1')},$true)
if ($blocks.Count -ne 1) { throw 'Find the dedicated local runtime startup block.' }
$projectRoot=$FixtureRoot;$Model='qwen3.5:4b'
$env:ISURVIX_OLLAMA_URL='http://127.0.0.1:11434'
$body=$blocks[0].Body.Extent.Text
. ([scriptblock]::Create($body.Substring(1,$body.Length-2)))
@{text=$env:ISURVIX_OLLAMA_URL;photo=$env:ISURVIX_PHOTO_OLLAMA_URL}|ConvertTo-Json -Compress
''')
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
                '-File',str(harness),'-RealLauncher',str(root/'Start-iSurvix.ps1'),'-FixtureRoot',str(fixture)],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),{'text':'http://127.0.0.1:11435','photo':'http://127.0.0.1:11435'})

    @patch('core.local_ai.ollama')
    def test_qa_runner_missing_error_is_specific_redacted_and_preserves_survey(self,call):
        quality=User.objects.create_user('local_qa')
        quality.profile.role=Profile.Roles.QUALITY_ENGINEER;quality.profile.project=self.project;quality.profile.save()
        self.survey.quality_reviewer=quality;self.survey.save(update_fields=['quality_reviewer'])
        self.client.force_login(quality)
        private='PRIVATE_RUNTIME_PATH_AND_PROMPT'
        body=json.dumps({'error':'error starting llama-server: llama-server binary not found '+private}).encode()
        call.side_effect=[{'models':[{'name':'qwen3.5:4b'}]},HTTPError('http://127.0.0.1:11434/api/chat',500,'Internal server error',{},BytesIO(body))]
        before=(self.survey.answer_data.copy(),self.survey.status,self.survey.section_approvals.copy())
        response=self.post({'question':'Reply with READY only.','checklist_id':self.survey.pk})
        self.assertEqual(response.status_code,503,response.content)
        self.assertEqual(response.json()['code'],'local_runner_unavailable')
        self.assertIn('Start-iSurvix.cmd',response.json()['error'])
        self.assertNotIn(private,response.content.decode())
        self.survey.refresh_from_db()
        self.assertEqual((self.survey.answer_data,self.survey.status,self.survey.section_approvals),before)
