"""Shared header consistency does not confer any role or project capability."""
from html.parser import HTMLParser
from types import SimpleNamespace
from urllib.parse import parse_qs,urlsplit

from django.template.loader import render_to_string
from django.test import SimpleTestCase,TestCase,override_settings
from django.urls import reverse

from .models import Profile
from . import test_role_designs as fixtures


class HeaderLinks(HTMLParser):
    def __init__(self,html):
        super().__init__(convert_charrefs=True)
        self.inside=False;self.details=0;self.current=None;self.links=[]
        self.feed(html)
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='nav' and values.get('aria-label')=='Primary navigation':self.inside=True
        if not self.inside:return
        if tag=='details':self.details+=1
        if tag=='a':self.current={'href':values.get('href'),'active':values.get('aria-current'),
            'details':self.details,'text':''}
    def handle_data(self,data):
        if self.current:self.current['text']+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.current:
            self.current['text']=' '.join(self.current['text'].split())
            self.links.append(self.current);self.current=None
        if tag=='details' and self.inside:self.details=max(0,self.details-1)
        if tag=='nav' and self.inside:self.inside=False


@override_settings(ROOT_URLCONF='checklist.urls_local')
class SharedHeaderContractTests(SimpleTestCase):
    def nav(self,role='QUALITY_ENGINEER',**context):
        values={'role_design':{'role':role},'selected_project_id':'17','selected_industry':'telecom',
            'can_administer':role=='ADMIN',**context}
        return HeaderLinks(render_to_string('dashboards/_primary_navigation.html',values)).links

    def test_quality_has_same_five_direct_links_with_or_without_workspace_flag(self):
        for quick in [True,False]:
            with self.subTest(quick=quick):
                links=self.nav(qa_quick_review=quick)
                self.assertEqual([l['text'] for l in links],['My reviews','Projects & sites','Overview','Review activity','Reports'])
                self.assertTrue(all(l['details']==0 for l in links))
                for link in links:self.assertEqual(parse_qs(urlsplit(link['href']).query)['project'],['17'])

    def test_quality_highlights_only_the_actual_primary_location(self):
        for active,label in [('tasks','My reviews'),('projects','Projects & sites'),('my_work','Overview'),
            ('reviews','Review activity'),('reports','Reports'),('profile',None),('',None)]:
            with self.subTest(active=active):
                selected=[l['text'] for l in self.nav(active_view=active) if l['active']=='page']
                self.assertEqual(selected,[label] if label else [])
        self.assertEqual([l['text'] for l in self.nav(checklist=SimpleNamespace(project=SimpleNamespace(industry='telecom')))
            if l['active']=='page'],['My reviews'])

    def test_existing_role_link_sets_are_preserved_without_quality_capabilities(self):
        expected={'ENGINEER':['My tasks'],
            'ADMIN':['Tasks','Overview','Your projects','Review queue','Reports','Administration','Checklists'],
            'TEAM_LEAD':['Tasks','Overview','Projects & sites','Review queue','Reports'],
            'CLIENT':['Tasks','Overview','Projects & sites','Review queue','Reports'],
            'SUPER_ADMIN':['Dashboard','Industries','Clients','Projects','Sites','Checklist Wizard']}
        for role,labels in expected.items():
            with self.subTest(role=role):self.assertEqual([l['text'] for l in self.nav(role=role)],labels)

    def test_engineer_task_record_keeps_my_tasks_active(self):
        links=self.nav(role='ENGINEER',checklist=SimpleNamespace(project=SimpleNamespace(industry='telecom')))
        self.assertEqual([l['text'] for l in links if l['active']=='page'],['My tasks'])


@override_settings(SECRET_KEY='isolated-shared-navigation',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedHeaderPageTests(TestCase):
    setUp=fixtures.RoleDesignTests.setUp

    def test_actual_quality_pages_share_header_order_and_project_scope(self):
        self.client.force_login(self.users[Profile.Roles.QUALITY_ENGINEER])
        locations=[(reverse('task_explorer'),'tasks','My reviews'),
            (reverse('governance_home'),'projects','Projects & sites'),
            (reverse('governance_home'),'my_work','Overview'),
            (reverse('governance_home'),'reviews','Review activity'),
            (reverse('governance_home'),'reports','Reports'),
            (reverse('photo_workspace',args=[self.survey.pk]),None,'My reviews'),
            (reverse('work_profile'),None,None)]
        for url,view,active in locations:
            params={'project':str(self.project.pk)}
            if view and view!='tasks':params['view']=view
            with self.subTest(url=url,view=view):
                result=self.client.get(url,params,follow=True)
                self.assertEqual(result.status_code,200,result.content)
                links=HeaderLinks(result.content.decode()).links
                self.assertEqual([l['text'] for l in links],['My reviews','Projects & sites','Overview','Review activity','Reports'])
                self.assertTrue(all(l['details']==0 for l in links))
                self.assertEqual([l['text'] for l in links if l['active']=='page'],[active] if active else [])

    def test_all_roles_keep_one_header_on_home_and_profile(self):
        for role,user in self.users.items():
            self.client.force_login(user)
            responses=[self.client.get(reverse('governance_home'),follow=True),self.client.get(reverse('work_profile'))]
            with self.subTest(role=role):
                for result in responses:
                    self.assertEqual(result.status_code,200,result.content)
                    html=result.content.decode()
                    self.assertEqual(html.count('id="role-navigation"'),1)
                    self.assertLess(html.index('id="role-navigation"'),html.index('</header>'))
                self.assertEqual([l['text'] for l in HeaderLinks(responses[0].content.decode()).links],
                    [l['text'] for l in HeaderLinks(responses[1].content.decode()).links])
                self.assertEqual([l['text'] for l in HeaderLinks(responses[1].content.decode()).links
                    if l['active']=='page'],[])
