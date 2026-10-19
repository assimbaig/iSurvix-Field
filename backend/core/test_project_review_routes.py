"""Isolated HTTP acceptance for Admin projects and frozen one-step review routes."""
from django.test import TestCase,Client,override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Company,Project,Profile,IndustryCatalog,ProjectMembership

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProjectReviewRouteHttpTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='Synthetic route tenant')
        self.foreign_company=Company.objects.create(name='Foreign route tenant')
        self.industry=IndustryCatalog.objects.get(code='telecom')
        self.admin=self.person('project_admin',Profile.Roles.ADMIN)
        self.superuser=self.person('platform_admin',Profile.Roles.SUPER_ADMIN,superuser=True)
        self.engineer=self.person('engineer',Profile.Roles.ENGINEER)
        self.quality=self.person('quality',Profile.Roles.QUALITY_ENGINEER)
        self.lead=self.person('lead',Profile.Roles.TEAM_LEAD)
        self.customer=self.person('client',Profile.Roles.CLIENT)
        self.client.force_login(self.admin)
    def person(self,name,role,superuser=False):
        actor=User.objects.create_user('route_http_'+name,is_superuser=superuser)
        actor.profile.role=role;actor.profile.company=self.company
        if role==Profile.Roles.ADMIN:actor.profile.admin_industry=self.industry
        actor.profile.save();return actor
    def create(self,layers=3,**extra):
        return self.client.post(reverse('governance_projects'),{'name':'New scoped project','description':'Synthetic route scope',
            'review_layers':layers,**extra})
    def test_admin_creates_first_project_with_server_bound_authority_and_membership(self):
        self.assertFalse(ProjectMembership.objects.filter(user=self.admin).exists())
        response=self.create();self.assertEqual(response.status_code,302,response.content)
        project=Project.objects.get(name='New scoped project')
        self.assertEqual((project.company_id,project.industry,project.administrator_id,project.review_layers),
                         (self.company.pk,'telecom',self.admin.pk,3))
        self.assertTrue(ProjectMembership.objects.filter(user=self.admin,project=project,is_active=True).exists())
    def test_super_and_field_roles_cannot_create_projects(self):
        for actor in [self.superuser,self.engineer,self.quality,self.lead,self.customer]:
            self.client.force_login(actor);self.assertEqual(self.create().status_code,403)
        self.assertFalse(Project.objects.exists())
    def test_project_scope_forgery_never_creates_foreign_tenant_or_industry(self):
        response=self.create(company=self.foreign_company.pk,industry='construction',administrator=self.superuser.pk)
        self.assertIn(response.status_code,[302,400,403])
        self.assertFalse(Project.objects.filter(company=self.foreign_company).exists())
        self.assertFalse(Project.objects.filter(industry='construction').exists())
        self.assertFalse(Project.objects.filter(administrator=self.superuser).exists())
    def test_layer_count_is_required_and_only_three_or_four(self):
        for layers in ['',0,2,5,'four']:
            self.assertEqual(self.create(layers).status_code,400)
        self.assertFalse(Project.objects.exists())
        self.assertEqual(self.create(4).status_code,302)
        self.assertEqual(Project.objects.get().review_layers,4)
    def test_project_creation_csrf_and_locked_or_unbound_admin_denied(self):
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.admin)
        self.assertEqual(secure.post(reverse('governance_projects'),{'name':'Missing CSRF','review_layers':3}).status_code,403)
        self.admin.profile.is_locked=True;self.admin.profile.save()
        self.assertEqual(self.create().status_code,403)
        self.admin.profile.is_locked=False;self.admin.profile.admin_industry=None
        self.admin.profile.admin_industry_pending=True;self.admin.profile.save()
        self.assertIn(self.create().status_code,[400,403])
        self.assertFalse(Project.objects.exists())

    def prepared(self,layers=4):
        from .models import ChecklistTemplate,Checklist,WorkflowTemplateQualification
        from .roadmap_service import definition_digest
        from .independent_workflow import configure_policy
        schema={'title':'Scoped route checklist','sections':[{'id':'general','title':'General','fields':[
            {'id':'condition','label':'Condition','type':'text','required':True}]}]}
        template=ChecklistTemplate.objects.create(name='Qualified route source',definition=schema,published=True)
        project=Project.objects.create(name='Routed project',company=self.company,industry='telecom',
            administrator=self.admin,review_layers=layers,checklist_template=template)
        for actor in [self.admin,self.engineer,self.quality,self.lead,self.customer]:
            actor.profile.project=project;actor.profile.save()
            ProjectMembership.objects.create(user=actor,project=project,is_primary=True)
        c=Checklist.objects.create(project=project,user=self.engineer,site_id='HTTP-ROUTE',
            governance_mode='independent',schema_snapshot=schema,checklist_template=template,
            answer_data={'custom':{'condition':'Original human observation'}},
            coordinate_reference={'source':'Synthetic surveyed coordinates','crs':'EPSG:4326'})
        WorkflowTemplateQualification.objects.create(project=project,template=template,workflow_type=c.workflow_type,
            definition_digest=definition_digest(schema),criteria_reference='Synthetic criteria',
            inspection_method='Synthetic visual inspection',reviewed_by=self.lead,reason='Fixture qualification')
        configure_policy(self.admin,c,self.quality,self.lead,'Explicit frozen route reviewers',
            customer_required=layers==4,customer_reviewer=self.customer if layers==4 else None,enable_route=True)
        return c
    def submit(self,c):
        self.client.force_login(self.engineer)
        response=self.client.post(reverse('custom_checklist_submit',args=[c.pk]))
        self.assertEqual(response.status_code,302,response.content);c.refresh_from_db()
    def action(self,c,actor,action,reason='Recorded clarification reason',token=None):
        from .review_route_service import route_context
        c.refresh_from_db();self.client.force_login(actor)
        context=route_context(actor,c)
        response=self.client.post(reverse('review_route_action',args=[c.pk]),
            {'action':action,'reason':reason,'expected_token':token or context['token']})
        return response
    def stage(self,c,stage,mode='review'):
        from .review_route_service import route_for
        route=route_for(c);self.assertEqual((route.stage,route.mode),(stage,mode));return route
    def test_four_layer_return_chain_and_new_engineer_revision_preserve_original(self):
        c=self.prepared();self.submit(c)
        route=self.stage(c,'quality_engineer');original=route.revision;original_snapshot=original.snapshot
        for actor in [self.quality,self.lead]:self.assertEqual(self.action(c,actor,'approve').status_code,302)
        self.stage(c,'client')
        self.assertEqual(self.action(c,self.customer,'reject','Client requests clarification').status_code,302)
        self.stage(c,'team_lead','clarification')
        self.assertEqual(self.action(c,self.lead,'return','QA must clarify evidence').status_code,302)
        self.stage(c,'quality_engineer','clarification')
        self.assertEqual(self.action(c,self.quality,'return','Engineer must correct observation').status_code,302)
        self.stage(c,'engineer','clarification')
        self.client.force_login(self.engineer)
        response=self.client.post(reverse('custom_checklist_save',args=[c.pk]),
            data='{"answers":{"condition":"Corrected human observation"}}',content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.submit(c);route=self.stage(c,'quality_engineer')
        self.assertNotEqual(route.revision_id,original.pk);self.assertEqual(route.revision.parent_id,original.pk)
        for actor in [self.quality,self.lead,self.customer]:self.assertEqual(self.action(c,actor,'approve').status_code,302)
        self.stage(c,'closed');original.refresh_from_db();self.assertEqual(original.snapshot,original_snapshot)
    def test_clarification_moves_only_one_stage_forward_without_editing_evidence(self):
        c=self.prepared();self.submit(c)
        for actor in [self.quality,self.lead]:self.assertEqual(self.action(c,actor,'approve').status_code,302)
        before=c.answer_data
        self.assertEqual(self.action(c,self.customer,'reject').status_code,302)
        self.assertEqual(self.action(c,self.lead,'return').status_code,302)
        self.assertEqual(self.action(c,self.quality,'clarify').status_code,302)
        self.stage(c,'team_lead')
        self.assertEqual(self.action(c,self.lead,'approve').status_code,302)
        self.stage(c,'client');c.refresh_from_db();self.assertEqual(c.answer_data,before)
    def test_three_layers_close_without_client_and_project_change_does_not_rewrite_route(self):
        c=self.prepared(3);self.submit(c)
        Project.objects.filter(pk=c.project_id).update(review_layers=4)
        for actor in [self.quality,self.lead]:self.assertEqual(self.action(c,actor,'approve').status_code,302)
        route=self.stage(c,'closed');self.assertEqual(route.layer_count,3)
        self.assertNotIn('client',route.reviewers)
        self.assertIn(self.action(c,self.customer,'approve').status_code,[403,404])
    def test_route_wrong_actor_stale_reason_csrf_and_revoked_access_fail_without_events(self):
        from .review_route_service import route_context,route_for
        c=self.prepared();self.submit(c);token=route_context(self.quality,c)['token']
        for actor in [self.admin,self.superuser,self.engineer,self.lead,self.customer]:
            self.assertIn(self.action(c,actor,'approve').status_code,[403,404])
        self.assertIn(self.action(c,self.quality,'reject','').status_code,[400,409])
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.quality)
        self.assertEqual(strict.post(reverse('review_route_action',args=[c.pk]),{'action':'approve','expected_token':token}).status_code,403)
        self.assertEqual(self.action(c,self.quality,'approve').status_code,302)
        count=route_for(c).events.count()
        self.assertIn(self.action(c,self.lead,'approve',token=token).status_code,[400,409])
        ProjectMembership.objects.filter(user=self.lead,project_id=c.project_id).update(is_active=False)
        self.assertIn(self.action(c,self.lead,'approve').status_code,[403,404])
        self.assertEqual(route_for(c).events.count(),count)

    def test_old_client_share_does_not_expose_current_engineer_correction_or_new_revision(self):
        c=self.prepared();self.submit(c)
        for actor in [self.quality,self.lead]:self.assertEqual(self.action(c,actor,'approve').status_code,302)
        from .review_route_service import route_for
        shared=route_for(c).revision
        self.assertEqual(self.action(c,self.customer,'reject').status_code,302)
        self.assertEqual(self.action(c,self.lead,'return').status_code,302)
        self.assertEqual(self.action(c,self.quality,'return').status_code,302)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse('custom_checklist',args=[c.pk])).status_code,404)
        response=self.client.get(reverse('roadmap_revision_export',args=[c.pk,shared.pk]))
        self.assertEqual(response.status_code,200,response.content)
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(reverse('custom_checklist_save',args=[c.pk]),
            data='{"answers":{"condition":"Private unshared correction"}}',content_type='application/json').status_code,200)
        self.submit(c);new=route_for(c).revision
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse('roadmap_revision_export',args=[c.pk,new.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('custom_checklist',args=[c.pk])).status_code,404)
        old=self.client.get(reverse('roadmap_revision_export',args=[c.pk,shared.pk]))
        self.assertEqual(old.status_code,200);self.assertNotIn(b'Private unshared correction',old.content)

    def test_company_industry_admin_invitation_bootstraps_first_project_without_existing_project(self):
        from urllib.parse import urlsplit
        from .models import ProjectInvitation
        self.client.force_login(self.superuser)
        response=self.client.post(reverse('governance_invite'),{'email':'newboundadmin@example.test',
            'role':Profile.Roles.ADMIN,'company':self.company.pk,'admin_industry':self.industry.pk})
        self.assertEqual(response.status_code,200,response.content)
        invitation=ProjectInvitation.objects.get(email='newboundadmin@example.test')
        self.assertIsNone(invitation.project_id)
        self.assertEqual(invitation.company_id,self.company.pk)
        accept=urlsplit(response.context['invite_url']).path
        browser=Client()
        response=browser.post(accept,{'username':'bootstrap_bound_admin','email':'newboundadmin@example.test',
            'password1':'Synthetic-bootstrap-pass-918!','password2':'Synthetic-bootstrap-pass-918!'})
        self.assertEqual(response.status_code,302,response.content)
        replay=browser.post(accept,{'username':'bootstrap_replay_admin','email':'newboundadmin@example.test',
            'password1':'Synthetic-bootstrap-pass-918!','password2':'Synthetic-bootstrap-pass-918!'})
        self.assertEqual(replay.status_code,404)
        self.assertFalse(User.objects.filter(username='bootstrap_replay_admin').exists())
        actor=User.objects.get(username='bootstrap_bound_admin')
        self.assertIsNone(actor.profile.project_id)
        self.assertEqual((actor.profile.role,actor.profile.company_id,actor.profile.admin_industry_id),
                         (Profile.Roles.ADMIN,self.company.pk,self.industry.pk))
        self.assertFalse(ProjectMembership.objects.filter(user=actor).exists())
        browser.force_login(actor)
        response=browser.post(reverse('governance_projects'),{'name':'First bootstrap project','review_layers':3})
        self.assertEqual(response.status_code,302,response.content)
        project=Project.objects.get(name='First bootstrap project')
        self.assertEqual((project.company_id,project.industry,project.administrator_id),
                         (self.company.pk,'telecom',actor.pk))
        self.assertTrue(ProjectMembership.objects.filter(user=actor,project=project,is_active=True).exists())

    def test_projectless_invites_require_company_industry_and_admin_role(self):
        from .models import ProjectInvitation
        self.client.force_login(self.superuser)
        payload={'email':'bootstrap_invalid@example.test','role':Profile.Roles.ADMIN,
                 'company':self.company.pk,'admin_industry':self.industry.pk}
        for missing in ['company','admin_industry']:
            data=dict(payload);data.pop(missing)
            self.assertIn(self.client.post(reverse('governance_invite'),data).status_code,[400,403])
        for role in [Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT]:
            self.assertIn(self.client.post(reverse('governance_invite'),{**payload,'role':role}).status_code,[400,403])
        self.assertFalse(ProjectInvitation.objects.filter(email=payload['email']).exists())

    def test_assignment_cannot_override_three_layer_policy_or_use_legacy_shortcut(self):
        from .models import Checklist
        from .review_route_service import route_for
        c=self.prepared(3);self.client.force_login(self.admin)
        payload={'project':c.project_id,'engineer':self.engineer.pk,'l2_reviewer':self.quality.pk,
            'l3_approver':self.lead.pk,'site_id':'ASSIGNED-THREE','latitude':'24','longitude':'46',
            'coordinate_source':'Surveyed coordinates','coordinate_crs':'EPSG:4326',
            'description':'Synthetic task','governance_mode':'legacy'}
        self.assertEqual(self.client.post(reverse('governance_assign'),{**payload,'customer_reviewer':self.customer.pk}).status_code,400)
        self.assertEqual(self.client.post(reverse('governance_assign'),{**payload,'client_review_required':'required'}).status_code,400)
        response=self.client.post(reverse('governance_assign'),payload)
        self.assertEqual(response.status_code,302,response.content)
        assigned=Checklist.objects.get(site_id='ASSIGNED-THREE')
        self.assertEqual(assigned.governance_mode,'independent');self.assertEqual(route_for(assigned).layer_count,3)

    def test_four_layer_assignment_requires_scoped_named_client(self):
        from .models import Checklist
        from .review_route_service import route_for
        c=self.prepared(4);self.client.force_login(self.admin)
        payload={'project':c.project_id,'engineer':self.engineer.pk,'l2_reviewer':self.quality.pk,
            'l3_approver':self.lead.pk,'site_id':'ASSIGNED-FOUR','latitude':'24','longitude':'46',
            'coordinate_source':'Surveyed coordinates','coordinate_crs':'EPSG:4326','description':'Synthetic task'}
        self.assertEqual(self.client.post(reverse('governance_assign'),payload).status_code,400)
        self.assertEqual(self.client.post(reverse('governance_assign'),{**payload,'client_review_required':'not_required',
            'customer_reviewer':self.customer.pk}).status_code,400)
        self.assertFalse(Checklist.objects.filter(site_id='ASSIGNED-FOUR').exists())
        response=self.client.post(reverse('governance_assign'),{**payload,'customer_reviewer':self.customer.pk})
        self.assertEqual(response.status_code,302,response.content)
        route=route_for(Checklist.objects.get(site_id='ASSIGNED-FOUR'))
        self.assertEqual(route.layer_count,4);self.assertEqual(route.reviewers['client'],self.customer.pk)


    def test_revoked_projectless_admin_invitation_cannot_be_accepted(self):
        from urllib.parse import urlsplit
        from .models import ProjectInvitation
        self.client.force_login(self.superuser)
        response=self.client.post(reverse('governance_invite'),{'email':'revokedbootstrap@example.test',
            'role':Profile.Roles.ADMIN,'company':self.company.pk,'admin_industry':self.industry.pk})
        self.assertEqual(response.status_code,200,response.content)
        path=urlsplit(response.context['invite_url']).path
        invitation=ProjectInvitation.objects.get(email='revokedbootstrap@example.test')
        self.assertEqual(self.client.post(reverse('governance_revoke_invite',args=[invitation.pk])).status_code,302)
        anonymous=Client();self.assertEqual(anonymous.get(path).status_code,404)
        response=anonymous.post(path,{'username':'revoked_bootstrap_admin','email':'revokedbootstrap@example.test',
            'password1':'Synthetic-bootstrap-pass-918!','password2':'Synthetic-bootstrap-pass-918!'})
        self.assertEqual(response.status_code,404)
        self.assertFalse(User.objects.filter(username='revoked_bootstrap_admin').exists())

    def test_same_company_nonowner_admin_membership_cannot_read_or_mutate_project(self):
        from .access import accessible_projects
        from .models import Checklist,ChecklistTemplate,PhotoEvidence
        c=self.prepared(4);owner_project=c.project
        peer=self.person('same_company_nonowner',Profile.Roles.ADMIN)
        own=Project.objects.create(name='Other Admin visible project',company=self.company,industry='telecom',administrator=peer)
        peer.profile.project=owner_project;peer.profile.save()
        ProjectMembership.objects.create(user=peer,project=owner_project,is_primary=True)
        ProjectMembership.objects.create(user=peer,project=own,is_primary=False)
        photo=PhotoEvidence.objects.create(checklist=c,filename='OWNER-PRIVATE-SOURCE.png',sha256='a'*64)
        self.assertEqual(set(accessible_projects(peer).values_list('pk',flat=True)),{own.pk})
        self.client.force_login(peer)
        for name,args in [('custom_checklist',[c.pk]),('photo_state',[c.pk]),('photo_workspace',[c.pk]),
                          ('roadmap_activity',[c.pk]),('custom_checklist_download',[c.pk]),
                          ('photo_evidence',[c.pk,photo.pk,'original']),('checklist_template_edit',[c.checklist_template_id])]:
            self.assertIn(self.client.get(reverse(name,args=args)).status_code,[403,404],name)
        for name in ['governance_home','task_explorer']:
            page=self.client.get(reverse(name));self.assertEqual(page.status_code,200)
            self.assertNotContains(page,'HTTP-ROUTE');self.assertNotContains(page,'Routed project')
        invalid=self.client.get(reverse('task_explorer'),{'project':owner_project.pk})
        self.assertEqual(invalid.status_code,200)
        self.assertIn('project',invalid.context['form'].errors)
        self.assertNotContains(invalid,'HTTP-ROUTE')
        self.assertEqual(self.client.get(reverse('task_explorer'),{'project':owner_project.pk,'export':'csv'}).status_code,400)
        before=c.answer_data;count=Checklist.objects.count()
        self.assertIn(self.client.post(reverse('governance_invite'),{'email':'foreignowner@example.test',
            'project':owner_project.pk,'role':Profile.Roles.ENGINEER}).status_code,[400,403,404])
        self.assertIn(self.client.post(reverse('governance_assign'),{'project':owner_project.pk,
            'engineer':self.engineer.pk,'site_id':'FORGED-OWNER','latitude':24,'longitude':46,
            'description':'Forbidden assignment','l2_reviewer':self.quality.pk,'l3_approver':self.lead.pk,
            'customer_reviewer':self.customer.pk}).status_code,[400,403,404])
        self.assertIn(self.client.post(reverse('custom_checklist_save',args=[c.pk]),
            '{"answers":{"condition":"Foreign admin tamper"}}',content_type='application/json').status_code,[403,404])
        self.assertIn(self.client.post(reverse('custom_checklist_review',args=[c.pk]),{'decision':'approve'}).status_code,[403,404])
        c.refresh_from_db();self.assertEqual(c.answer_data,before);self.assertEqual(Checklist.objects.count(),count)
        self.assertFalse(ChecklistTemplate.objects.filter(name='Foreign admin tamper').exists())

    def test_super_owner_transfer_preserves_history_but_removes_old_admin_access(self):
        from .access import accessible_projects
        from .models import GovernanceAudit
        c=self.prepared(3);project=c.project
        replacement=self.person('replacement_owner',Profile.Roles.ADMIN)
        before=c.answer_data;history=c.review_history;schema=c.schema_snapshot
        self.client.force_login(self.superuser)
        response=self.client.post(reverse('governance_project_admin',args=[project.pk]),{'administrator':replacement.pk})
        self.assertEqual(response.status_code,302,response.content)
        project.refresh_from_db();self.assertEqual(project.administrator_id,replacement.pk)
        self.assertTrue(ProjectMembership.objects.filter(user=self.admin,project=project,is_active=True).exists())
        self.assertFalse(accessible_projects(self.admin).filter(pk=project.pk).exists())
        self.assertTrue(accessible_projects(replacement).filter(pk=project.pk).exists())
        self.client.force_login(self.admin)
        self.assertIn(self.client.get(reverse('custom_checklist',args=[c.pk])).status_code,[403,404])
        self.client.force_login(replacement)
        self.assertEqual(self.client.get(reverse('custom_checklist',args=[c.pk])).status_code,200)
        c.refresh_from_db();self.assertEqual((c.answer_data,c.review_history,c.schema_snapshot),(before,history,schema))
        self.assertTrue(GovernanceAudit.objects.filter(project=project,action='project_administrator_assigned').exists())
