"""Representative real ORM data in an isolated database, never operational records."""
from pathlib import Path
import os,sys,json,time,statistics
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.local/survey-progress-benchmark';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'backend'));os.environ['DJANGO_SETTINGS_MODULE']='checklist.settings_local'
from django.conf import settings
settings.DATABASES['default']['NAME']=OUT/'performance.sqlite3'
settings.MEDIA_ROOT=OUT/'performance-media';settings.MEDIA_ROOT.mkdir(exist_ok=True)
settings.LOGGING['handlers']['file']['filename']=OUT/'performance-app.log'
settings.PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
import django;django.setup()
from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import Client
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse,NoReverseMatch
from core.models import Company,Project,ChecklistTemplate,Checklist,Profile,PhotoEvidence
from core import survey_processing as pipeline
from core.survey_processing_models import SurveyProcessingRevision,SurveyProcessingJob,SurveyProcessingResult,SurveySourceAnalysis,SurveyProcessingEvent,SurveyDrawingSet
if '--seed' in sys.argv:
    call_command('migrate',verbosity=0)
    assert not Checklist.objects.exists(),'Do not overwrite a prior performance fixture'
    company=Company.objects.create(name='SYNTHETIC performance company')
    user=User.objects.create_user('synthetic_performance_engineer')
    schema={'title':'Synthetic200-field performance checklist','sections':[{'id':'observations','title':'Synthetic observed records','fields':[{'id':f'field_{i:03d}','label':f'Synthetic recorded item {i}','type':'text'} for i in range(200)]}]}
    template=ChecklistTemplate.objects.create(name='SYNTHETIC performance checklist',definition=schema,published=True,checklist_required=True,client_left_name='',client_right_name='')
    project=Project.objects.create(name='SYNTHETIC performance project',company=company,checklist_template=template)
    user.profile.company=company;user.profile.project=project;user.profile.role=Profile.Roles.ENGINEER;user.profile.save()
    checklist=Checklist.objects.create(project=project,user=user,site_id='SYN-PERF-200')
    PhotoEvidence.objects.bulk_create([PhotoEvidence(checklist=checklist,uploaded_by=user,filename=f'synthetic-evidence-{i:03d}.jpg',group='Civil',sha256=pipeline.digest({'photo':i}),original=f'performance/{i}.jpg',preview=f'performance/{i}-preview.jpg',metadata={'width':1200,'height':800,'format':'JPEG'}) for i in range(200)])
    photos=list(checklist.photo_evidence.order_by('pk'))
    for number in range(20):
        checklist.answer_data={'custom':{'fixture_revision':number}}
        checklist.save(update_fields=['answer_data','updated_at'])
        snapshot=pipeline.freeze_data(checklist)
        revision=SurveyProcessingRevision.objects.create(checklist=checklist,number=number+1,digest=pipeline.digest(snapshot),snapshot=snapshot,submitted_by=user)
        SurveyProcessingJob.objects.create(revision=revision,status='preparing_drawings' if number==19 else 'ready_for_review',model='synthetic-performance-only',completed=200,total=200)
        items=[{'id':f'field_{i:03d}','section':'Synthetic observed records','label':f'Synthetic recorded item {i}','value':'SYNTHETIC recorded value '+str(i),'proposed_answer':'SYNTHETIC recorded value '+str(i),'status':'Needs review','sources':[{'source_id':f'photo:{photos[i].pk}','reference':'original'}],'confidence':'medium','accepted':False,'conflict':False,'unit':'','reason':'Synthetic performance data only'} for i in range(200)]
        findings=[{'field_hint':f'field_{i%200:03d}','category':'equipment','value':'Synthetic equipment observation '+str(i),'unit':'','source_id':f'photo:{photos[i%200].pk}','reference':'original','finding_key':f'photo:{photos[i%200].pk}:finding:{i//200+1}','verification_status':'needs_review','confidence':'medium','notes':'Synthetic traceable performance observation, no engineering approval.'} for i in range(400)]
        payload={'checklist_items':items,'findings':findings,'missing':[],'conflicts':[],'suggested_items':[],'drawing_records':[]}
        SurveyProcessingResult.objects.create(revision=revision,payload=payload,digest=pipeline.digest(payload))
        source_records=[]
        for photo in photos:
            entry={'source_id':f'photo:{photo.pk}','reference':'original','preview_file':'synthetic-not-requested.jpg','findings':[f for f in findings if f['source_id']==f'photo:{photo.pk}']}
            source_records.append(SurveySourceAnalysis(revision=revision,source_id=f'photo:{photo.pk}',payload=entry,digest=pipeline.digest(entry)))
        SurveySourceAnalysis.objects.bulk_create(source_records)
        SurveyProcessingEvent.objects.bulk_create([SurveyProcessingEvent(revision=revision,actor=user,action='synthetic_benchmark_note',reason='Synthetic retained review history; '*12,payload={}) for _ in range(20)])
        for edition in (1,2):
            SurveyDrawingSet.objects.create(revision=revision,edition=edition,released=False,review_digest=pipeline.digest({'edition':edition}),geometry={'sheets':[]},manifest={'sheets':[{'number':f'SV-{i:03d}','title':'Synthetic retained output','scale':'Not to Scale'} for i in range(4)]})
    print('Seeded20 revisions,200 photos,200 fields,8000 findings,4000 source checkpoints,400 events and40 retained draft editions in isolatedDB.')
    raise SystemExit
if '--migrate' in sys.argv:call_command('migrate',verbosity=0)
user=User.objects.get(username='synthetic_performance_engineer');checklist=Checklist.objects.get(site_id='SYN-PERF-200')
client=Client(HTTP_HOST='127.0.0.1');client.force_login(user)
phase=sys.argv[sys.argv.index('--phase')+1] if '--phase' in sys.argv else 'baseline'
paths={'state':reverse('survey_processing_state',args=[checklist.pk]),'compact':reverse('survey_processing_state',args=[checklist.pk])+'?compact=1'}
try:paths['progress']=reverse('survey_processing_progress',args=[checklist.pk])
except NoReverseMatch:pass
receipt={'phase':phase,'synthetic':True,'fixture':{'revisions':20,'photos':200,'fields':200,'findings':8000,'sources':4000,'events':400,'drawing_editions':40},'requests':{}}
for label,url in paths.items():
    samples=[]
    for _ in range(5):
        with CaptureQueriesContext(connection) as queries:
            start=time.perf_counter();response=client.get(url);elapsed=(time.perf_counter()-start)*1000
        assert response.status_code==200,(url,response.status_code,response.content[:300])
        samples.append({'ms':round(elapsed,3),'queries':len(queries),'bytes':len(response.content)})
    receipt['requests'][label]={'url':url,'samples':samples,'median_ms':round(statistics.median(s['ms'] for s in samples),3),'median_queries':statistics.median(s['queries'] for s in samples),'bytes':samples[-1]['bytes']}
(OUT/f'performance-{phase}.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))

