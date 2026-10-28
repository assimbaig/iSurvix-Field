"""Independent tenant-boundary contracts: real records/files and scoped HTTP jobs.

All fixtures are disposable. Native inference, customer records and approvals
are deliberately outside these access tests.
"""
import hashlib
import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import remote_worker_service as bridge, survey_processing as pipeline
from . import test_survey_processing as original_fixture
from .access import accessible_projects
from .models import Checklist, Company, Profile, Project, ProjectMembership
from .survey_processing_models import SurveyDocument, SurveyDrawingSet, SurveyProcessingEvent


@override_settings(SECRET_KEY='independent-company-boundaries',ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentCompanyBoundaryTests(TestCase):
    person=original_fixture.SurveyProcessingTests.person
    request=original_fixture.SurveyProcessingTests.request
    add_photo=original_fixture.SurveyProcessingTests.add_photo

    def setUp(self):
        original_fixture.SurveyProcessingTests.setUp(self)
        self.company_b=Company.objects.create(name='PRIVATE-EMPLOYER-B-729')
        self.project_b=Project.objects.create(name='PRIVATE-PROJECT-B-729',company=self.company_b,
                                              checklist_template=self.template)
        roles=[Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD,Profile.Roles.QUALITY_ENGINEER,
               Profile.Roles.ENGINEER,Profile.Roles.CLIENT]
        self.people_a=dict(zip(roles,[self.admin,self.lead,self.quality,self.engineer,self.customer]))
        self.people_b={role:self.person('independent_b_'+role.lower(),role,self.project_b) for role in roles}
        self.checklist_b=Checklist.objects.create(project=self.project_b,
            user=self.people_b[Profile.Roles.ENGINEER],quality_reviewer=self.people_b[Profile.Roles.QUALITY_ENGINEER],
            site_id='PRIVATE-SITE-B-729',answer_data={'custom':{'contact':'PRIVATE-CONTACT-B-729'}})
        buffer=BytesIO();Image.new('RGB',(60,40),'orange').save(buffer,'PNG');raw=buffer.getvalue()
        self.photo_b=type(self.photo).objects.create(checklist=self.checklist_b,
            uploaded_by=self.people_b[Profile.Roles.ENGINEER],filename='PRIVATE-PHOTO-B-729.png',
            sha256=hashlib.sha256(raw).hexdigest(),metadata={'format':'PNG'})
        self.photo_b.original.save('independent-b.png',ContentFile(raw))
        self.photo_b.preview.save('independent-b-preview.png',ContentFile(raw))
        self.photo.preview.save('independent-a-preview.png',ContentFile(Path(self.photo.original.path).read_bytes()))
        self.doc_a=self.document(self.checklist,self.engineer,b'PRIVATE-DOCUMENT-A-728')
        self.doc_b=self.document(self.checklist_b,self.people_b[Profile.Roles.ENGINEER],b'PRIVATE-DOCUMENT-B-729')
        self.revision_a,_=pipeline.submit(self.request(),self.checklist.pk,True)
        self.revision_b,_=pipeline.submit(SimpleNamespace(user=self.people_b[Profile.Roles.ENGINEER]),self.checklist_b.pk,True)
        self.output_a=self.output(self.revision_a,'a')
        self.output_b=self.output(self.revision_b,'b')

    def document(self,checklist,actor,raw):
        from reportlab.pdfgen import canvas
        stream=BytesIO();page=canvas.Canvas(stream,pagesize=(250,150),pageCompression=0);page.drawString(10,75,raw.decode());page.showPage();page.save();raw=stream.getvalue()
        document=SurveyDocument(checklist=checklist,uploaded_by=actor,filename='private-note.pdf',
            sha256=hashlib.sha256(raw).hexdigest(),content_type='application/pdf',size=len(raw))
        document.original.save('private-note.pdf',ContentFile(raw),save=False);document.save()
        return document

    def output(self,revision,key):
        folder=Path(settings.MEDIA_ROOT)/'independent-outputs'/key;folder.mkdir(parents=True)
        manifest={'sheets':[{}]}
        for kind in ['pdf','dxf','preview','bundle']:
            path=folder/('private-output.'+kind);path.write_bytes(('PRIVATE-OUTPUT-'+key+'-'+kind).encode())
            if kind in {'pdf','bundle'}:manifest[kind]=str(path)
            else:manifest['sheets'][0][kind]=str(path)
        return SurveyDrawingSet.objects.create(revision=revision,edition=1,review_digest='unreleased',geometry={},manifest=manifest)

    def response(self,actor,url,method='get',data=None,**extra):
        client=Client()
        if actor:client.force_login(actor)
        result=getattr(client,method)(url,data or {},**extra)
        body=b''.join(result.streaming_content) if result.streaming else result.content
        result.close()
        return result.status_code,body

    def test_all_company_roles_cannot_read_foreign_records_files_or_job_progress(self):
        urls=[reverse(name,args=[self.checklist_b.pk]) for name in
              ['custom_checklist','photo_workspace','photo_state','survey_processing_state','survey_processing_progress','roadmap_activity']]
        urls += [reverse('photo_evidence',args=[self.checklist_b.pk,self.photo_b.pk,kind]) for kind in ['original','preview']]
        urls += [reverse('survey_processing_document',args=[self.checklist_b.pk,self.doc_b.pk])]
        urls += [reverse('survey_processing_output',args=[self.checklist_b.pk,self.output_b.pk,0,kind]) for kind in ['pdf','dxf','preview','bundle']]
        for role,actor in self.people_a.items():
            for url in urls:
                with self.subTest(role=role,url=url):
                    status,body=self.response(actor,url)
                    self.assertIn(status,(403,404))
                    for token in [b'PRIVATE-SITE-B-729',b'PRIVATE-CONTACT-B-729',b'PRIVATE-OUTPUT-b',b'PRIVATE-DOCUMENT-B']:
                        self.assertNotIn(token,body)

    def test_same_company_positive_controls_deliver_exact_saved_bytes(self):
        urls=[(reverse('photo_evidence',args=[self.checklist.pk,self.photo.pk,'original']),Path(self.photo.original.path).read_bytes()),
              (reverse('photo_evidence',args=[self.checklist.pk,self.photo.pk,'preview']),Path(self.photo.preview.path).read_bytes()),
              (reverse('survey_processing_document',args=[self.checklist.pk,self.doc_a.pk]),Path(self.doc_a.original.path).read_bytes()),
              (reverse('survey_processing_output',args=[self.checklist.pk,self.output_a.pk,0,'pdf']),b'PRIVATE-OUTPUT-a-pdf')]
        for actor in [self.engineer,self.admin,self.lead]:
            for url,expected in urls:
                with self.subTest(actor=actor.pk,url=url):
                    status,body=self.response(actor,url);self.assertEqual(status,200);self.assertEqual(body,expected)

    def test_nested_foreign_photo_document_output_ids_do_not_cross_the_authorized_parent(self):
        urls=[reverse('photo_evidence',args=[self.checklist.pk,self.photo_b.pk,'original']),
              reverse('survey_processing_document',args=[self.checklist.pk,self.doc_b.pk]),
              reverse('survey_processing_output',args=[self.checklist.pk,self.output_b.pk,0,'pdf'])]
        for actor in [self.engineer,self.admin]:
            for url in urls:
                with self.subTest(actor=actor.pk,url=url):self.assertEqual(self.response(actor,url)[0],404)

    def test_task_search_counts_exports_and_foreign_filter_do_not_disclose_other_company(self):
        for role,actor in self.people_a.items():
            if role==Profile.Roles.CLIENT:
                Checklist.objects.filter(pk=self.checklist.pk).update(status=Checklist.Status.FINAL)
                Checklist.objects.filter(pk=self.checklist_b.pk).update(status=Checklist.Status.FINAL)
            for query in [{},{'q':'PRIVATE-SITE-B-729'},{'export':'csv'},
                          {'export':'csv','selected':'C'+str(self.checklist_b.pk)},{'project':self.project_b.pk}]:
                with self.subTest(role=role,query=query):
                    browser=Client();browser.force_login(actor);response=browser.get(reverse('task_explorer'),query)
                    status,body=response.status_code,response.content
                    self.assertIn(status,(200,400))
                    if query.get('q'):
                        self.assertEqual(response.context['total'],0)
                    else:self.assertNotIn(b'PRIVATE-SITE-B-729',body)
                    self.assertNotIn(b'PRIVATE-PROJECT-B-729',body)
                    if query=={'q':'PRIVATE-SITE-B-729'}:self.assertNotIn(b'PRIVATE-CONTACT-B-729',body)
        status,body=self.response(self.admin,reverse('task_explorer'),data={'export':'csv'})
        self.assertEqual(status,200);self.assertIn(self.checklist.site_id.encode(),body)

    def test_foreign_membership_and_primary_pointer_cannot_override_explicit_company(self):
        for actor in self.people_a.values():
            ProjectMembership.objects.create(user=actor,project=self.project_b,is_active=True,legacy_admin_access=True)
            Profile.objects.filter(user=actor).update(project=self.project_b)
            actor.refresh_from_db()
            self.assertNotIn(self.project_b.pk,set(accessible_projects(actor).values_list('pk',flat=True)))
            self.assertIn(self.response(actor,reverse('photo_state',args=[self.checklist_b.pk]))[0],(403,404))

    def test_foreign_mutation_attempts_preserve_revision_records_and_file_hashes(self):
        before=(deepcopy(self.checklist_b.answer_data),self.revision_b.processing_job.status,SurveyProcessingEvent.objects.count(),
                hashlib.sha256(Path(self.photo_b.original.path).read_bytes()).hexdigest())
        urls=[(reverse('survey_processing_action',args=[self.checklist_b.pk]),{'action':'retry','revision_id':self.revision_b.pk}),
              (reverse('checklist_site_information',args=[self.checklist_b.pk]),{'site_id':'ILLEGAL-CROSS-COMPANY'}),
              (reverse('governance_project_client',args=[self.project_b.pk]),{'client_organization':''})]
        for role,actor in self.people_a.items():
            for url,payload in urls:
                with self.subTest(role=role,url=url):self.assertIn(self.response(actor,url,'post',payload)[0],(403,404))
        self.checklist_b.refresh_from_db();self.revision_b.processing_job.refresh_from_db()
        after=(self.checklist_b.answer_data,self.revision_b.processing_job.status,SurveyProcessingEvent.objects.count(),
               hashlib.sha256(Path(self.photo_b.original.path).read_bytes()).hexdigest())
        self.assertEqual(before,after)

    def test_scoped_machine_credentials_claim_only_own_company_and_cannot_read_or_complete_foreign_task(self):
        credential_a,token_a=bridge.provision(self.admin,[self.project.pk])
        credential_b,token_b=bridge.provision(self.people_b[Profile.Roles.ADMIN],[self.project_b.pk])
        identity={'versions':bridge.versions(),'model':'qwen3.5:4b','model_digest':'d'*64}
        claim_a=bridge.claim(credential_a,identity);claim_b=bridge.claim(credential_b,identity)
        self.assertEqual(claim_a['job_id'],self.revision_a.processing_job.pk)
        self.assertEqual(claim_b['job_id'],self.revision_b.processing_job.pk)
        task_a=bridge.next_task(credential_a,claim_a['job_id'],claim_a['lease'])
        task_b=bridge.next_task(credential_b,claim_b['job_id'],claim_b['lease'])
        client=Client(HTTP_AUTHORIZATION='Bearer '+token_a,HTTP_X_WORKER_LEASE=claim_b['lease'])
        urls=[('get',reverse('remote_worker_image',args=[claim_b['job_id'],task_b['task_id']])),
              ('post',reverse('remote_worker_heartbeat',args=[claim_b['job_id']])),
              ('post',reverse('remote_worker_next',args=[claim_b['job_id']])),
              ('post',reverse('remote_worker_complete',args=[claim_b['job_id'],task_b['task_id']]))]
        for method,url in urls:
            with self.subTest(method=method,url=url):
                response=getattr(client,method)(url,{} if method=='get' else json.dumps({'versions':bridge.versions()}),**({} if method=='get' else {'content_type':'application/json'}))
                self.assertIn(response.status_code,(403,404))
        good=Client(HTTP_AUTHORIZATION='Bearer '+token_b,HTTP_X_WORKER_LEASE=claim_b['lease'])
        response=good.get(reverse('remote_worker_image',args=[claim_b['job_id'],task_b['task_id']]))
        self.assertEqual(response.status_code,200);self.assertTrue(b''.join(response.streaming_content));response.close()

    def test_raw_media_and_anonymous_requests_never_bypass_company_delivery(self):
        for actor in [None,self.engineer,self.admin,self.people_b[Profile.Roles.ADMIN]]:
            for name in [self.photo.original.name,self.photo_b.original.name,self.doc_b.original.name]:
                with self.subTest(actor=str(actor),name=name):self.assertEqual(self.response(actor,'/media/'+name)[0],404)
        for url in [reverse('photo_state',args=[self.checklist_b.pk]),
                    reverse('photo_evidence',args=[self.checklist_b.pk,self.photo_b.pk,'original'])]:
            self.assertIn(self.response(None,url)[0],(302,403,404))

    def test_retired_django_admin_routes_do_not_reintroduce_global_model_permission_access(self):
        from django.contrib.auth.models import Permission
        self.admin.is_staff=True;self.admin.save(update_fields=['is_staff'])
        self.admin.user_permissions.add(*Permission.objects.filter(content_type__app_label__in=['core','auth']))
        for path in ['/admin/core/project/','/admin/core/checklist/','/admin/core/checklist/'+str(self.checklist_b.pk)+'/change/','/admin/auth/user/']:
            with self.subTest(path=path):
                status,body=self.response(self.admin,path)
                self.assertIn(status,(200,302))
                self.assertNotIn(b'PRIVATE-SITE-B-729',body)
                self.assertNotIn(b'PRIVATE-PROJECT-B-729',body)
                self.assertEqual(self.response(self.admin,path,'post',{'name':'forged'})[0],410)

    def test_worker_credential_issued_by_company_a_never_follows_reclassified_issuer_into_b(self):
        credential,token=bridge.provision(self.admin,[self.project.pk])
        # Trusted administrative maintenance is simulated, not an API privilege.
        # A pre-existing machine token must retain its original company boundary.
        Profile.objects.filter(user=self.admin).update(company=self.company_b,project=self.project)
        Project.objects.filter(pk=self.project.pk).update(company=self.company_b)
        self.project.refresh_from_db()
        job=self.revision_a.processing_job;job.status='failed';job.save(update_fields=['status'])
        engineer_b=self.people_b[Profile.Roles.ENGINEER]
        ProjectMembership.objects.create(user=engineer_b,project=self.project,is_active=True)
        next_site=Checklist.objects.create(project=self.project,user=engineer_b,
            quality_reviewer=self.people_b[Profile.Roles.QUALITY_ENGINEER],site_id='NEW-PRIVATE-B-730',
            answer_data={'custom':{'contact':'NEW-COMPANY-B-CONTACT'}})
        raw=Path(self.photo_b.original.path).read_bytes()
        photo=type(self.photo).objects.create(checklist=next_site,uploaded_by=engineer_b,filename='new-b.png',
            sha256=hashlib.sha256(raw).hexdigest())
        photo.original.save('new-b.png',ContentFile(raw))
        revision,_=pipeline.submit(SimpleNamespace(user=engineer_b),next_site.pk,True)
        identity={'versions':bridge.versions(),'model':'qwen3.5:4b','model_digest':'d'*64}
        client=Client(HTTP_AUTHORIZATION='Bearer '+token)
        response=client.post(reverse('remote_worker_claim'),json.dumps(identity),content_type='application/json')
        self.assertIn(response.status_code,(200,403))
        if response.status_code==200:self.assertIsNone(response.json()['job'],'An old companyA credential must not receive companyB work after reclassification.')
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status,'queued')

    def test_same_company_released_client_evidence_positive_but_foreign_released_evidence_denied(self):
        Checklist.objects.filter(pk__in=[self.checklist.pk,self.checklist_b.pk]).update(status=Checklist.Status.FINAL)
        own=reverse('photo_evidence',args=[self.checklist.pk,self.photo.pk,'original'])
        foreign=reverse('photo_evidence',args=[self.checklist_b.pk,self.photo_b.pk,'original'])
        status,content=self.response(self.customer,own)
        self.assertEqual(status,200);self.assertEqual(content,Path(self.photo.original.path).read_bytes())
        self.assertEqual(self.response(self.customer,foreign)[0],404)

    def test_private_draft_and_branding_are_scoped_without_hiding_shared_published_standard(self):
        from .models import ChecklistTemplate
        draft=ChecklistTemplate.objects.create(name='PRIVATE-B-DRAFT-739',definition={'title':'Private template','sections':[{'id':'private_section','title':'Private section','fields':[{'id':'private_label','label':'Private label','type':'text'}]}]},
                                              created_by=self.people_b[Profile.Roles.ADMIN],published=False)
        draft.company_logo.save('private-b-company.png',ContentFile(Path(self.photo_b.original.path).read_bytes()))
        private=[reverse('checklist_wizard_edit',args=[draft.pk]),
                 reverse('checklist_wizard_export',args=[draft.pk]),
                 reverse('checklist_template_logo',args=[draft.pk,'company'])]
        for url in private:
            with self.subTest(url=url):
                self.assertEqual(self.response(self.admin,url)[0],404)
                self.assertEqual(self.response(self.people_b[Profile.Roles.ADMIN],url)[0],200)
        self.assertEqual(self.response(self.admin,reverse('checklist_wizard_edit',args=[self.template.pk]))[0],200)

    def test_super_admin_keeps_platform_administration_but_cannot_read_operational_evidence(self):
        actor=User.objects.create_user('independent_platform_operator',is_superuser=True,is_staff=True)
        actor.profile.role=Profile.Roles.SUPER_ADMIN;actor.profile.save()
        status,body=self.response(actor,reverse('governance_home'))
        self.assertEqual(status,200);self.assertIn(self.company_b.name.encode(),body)
        for checklist,photo in [(self.checklist,self.photo),(self.checklist_b,self.photo_b)]:
            for url in [reverse('custom_checklist',args=[checklist.pk]),
                        reverse('photo_evidence',args=[checklist.pk,photo.pk,'original']),
                        reverse('survey_processing_state',args=[checklist.pk])]:
                with self.subTest(url=url):self.assertIn(self.response(actor,url)[0],(403,404))

    def test_published_staff_qualifications_require_same_company_shared_project(self):
        from .work_profile_models import WorkProfile,ProfessionalExperience
        from datetime import date
        own=WorkProfile.objects.create(user=self.engineer,display_name='OWN-ENGINEER-PROFILE-728',published=True)
        foreign=WorkProfile.objects.create(user=self.people_b[Profile.Roles.ENGINEER],display_name='PRIVATE-B-PROFILE-739',published=True)
        for record,label in [(own,'OWN-QUALIFICATION-728'),(foreign,'PRIVATE-B-QUALIFICATION-739')]:
            ProfessionalExperience.objects.create(work_profile=record,organization=label,job_title='Survey Engineer',
                                                  start_date=date(2025,1,1),qualifications=label)
        for actor in [self.customer,self.admin,self.quality]:
            with self.subTest(actor=actor.pk):
                status,body=self.response(actor,reverse('work_profile_detail',args=[self.engineer.pk]))
                self.assertEqual(status,200);self.assertIn(b'OWN-QUALIFICATION-728',body)
                self.assertEqual(self.response(actor,reverse('work_profile_detail',args=[foreign.user_id]))[0],404)
                status,body=self.response(actor,reverse('work_profile_directory'))
                self.assertEqual(status,200);self.assertNotIn(b'PRIVATE-B-PROFILE-739',body)

    def test_project_with_private_template_cannot_transfer_template_visibility_by_reclassification(self):
        from .models import ChecklistTemplate
        private=ChecklistTemplate.objects.create(name='A-PRIVATE-PUBLISHED-740',definition=deepcopy(self.schema),
                                                published=True,created_by=self.admin)
        unused=Project.objects.create(name='A-UNUSED-BUT-TEMPLATE-BOUND',company=self.company,checklist_template=private)
        actor=User.objects.create_user('independent_classification_operator',is_superuser=True,is_staff=True)
        actor.profile.role=Profile.Roles.SUPER_ADMIN;actor.profile.save()
        status,_=self.response(actor,reverse('governance_project_company',args=[unused.pk]),'post',{'company':self.company_b.pk})
        self.assertEqual(status,409,'A project-bound private checklist is retained company content even without activity history.')
        unused.refresh_from_db();self.assertEqual(unused.company_id,self.company.pk)
        self.assertEqual(self.response(self.people_b[Profile.Roles.ADMIN],reverse('checklist_wizard_edit',args=[private.pk]))[0],404)
