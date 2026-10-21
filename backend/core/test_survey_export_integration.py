"""Isolated synthetic workflow with real evidence parsing and real PDF/DXF exports.

The complete happy path mocks only native Ollama transport. The recovery case
additionally injects a single interruption after mapping. No live user, record,
photo, model call or approval is involved. FINAL task status below is an explicit
test fixture, not a claim of approval by a real reviewer.
"""
import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import zipfile
from copy import deepcopy

import ezdxf
import pymupdf
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import survey_processing as pipeline
from . import test_survey_processing as fixtures
from .models import Checklist, Company, Profile, Project
from .survey_processing_models import SurveyProcessingEvent, SurveyDrawingSet
from .survey_drawings import _digest


@override_settings(SECRET_KEY='synthetic-real-export-only', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SurveyExportIntegrationTests(TestCase):
    setUp=fixtures.SurveyProcessingTests.setUp
    person=fixtures.SurveyProcessingTests.person
    request=fixtures.SurveyProcessingTests.request
    add_photo=fixtures.SurveyProcessingTests.add_photo
    pristine=fixtures.SurveyProcessingTests.pristine

    def fake_native_transport(self, path, payload=None, *, base_url=None):
        if path=='/api/tags':
            return {'models':[{'name':settings.OLLAMA_MODEL,'digest':'synthetic-vision-model'}]}
        if path=='/api/show':
            return {'capabilities':['completion','vision'],'digest':'synthetic-vision-model'}
        self.assertEqual(path,'/api/chat')
        content=payload['messages'][-1]['content']
        if content.startswith('UNTRUSTED_MAPPING_DATA_JSON'):
            self.assertNotIn('images',payload['messages'][-1])
            data=json.loads(content.split('\n',1)[1].rsplit('\n',1)[0])
            fields={field['id'] for field in data['approved_candidate_catalog']}
            bindings=[];unassigned=[]
            for finding in data['observations']:
                if finding.get('field_hint') in fields and finding.get('value') is not None:
                    bindings.append({'finding_key':finding['finding_key'],'field_id':finding['field_hint'],
                        'reason':'Synthetic text-only binding to the already extracted supported property.'})
                else:
                    unassigned.append(finding['finding_key'])
            return {'message':{'content':json.dumps({'bindings':bindings,'unassigned':unassigned})},'done_reason':'stop'}
        images=payload['messages'][-1]['images']
        self.assertEqual(len(images),1,'Each real model request must contain a bounded image batch.')
        with Image.open(BytesIO(base64.b64decode(images[0],validate=True))) as image:
            self.assertLessEqual(max(image.size),1800)
            self.assertEqual(image.size,(60,40))
        self.assertIn('UNTRUSTED_EVIDENCE_JSON',payload['messages'][-1]['content'])
        self.assertIn('never instructions',payload['messages'][0]['content'])
        self.native_images.append(images[0])
        number=len(self.native_images)
        observations=[
            {'field_hint':'manufacturer','category':'equipment','component':'cabinet',
             'value':f'Unverified source manufacturer {number}','unit':'','basis':'recorded',
             'evidence_quote':f'Synthetic manufacturer {number}','confidence':'high','notes':''},
            {'field_hint':'tower_height','category':'measurement','component':'tower',
             'value':29+number,'unit':'m','basis':'recorded',
             'evidence_quote':f'{29+number} m on synthetic source','confidence':'medium','notes':''},
            {'field_hint':'','category':'measurement','component':'Uncalibrated photograph dimension',
             'value':999,'unit':'m','basis':'visible','evidence_quote':'','confidence':'high',
             'notes':'Synthetic adversarial unsupported dimension must be withheld.'},
        ]
        return {'message':{'content':json.dumps({'findings':observations,'missing':[],
            'conflicts':[],'suggested_items':[]})},'done_reason':'stop'}

    def process_real(self):
        self.native_images=[]
        original=self.pristine()
        originals={p.pk:Path(p.original.path).read_bytes() for p in (self.photo,self.photo2)}
        self.client.force_login(self.engineer)
        response=self.client.post(reverse('survey_processing_action',args=[self.checklist.pk]),
            {'action':'submit','uploads_finished':'true'})
        self.assertEqual(response.status_code,201,response.content)
        revision=self.checklist.processing_revisions.get(pk=response.json()['revision_id'])
        with patch('core.local_ai.ollama',side_effect=self.fake_native_transport), \
             patch('core.photo_service.assistant_ollama',side_effect=self.fake_native_transport):
            self.assertTrue(pipeline.process_next())
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status,'ready_for_review',revision.processing_job.error)
        self.assertEqual(len(self.native_images),2)
        self.assertNotEqual(self.native_images[0],self.native_images[1])
        self.assertEqual(self.pristine(),original)
        for photo in (self.photo,self.photo2):
            self.assertEqual(originals[photo.pk],Path(photo.original.path).read_bytes())
        return revision

    def post_review(self, actor, revision, decision, **data):
        self.client.force_login(actor)
        values={'action':'review','revision_id':revision.pk,'decision':decision}
        for key,value in data.items():
            values[key]=json.dumps(value) if key in {'finding_ids','corrections','drawing_records'} else value
        response=self.client.post(reverse('survey_processing_action',args=[self.checklist.pk]),values)
        self.assertEqual(response.status_code,200,response.content)
        return response

    def correct_and_complete(self, revision):
        self.post_review(self.engineer,revision,'accept',finding_ids=['site_id','contact'])
        self.post_review(self.engineer,revision,'correct',finding_ids=['manufacturer'],
            corrections={'manufacturer':'Synthetic reviewed manufacturer'},reason='Isolated synthetic reconciliation; source label selected by test Engineer.')
        self.post_review(self.engineer,revision,'correct',finding_ids=['tower_height'],
            corrections={'tower_height':'32'},reason='Isolated synthetic confirmed record; conflicting photo records superseded.')
        self.post_review(self.engineer,revision,'reject',finding_ids=['cabinet_condition'],
            reason='Synthetic missing condition evidence explicitly retained as Missing, not compliant.')
        record={'source_id':f'photo:{self.photo.pk}','verified':True,'unit':'m','sheet':'site_layout',
            'kind':'equipment','equipment_type':'cabinet','tag':'SYN-CAB-01',
            'x':1,'y':1,'width':.8,'height':1.2}
        self.post_review(self.engineer,revision,'geometry',drawing_records=[record],
            reason='Isolated synthetic measured geometry verified by the assigned test Engineer.')
        self.post_review(self.engineer,revision,'engineer_complete',
            reason='Isolated synthetic review disposition: conflicting labels corrected; unsupported dimension and missing condition retained as gaps.')
        return record

    def assert_export_identity(self, asset, *, released):
        self.assertEqual(asset.geometry,json.loads(Path(asset.manifest['geometry']).read_text()))
        geometry=dict(asset.geometry);digest=geometry.pop('digest')
        self.assertEqual(digest,_digest(geometry))
        self.assertEqual(digest,asset.manifest['geometry_digest'])
        self.assertEqual(geometry['released'],released)
        self.assertEqual(geometry['date'],asset.revision.created_at.date().isoformat())
        with pymupdf.open(asset.manifest['pdf']) as pdf:
            self.assertIn(digest,pdf.metadata['subject'])
            self.assertEqual(len(pdf),len(geometry['sheets']))
            for index,sheet in enumerate(geometry['sheets']):
                dxf=ezdxf.readfile(asset.manifest['sheets'][index]['dxf'])
                self.assertFalse(dxf.audit().has_errors)
                dictionary=dxf.rootdict['ISURVIX_GEOMETRY']
                self.assertEqual(dictionary.tags[0].value,digest)
                entities=list(dxf.modelspace())
                self.assertEqual(len(entities),len(sheet['entities']))
                for entity,record in zip(entities,sheet['entities']):
                    self.assertEqual(entity.get_xdata('ISURVIX')[1].value,_digest(record))
                page_text=pdf[index].get_text()
                self.assertIn('RELEASED' if released else 'DRAFT - FOR REVIEW',page_text)
                if released:
                    for actor in (self.engineer,self.quality,self.lead):
                        self.assertIn(actor.get_username(),page_text)
        with zipfile.ZipFile(asset.manifest['bundle']) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn('survey-drawings.pdf',archive.namelist())
            self.assertIn('geometry.json',archive.namelist())
            self.assertNotIn('survey-drawings.zip',archive.namelist())
            self.assertEqual(json.loads(archive.read('geometry.json')),asset.geometry)

    def test_real_worker_review_release_and_private_exports_keep_source_revision(self):
        self.checklist.answer_data['legacy_notes']={'preserve':'Existing unrelated survey information'}
        self.checklist.answer_data['custom']['unrelated_existing_value']='Preserve existing field data'
        self.checklist.save(update_fields=['answer_data'])
        original_answers=deepcopy(self.checklist.answer_data)
        submit_url=reverse('custom_checklist_submit',args=[self.checklist.pk])
        self.client.force_login(self.engineer)
        before_ai=self.client.post(submit_url)
        self.assertEqual(before_ai.status_code,302)
        self.checklist.refresh_from_db();self.assertEqual(self.checklist.status,Checklist.Status.DRAFT)
        revision=self.process_real()
        original_snapshot=deepcopy(revision.snapshot)
        before_review=self.client.post(submit_url)
        self.assertEqual(before_review.status_code,302)
        self.checklist.refresh_from_db();self.assertEqual(self.checklist.status,Checklist.Status.DRAFT)
        payload=pipeline.reviewed_payload(revision)
        by_id={item['id']:item for item in payload['checklist_items']}
        self.assertTrue(by_id['manufacturer']['conflict'])
        self.assertTrue(by_id['tower_height']['conflict'])
        self.assertEqual(len(by_id['manufacturer']['sources']),2)
        self.assertTrue(payload['missing'])
        draft=revision.drawing_sets.get()
        original_draft=Path(draft.manifest['pdf']).read_bytes()
        self.assert_export_identity(draft,released=False)
        self.assertFalse(any(e['layer'] in {'EQUIPMENT','MEASURED','ROUTES','DIMENSIONS'}
            for sheet in draft.geometry['sheets'] for e in sheet['entities']))
        self.assertTrue(any(f.get('value') is None for f in payload['findings'] if f.get('component')=='Uncalibrated photograph dimension'))
        self.correct_and_complete(revision)
        self.checklist.refresh_from_db();revision.refresh_from_db()
        self.assertEqual(revision.snapshot,original_snapshot)
        self.assertEqual(revision.snapshot['answers'],original_answers)
        self.assertEqual(self.checklist.answer_data['custom']['manufacturer'],'Synthetic reviewed manufacturer')
        self.assertEqual(self.checklist.answer_data['custom']['tower_height'],'32')
        self.assertEqual(self.checklist.answer_data['custom']['contact'],original_answers['custom']['contact'])
        self.assertEqual(self.checklist.answer_data['custom']['unrelated_existing_value'],original_answers['custom']['unrelated_existing_value'])
        self.assertEqual(self.checklist.answer_data['legacy_notes'],original_answers['legacy_notes'])
        self.assertTrue(pipeline.current(revision))
        self.assertTrue(revision.processing_events.filter(action='applied',payload__source_digest=pipeline.digest(pipeline.freeze_data(self.checklist))).exists())
        self.client.force_login(self.engineer)
        saved_page=self.client.get(reverse('custom_checklist',args=[self.checklist.pk]))
        self.assertEqual(saved_page.status_code,200)
        fields={field['id']:field for section in saved_page.context['sections'] for field in section['fields']}
        self.assertEqual(fields['manufacturer']['value'],'Synthetic reviewed manufacturer')
        self.assertEqual(fields['tower_height']['value'],'32')
        self.assertTrue(fields['manufacturer']['linked_photos'])
        submitted=self.client.post(submit_url)
        self.assertEqual(submitted.status_code,302)
        self.checklist.refresh_from_db();self.assertEqual(self.checklist.status,Checklist.Status.SUBMITTED)
        self.assertEqual(self.checklist.answer_data['custom']['manufacturer'],'Synthetic reviewed manufacturer')
        self.assertTrue(pipeline.current(revision))
        self.post_review(self.quality,revision,'technical_approve',reason='Isolated synthetic independent QA review.')
        # Explicit existing-task FINAL fixture in this disposable test database only.
        self.checklist.status=Checklist.Status.FINAL
        self.checklist.save(update_fields=['status'])
        self.post_review(self.lead,revision,'release',reason='Isolated synthetic output release fixture.')
        released=revision.drawing_sets.get(released=True)
        self.assert_export_identity(released,released=True)
        self.assertGreater(released.edition,draft.edition)
        self.assertEqual(Path(draft.manifest['pdf']).read_bytes(),original_draft)
        self.assertEqual(revision.drawing_sets.count(),3)
        values=str(released.geometry)
        self.assertIn('Synthetic reviewed manufacturer',values)
        self.assertNotIn('Unverified source manufacturer',values)
        self.assertIn('32',values)
        measured=next(sheet for sheet in released.geometry['sheets'] if sheet['key']=='site_layout')
        self.assertGreater(measured['measured_record_count'],0)
        self.assertTrue(all(e['sources'] for e in measured['entities'] if e['layer']=='EQUIPMENT'))
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.answer_data['custom']['manufacturer'],'Synthetic reviewed manufacturer')
        self.assertEqual(self.checklist.answer_data['custom']['tower_height'],'32')
        self.assertEqual(revision.snapshot,original_snapshot)
        self.assertTrue(pipeline.current(revision))
        self.assertEqual(self.checklist.section_approvals,{})
        state_url=reverse('survey_processing_state',args=[self.checklist.pk])
        self.client.force_login(self.engineer)
        state=self.client.get(state_url)
        self.assertEqual(state.status_code,200,state.content)
        self.assertTrue(state.json()['active']['engineer_complete'])
        self.assertTrue(state.json()['active']['technical_approved'])
        source=next(item for item in state.json()['active']['checklist_items'] if item['id']=='manufacturer')['sources'][0]
        self.assertIn('url',source);self.assertIn('thumbnail_url',source)
        for role in (self.engineer,self.quality,self.lead,self.customer):
            self.client.force_login(role)
            for kind,key in [('pdf','pdf'),('dxf','dxf'),('preview','preview'),('bundle','bundle')]:
                url=reverse('survey_processing_output',args=[self.checklist.pk,released.pk,0,kind])
                response=self.client.get(url)
                self.assertEqual(response.status_code,200,(role.get_username(),kind))
                file=released.manifest[key] if kind in ('pdf','bundle') else released.manifest['sheets'][0][key]
                self.assertEqual(b''.join(response.streaming_content),Path(file).read_bytes())
                self.assertIn('private',response['Cache-Control'])
                self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.client.force_login(self.customer)
        client_state=self.client.get(state_url).json()['active']
        self.assertEqual(client_state['findings'],[])
        self.assertTrue(client_state['drawings'])
        self.assertTrue(all(sheet['released'] for sheet in client_state['drawings']))
        draft_url=reverse('survey_processing_output',args=[self.checklist.pk,draft.pk,0,'pdf'])
        self.assertEqual(self.client.get(draft_url).status_code,404)
        other=Project.objects.create(name='Synthetic separate export project',company=Company.objects.create(name='Synthetic separate export company'),checklist_template=self.template)
        outsider=self.person('export_outsider',Profile.Roles.ENGINEER,other)
        self.client.force_login(outsider)
        released_url=reverse('survey_processing_output',args=[self.checklist.pk,released.pk,0,'bundle'])
        self.assertEqual(self.client.get(released_url).status_code,404)
        self.client.logout();self.assertEqual(self.client.get(released_url).status_code,302)
        self.client.force_login(self.engineer)
        corrupt=Path(released.manifest['pdf']);corrupt.write_bytes(corrupt.read_bytes()+b'SYNTHETIC TAMPER TEST')
        response=self.client.get(reverse('survey_processing_output',args=[self.checklist.pk,released.pk,0,'pdf']))
        self.assertEqual(response.status_code,409)

    def test_false_verified_and_foreign_sources_cannot_create_measured_geometry(self):
        revision=self.process_real()
        for value in (False,0,1,'true',None):
            with self.subTest(verified=value),self.assertRaises(ValidationError):
                pipeline.review(self.request(),self.checklist.pk,revision.pk,'geometry',reason='Synthetic invalid record',
                    drawing_records=[{'source_id':f'photo:{self.photo.pk}','verified':value,'unit':'m',
                        'kind':'equipment','x':0,'y':0,'width':1,'height':1}])
        for source in ('photo:foreign','photo:999999','mapping:0001'):
            with self.assertRaises(ValidationError):
                pipeline.review(self.request(),self.checklist.pk,revision.pk,'geometry',reason='Synthetic foreign record',
                    drawing_records=[{'source_id':source,'verified':True,'unit':'m',
                        'kind':'equipment','x':0,'y':0,'width':1,'height':1}])
        self.assertEqual(revision.drawing_sets.count(),1)
        self.assertFalse(SurveyProcessingEvent.objects.filter(revision=revision,action='geometry').exists())

    def test_non_numeric_polyline_points_cannot_become_confirmed_measurements(self):
        revision=self.process_real()
        for coordinate in (True,False,'2',float('nan'),float('inf')):
            with self.subTest(coordinate=coordinate),self.assertRaises(ValidationError):
                pipeline.review(self.request(),self.checklist.pk,revision.pk,'geometry',reason='Synthetic invalid point type',
                    drawing_records=[{'source_id':f'photo:{self.photo.pk}','verified':True,'unit':'m',
                        'kind':'line','sheet':'site_layout','points':[[coordinate,0],[1,1]]}])
        self.assertEqual(revision.drawing_sets.count(),1)
        self.assertFalse(SurveyProcessingEvent.objects.filter(revision=revision,action='geometry').exists())

    def test_retry_recovers_saved_text_mapping_without_reanalysing_images(self):
        self.native_images=[]
        revision,_=pipeline.submit(self.request(),self.checklist.pk,True)
        with patch('core.local_ai.ollama',side_effect=self.fake_native_transport), \
             patch('core.photo_service.assistant_ollama',side_effect=self.fake_native_transport), \
             patch('core.survey_processing.prepare_checklist',side_effect=RuntimeError('Synthetic interruption after mapping cache')):
            self.assertTrue(pipeline.process_next())
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status,'failed')
        self.assertEqual(len(self.native_images),2)
        self.assertTrue(revision.source_analyses.filter(source_id__startswith='mapping:').exists())
        self.assertFalse(hasattr(revision,'processing_result'))
        pipeline.retry(self.request(),self.checklist.pk,revision.pk)
        with patch('core.local_ai.ollama',side_effect=self.fake_native_transport), \
             patch('core.photo_service.assistant_ollama',side_effect=self.fake_native_transport):
            self.assertTrue(pipeline.process_next())
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status,'ready_for_review',revision.processing_job.error)
        self.assertEqual(len(self.native_images),2,'Saved source analyses must be reused after restart/retry.')
        self.assertEqual(revision.drawing_sets.count(),1)
        self.assert_export_identity(revision.drawing_sets.get(),released=False)
