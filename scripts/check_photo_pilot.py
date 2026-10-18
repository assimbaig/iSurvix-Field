"""Opt-in real local vision pilot; disposable DB/media under project .local only."""
import json
import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ['DJANGO_SETTINGS_MODULE']='checklist.settings_local'
import django
django.setup()
from django.conf import settings
from django.test import Client, override_settings
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.db import connections
from PIL import Image, ImageDraw
from core.models import Profile,Project,ChecklistTemplate,Checklist,PhotoJob,PhotoDraft
from core.photo_queue import process_next
from core.photo_service import verify_vision


def main():
    verify_vision(settings.OLLAMA_MODEL)
    connections.close_all()
    with tempfile.TemporaryDirectory(prefix='synthetic-pilot-',dir=ROOT/'.local') as temporary:
        database=dict(settings.DATABASES['default'])
        database['NAME']=str(Path(temporary)/'test.sqlite3')
        with override_settings(DATABASES={'default':database},MEDIA_ROOT=str(Path(temporary)/'media'),ALLOWED_HOSTS=['testserver']):
            try:
                connections['default'].close()
                connections['default'].settings_dict.update(database)
                call_command('migrate',verbosity=0,interactive=False)
                user=User.objects.create_user('synthetic_pilot')
                project=Project.objects.create(name='Disposable synthetic pilot')
                user.profile.project=project
                user.profile.role=Profile.Roles.ENGINEER
                user.profile.save()
                schema={'title':'Synthetic image pilot','sections':[{'id':'visual','title':'Visual evidence','fields':[{'id':'visible_shapes','label':'Describe the visible colored shapes and positions','type':'text'}]}]}
                template=ChecklistTemplate.objects.create(name='Disposable pilot',published=True,definition=schema)
                project.checklist_template=template
                project.save()
                survey=Checklist.objects.create(project=project,user=user,site_id='SYNTHETIC-ONLY')
                image=Image.new('RGB',(640,480),'white')
                draw=ImageDraw.Draw(image)
                draw.rectangle((40,100,250,310),fill='red')
                draw.ellipse((370,100,580,310),fill='blue')
                raw=BytesIO()
                image.save(raw,format='PNG')
                client=Client()
                client.force_login(user)
                base=f'/local/photos/{survey.pk}/'
                response=client.post(base+'upload/',{'files':[SimpleUploadedFile('synthetic-shapes.png',raw.getvalue(),content_type='image/png')]})
                assert response.status_code==201,response.content
                photo=response.json()['photos'][0]['id']
                original=client.get(base+f'evidence/{photo}/original/')
                assert b''.join(original.streaming_content)==raw.getvalue()
                original.close()
                response=client.post(base+'enqueue/',json.dumps({'photo_ids':[photo]}),content_type='application/json')
                assert response.status_code==201,response.content
                job=PhotoJob.objects.get(pk=response.json()['id'])
                assert process_next()
                job.refresh_from_db()
                assert job.status=='completed',(job.status,job.error)
                state=client.get(base+'state/').json()
                survey.refresh_from_db()
                assert survey.answer_data=={} and not survey.section_approvals
                draft=PhotoDraft.objects.filter(job=job,value__isnull=False).first()
                assert draft is not None,'Model returned insufficient evidence; no acceptable draft.'
                response=client.post(base+f'drafts/{draft.pk}/accept/',data='{}',content_type='application/json')
                assert response.status_code==200,response.content
                survey.refresh_from_db()
                assert survey.answer_data['custom'][draft.field_id]==draft.value
                assert survey.status==Checklist.Status.DRAFT and not survey.section_approvals
                report=client.get(base+'report/')
                assert report.status_code==200 and report.json()['drafts'][0]['status']=='accepted'
                print(json.dumps({'result':'PASS','model':settings.OLLAMA_MODEL,'job_status':job.status,'drafts':len(state['drafts']),'explicit_acceptance':True,'original_preserved':True,'automatic_approval':False,'data':'disposable synthetic only'}))
                connections.close_all()
            finally:
                connections.close_all()

if __name__=='__main__':
    main()
