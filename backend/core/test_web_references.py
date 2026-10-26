"""Public reference lookup contracts; ordinary tests never use external services."""
import json
import os
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.core.cache import cache
from django.urls import reverse

from . import web_references as service
from . import test_engineer_category_submission_acceptance as fixtures


def response(payload, status=200):
    raw=json.dumps(payload).encode()
    return SimpleNamespace(status_code=status,headers={'Content-Type':'application/json'},
        iter_content=lambda chunk_size:iter([raw]),close=Mock())


class WebReferenceContractTests(SimpleTestCase):
    def setUp(self):cache.clear()

    def test_ws1_rejects_obfuscated_numeric_encoded_and_nonpublic_result_destinations(self):
        blocked=[
            'http://127.1/private','http://2130706433/private','http://0x7f000001/private',
            'http://%31%32%37.0.0.1/private','http://localhost./private',
            'http://127.000.000.001/','http://0177.0.0.1/','http://0x7f.1/',
            'http://[::1]/','http://[::ffff:127.0.0.1]/','http://[::ffff:7f00:1]/',
            'http://[64:ff9b::7f00:1]/','http://[fe80::1%25eth0]/',
            'http://10.0.0.1/','http://192.168.1.1/','http://169.254.169.254/',
            'http://0/','http://0xffffffff/','http://printer.local/',
            'https://camera.lan/','http://device.localhost/','http://home.arpa/',
            'https://equipment.internal/','https://equipment.test/',
            'http://example.org:8000/','https://example.org:80/','http://example.org:443/',
            'https://example.org:/','https://example.org:0443/','https://example.org./',
            'https://example.org\\@127.1/','https://user:pass@example.org/',
            'https://example.org\n/','https://example.org\x7f/',
            'https://ＥＸＡＭＰＬＥ.org/','https://example。org/',
            'http://8.8.8.8/','https://[2606:4700:4700::1111]/']
        for url in blocked:
            with self.subTest(url=url):self.assertIsNone(service.safe_url(url))

    def test_ws1_preserves_normal_public_manufacturer_dns_urls_and_default_ports(self):
        allowed=['https://www.ericsson.com/en/portfolio/networks',
            'https://www.nokia.com:443/networks/','http://www.example.org:80/reference',
            'https://support.example.org/manuals/radio%20unit.pdf?q=equipment#specifications']
        for url in allowed:
            with self.subTest(url=url):self.assertEqual(service.safe_url(url),url)

    @patch.object(service.requests,'get')
    def test_ws1_does_not_reuse_cached_results_from_before_the_url_policy_fix(self,get):
        signature=hashlib.sha256(json.dumps([71,'brave','radio tower']).encode()).hexdigest()
        cache.set('public-reference-result:'+signature,{'results':[{'url':'http://127.1/private'}]},timeout=60)
        get.return_value=response({'web':{'results':[{'title':'Unsafe','url':'http://127.1/private'},
            {'title':'Manufacturer reference','url':'https://www.nokia.com/networks/'}]}})
        with patch.dict(os.environ,{'BRAVE_SEARCH_API_KEY':'synthetic-test-token'}):
            result=service.user_search(71,'radio tower','brave')
        self.assertEqual([row['url'] for row in result['results']],['https://www.nokia.com/networks/'])
        get.assert_called_once()

    @patch.object(service.requests,'get')
    def test_wikipedia_returns_actual_provider_records_as_unverified_references(self, get):
        get.return_value=response({'pages':[{'title':'Radio masts and towers','key':'Radio_masts_and_towers',
            'description':'Tall structures supporting antennas','excerpt':'A <span>radio mast</span> supports antennas.'}]})
        result=service.search('telecommunications tower')
        self.assertEqual(result['provider'],'wikipedia')
        self.assertEqual(result['scope'],'encyclopedia')
        self.assertTrue(result['reference_only'])
        self.assertFalse(result['verified'])
        self.assertEqual(result['results'][0]['title'],'Radio masts and towers')
        self.assertEqual(result['results'][0]['url'],'https://en.wikipedia.org/wiki/Radio_masts_and_towers')
        self.assertEqual(result['results'][0]['snippet'],'A radio mast supports antennas.')
        self.assertTrue(result['fetched_at'])
        self.assertEqual(get.call_args.kwargs['params'],{'q':'telecommunications tower','limit':5})
        self.assertFalse(get.call_args.kwargs['allow_redirects'])

    @patch.object(service.requests,'get')
    def test_invalid_keywords_or_provider_never_reach_provider(self,get):
        for query in ['', 'x'*161,'tower\nmodel','tower\x00model',' '.join(['word']*26),None,{}]:
            with self.subTest(query=query), self.assertRaises(service.ReferenceError):service.search(query)
        with self.assertRaises(service.ReferenceError):service.search('tower','unknown')
        get.assert_not_called()

    @patch.object(service.requests,'get')
    def test_brave_requires_owner_key_and_returns_only_safe_plaintext_web_references(self,get):
        with patch.dict(os.environ,{'BRAVE_SEARCH_API_KEY':''}):
            with self.assertRaises(service.ReferenceError) as caught:service.search('radio tower','brave')
        self.assertEqual(caught.exception.code,'not_configured')
        get.assert_not_called()
        get.return_value=response({'web':{'results':[
            {'title':'<b>Tower</b><script>hidden()</script> guide','url':'https://example.org/tower',
                'description':'Public <em>reference</em> &amp; details'},
            {'title':'Injected','url':'javascript:alert(1)'},
            {'title':'Credentials','url':'https://user:pass@example.org/'},
            {'title':'Private','url':'http://127.0.0.1/private'}]}})
        with patch.dict(os.environ,{'BRAVE_SEARCH_API_KEY':'synthetic-test-token'}):
            result=service.search('radio tower','brave')
        self.assertEqual(result['scope'],'web')
        self.assertEqual(result['results'],[{'title':'Tower guide','url':'https://example.org/tower',
            'snippet':'Public reference & details','source':'example.org'}])
        self.assertEqual(get.call_args.kwargs['headers']['X-Subscription-Token'],'synthetic-test-token')

    @patch.object(service.requests,'get')
    def test_timeout_redirect_malformed_and_oversized_responses_are_honest_errors(self,get):
        get.side_effect=service.requests.exceptions.Timeout()
        with self.assertRaises(service.ReferenceError) as caught:service.search('tower')
        self.assertEqual(caught.exception.code,'provider_timeout')
        get.side_effect=None
        for payload,status,code in [({},302,'provider_unavailable'),({'pages':{}},200,'invalid_provider_response')]:
            get.return_value=response(payload,status)
            with self.subTest(code=code),self.assertRaises(service.ReferenceError) as caught:service.search('tower')
            self.assertEqual(caught.exception.code,code)
        for raw,code in [(b'not json','invalid_provider_response'),(b'x'*(service.MAX_BYTES+1),'provider_response_too_large')]:
            get.return_value=SimpleNamespace(status_code=200,iter_content=lambda chunk_size:iter([raw]),close=Mock())
            with self.subTest(code=code),self.assertRaises(service.ReferenceError) as caught:service.search('tower')
            self.assertEqual(caught.exception.code,code)
            get.return_value.close.assert_called_once()

    @patch.object(service.requests,'get')
    def test_empty_results_are_not_invented_and_duplicate_searches_are_cached_and_throttled(self,get):
        get.return_value=response({'pages':[]})
        first=service.user_search(71,'tower','wikipedia')
        self.assertEqual(first['results'],[])
        self.assertEqual(service.user_search(71,'tower','wikipedia'),first)
        self.assertEqual(get.call_count,1)
        for index in range(9):service.user_search(71,'tower '+str(index),'wikipedia')
        with self.assertRaises(service.ReferenceError) as caught:service.user_search(71,'different equipment','wikipedia')
        self.assertEqual(caught.exception.code,'rate_limited')
        self.assertEqual(get.call_count,10)
        self.assertEqual(service.user_search(71,'tower','wikipedia'),first)


@override_settings(SECRET_KEY='isolated-web-reference-tests',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class WebReferenceAccessTests(TestCase):
    person=fixtures.EngineerCategorySubmissionAcceptanceTests.person
    add_photo=fixtures.EngineerCategorySubmissionAcceptanceTests.add_photo
    post=fixtures.EngineerCategorySubmissionAcceptanceTests.post
    state=fixtures.EngineerCategorySubmissionAcceptanceTests.state
    raw=fixtures.EngineerCategorySubmissionAcceptanceTests.raw
    upload=fixtures.EngineerCategorySubmissionAcceptanceTests.upload
    submit=fixtures.EngineerCategorySubmissionAcceptanceTests.submit
    assert_submitted=fixtures.EngineerCategorySubmissionAcceptanceTests.assert_submitted

    def setUp(self):
        cache.clear()
        fixtures.EngineerCategorySubmissionAcceptanceTests.setUp(self)
        self.upload('Civil')
        result,_=self.submit()
        self.assertEqual(result.status_code,201,result.content)
        self.revision=self.assert_submitted()
        self.payload={'revision_id':self.revision.pk,'source_digest':self.revision.digest,
            'query':'telecommunications tower','provider':'wikipedia'}
        self.url=reverse('photo_capture_web_references',args=[self.checklist.pk])

    @patch.object(service.requests,'get')
    def test_assigned_qa_can_search_only_explicit_keywords_without_writes(self,get):
        get.return_value=response({'pages':[{'title':'Radio masts and towers','key':'Radio_masts_and_towers',
            'description':'Tall structures supporting antennas'}]})
        self.client.force_login(self.quality)
        before=(self.checklist.answer_data,self.checklist.section_approvals,
            self.revision.processing_events.count(),self.revision.source_analyses.count())
        result=self.client.post(self.url,json.dumps(self.payload),content_type='application/json')
        self.assertEqual(result.status_code,200,result.content)
        self.assertTrue(result.json()['reference_only'])
        self.assertEqual(get.call_args.kwargs['params'],{'q':'telecommunications tower','limit':5})
        self.checklist.refresh_from_db()
        self.assertEqual((self.checklist.answer_data,self.checklist.section_approvals,
            self.revision.processing_events.count(),self.revision.source_analyses.count()),before)

    @patch.object(service.requests,'get')
    def test_anonymous_wrong_role_and_wrong_revision_cannot_search(self,get):
        self.client.logout()
        self.assertEqual(self.client.post(self.url,json.dumps(self.payload),content_type='application/json').status_code,302)
        for actor in [self.engineer,self.lead,self.customer,self.admin]:
            self.client.force_login(actor)
            result=self.client.post(self.url,json.dumps(self.payload),content_type='application/json')
            self.assertIn(result.status_code,(403,404),result.content)
        self.client.force_login(self.quality)
        for change in [{'revision_id':self.revision.pk+1},{'source_digest':'0'*64}]:
            result=self.client.post(self.url,json.dumps({**self.payload,**change}),content_type='application/json')
            self.assertEqual(result.status_code,409,result.content)
        self.quality.is_active=False
        self.quality.save(update_fields=['is_active'])
        self.assertIn(self.client.post(self.url,json.dumps(self.payload),content_type='application/json').status_code,(302,404))
        get.assert_not_called()

    @patch.object(service.requests,'get')
    def test_csrf_post_only_and_request_size_guards_prevent_provider_calls(self,get):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.quality)
        self.assertEqual(client.post(self.url,json.dumps(self.payload),content_type='application/json').status_code,403)
        self.client.force_login(self.quality)
        self.assertEqual(self.client.get(self.url).status_code,405)
        self.assertEqual(self.client.post(self.url,'x'*4097,content_type='application/json').status_code,413)
        for content in ['bad json',json.dumps({**self.payload,'context':'private site context'}),json.dumps({**self.payload,'query':'tower\nmodel'})]:
            self.assertEqual(self.client.post(self.url,content,content_type='application/json').status_code,400)
        get.assert_not_called()

    @patch.object(service.requests,'get')
    def test_unassigned_qa_and_revoked_project_membership_cannot_search(self,get):
        from .models import Company,Profile,Project,ProjectMembership
        other=self.person('unassigned-reference-qa',Profile.Roles.QUALITY_ENGINEER)
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url,json.dumps(self.payload),content_type='application/json').status_code,404)
        foreign_project=Project.objects.create(name='Foreign reference project',
            company=Company.objects.create(name='Foreign reference company'))
        foreign=self.person('foreign-reference-qa',Profile.Roles.QUALITY_ENGINEER,foreign_project)
        self.client.force_login(foreign)
        self.assertEqual(self.client.post(self.url,json.dumps(self.payload),content_type='application/json').status_code,404)
        self.client.force_login(self.quality)
        ProjectMembership.objects.update_or_create(user=self.quality,project=self.project,
            defaults={'is_active':False})
        self.assertEqual(self.client.post(self.url,json.dumps(self.payload),content_type='application/json').status_code,404)
        get.assert_not_called()

    @patch.object(service.requests,'get')
    def test_ws1_actual_qa_endpoint_filters_each_reproduced_destination_but_retains_manufacturer_links(self,get):
        self.client.force_login(self.quality)
        blocked=['http://127.1/private','http://2130706433/private','http://0x7f000001/private',
            'http://%31%32%37.0.0.1/private','http://localhost./private']
        with patch.dict(os.environ,{'BRAVE_SEARCH_API_KEY':'synthetic-test-token'}):
            for index,url in enumerate(blocked):
                with self.subTest(url=url):
                    get.return_value=response({'web':{'results':[{'title':'Unsafe destination','url':url},
                        {'title':'Equipment reference','url':'https://www.ericsson.com/en/portfolio/networks'}]}})
                    result=self.client.post(self.url,json.dumps({**self.payload,'provider':'brave',
                        'query':'radio equipment reference '+str(index)}),content_type='application/json')
                    self.assertEqual(result.status_code,200,result.content)
                    self.assertEqual([row['url'] for row in result.json()['results']],
                        ['https://www.ericsson.com/en/portfolio/networks'])
                    self.assertTrue(result.json()['reference_only'])
        self.assertEqual(get.call_count,5)
        self.assertEqual(self.revision.source_analyses.count(),0)
