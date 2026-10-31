"""Independent customer candidate preservation and authenticated offline HTTP.

Docker calls are controlled here; actual Linux/Compose and physical LAN require
their separate rehearsals. No operational records or external network are used.
"""
from contextlib import closing
import base64
import hashlib
from html.parser import HTMLParser
import json
from io import BytesIO
from pathlib import Path
import sqlite3
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from . import test_customer_package as fixture_helpers
from .models import Company, IndustryCatalog, Profile


class IndependentCustomerCandidateTests(SimpleTestCase):
    def setUp(self):
        fixture=fixture_helpers.CustomerPackageTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture=fixture
        self.customer=fixture.customer
        self.path=fixture.path

    def prepare(self):
        return self.fixture.prepare()

    def test_prepare_preserves_package_bytes_and_never_copies_private_credentials(self):
        package=self.fixture.bundle()
        before={name:self.customer._digest(path) for name,path in self.customer._files(package).items()}
        secret,tls=self.fixture.private_inputs()
        value=secret.read_text()
        result=self.customer.prepare_runtime(package,self.path/'runtime',host='customer.example.test',
            lan_ip='192.168.20.10',secret_file=secret,tls_directory=tls,acknowledge_draft=True)
        after={name:self.customer._digest(path) for name,path in self.customer._files(package).items()}
        self.assertEqual(before,after)
        for target in (package,self.path/'runtime'):
            for name,path in self.customer._files(target).items():
                self.assertNotIn(value.encode(),path.read_bytes(),name)
        self.assertFalse(result['deployment_performed'])
        self.assertFalse(result['database_created'])
        self.assertFalse((self.path/'runtime/data/database.sqlite3').exists())

    def test_prepare_refuses_existing_runtime_without_touching_its_records(self):
        package=self.fixture.bundle();secret,tls=self.fixture.private_inputs()
        runtime=self.path/'runtime';runtime.mkdir()
        sentinel=runtime/'database.sqlite3';sentinel.write_bytes(b'preserve existing customer bytes')
        with self.assertRaises(ValueError):
            self.customer.prepare_runtime(package,runtime,host='customer.example.test',
                lan_ip='192.168.20.10',secret_file=secret,tls_directory=tls,acknowledge_draft=True)
        self.assertEqual(sentinel.read_bytes(),b'preserve existing customer bytes')
        self.assertEqual(list(runtime.iterdir()),[sentinel])

    def test_trusted_manifest_digest_rejects_rewritten_content_and_inventory(self):
        package=self.fixture.bundle()
        manifest=package/'manifest.json'
        trusted=hashlib.sha256(manifest.read_bytes()).hexdigest()
        data=json.loads(manifest.read_text())
        image=package/'images/server-images.tar';image.write_bytes(b'replaced image bytes')
        data['files']['images/server-images.tar']=self.customer._digest(image)
        manifest.write_text(json.dumps(data))
        with self.assertRaisesMessage(ValueError,'independently trusted digest'):
            self.customer.verify_package(package,expected_manifest_sha256=trusted)

    def test_no_draft_acknowledgement_means_no_docker_or_runtime_changes(self):
        package=self.fixture.bundle()
        with patch.object(self.customer,'_docker') as docker:
            with self.assertRaises(ValueError):
                self.customer.load_images(package)
            with self.assertRaises(ValueError):
                self.customer.run_action(package,self.path/'runtime','initialize')
        docker.assert_not_called()
        self.assertFalse((self.path/'runtime').exists())

    def test_real_backup_restore_preserves_database_evidence_and_backup_artifact(self):
        from .operations_backup import create_backup
        source=self.path/'source';source.mkdir()
        database=source/'database.sqlite3'
        with closing(sqlite3.connect(database)) as db:
            db.execute('create table human_review (id integer primary key, result text)')
            db.execute("insert into human_review values (1,'human-confirmed-synthetic')")
            db.commit()
        media=source/'media';media.mkdir();(media/'original.png').write_bytes(b'unchanged original bytes')
        backup=self.path/'backup'
        create_backup(database,media,backup,release_id='a'*40,quiesced=True)
        before={name:self.customer._digest(path) for name,path in self.customer._files(backup).items()}
        package=self.fixture.bundle();secret,tls=self.fixture.private_inputs()
        result=self.customer.prepare_runtime(package,self.path/'runtime',host='customer.example.test',
            lan_ip='192.168.20.10',secret_file=secret,tls_directory=tls,
            acknowledge_draft=True,restore_backup=backup)
        self.assertTrue(result['restored_backup'])
        self.assertFalse(result['deployment_performed'])
        restored=self.path/'runtime/data'
        self.assertEqual((restored/'media/original.png').read_bytes(),b'unchanged original bytes')
        with closing(sqlite3.connect((restored/'database.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
            self.assertEqual(db.execute('select result from human_review').fetchone(),('human-confirmed-synthetic',))
        self.assertEqual(before,{name:self.customer._digest(path) for name,path in self.customer._files(backup).items()})

    def test_missing_image_archive_blocks_loading_without_network_or_docker(self):
        package=self.fixture.bundle()
        (package/'images/server-images.tar').unlink()
        with patch.object(self.customer,'_docker') as docker,self.assertRaises(ValueError):
            self.customer.load_images(package,acknowledge_draft=True)
        docker.assert_not_called()

    def test_start_requires_initialized_existing_data_and_preserves_empty_runtime(self):
        package,_=self.prepare()
        runtime=self.path/'runtime'
        with patch.object(self.customer,'_docker') as docker,self.assertRaises(ValueError):
            self.customer.run_action(package,runtime,'start',acknowledge_draft=True)
        docker.assert_not_called()
        self.assertFalse((runtime/'data/database.sqlite3').exists())


class _Assets(HTMLParser):
    def __init__(self,html):
        super().__init__();self.urls=[];self.feed(html)
    def handle_starttag(self,tag,attributes):
        values=dict(attributes)
        if tag in ('script','img','iframe') and values.get('src'):self.urls.append(values['src'])
        if tag=='link' and values.get('rel') in ('stylesheet','preload','preconnect') and values.get('href'):self.urls.append(values['href'])


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['localhost','127.0.0.1','testserver'],
    SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentCustomerHTTPTests(StaticLiveServerTestCase):
    host='127.0.0.1'
    def test_authenticated_saved_company_settings_load_all_critical_assets_locally(self):
        company=Company.objects.create(name='Synthetic independent offline company')
        user=User.objects.create_user('independent_offline_admin')
        user.profile.role=Profile.Roles.ADMIN;user.profile.company=company
        industry,_=IndustryCatalog.objects.get_or_create(code='telecom',defaults={
            'name':'Telecom','workflow_family':'telecom'})
        user.profile.admin_industry=industry;user.profile.save()
        self.client.force_login(user)
        from django.conf import settings
        from urllib.request import Request
        cookie=settings.SESSION_COOKIE_NAME+'='+self.client.cookies[settings.SESSION_COOKIE_NAME].value
        url=self.live_server_url+reverse('ai_settings_company',args=[company.pk])
        opener=build_opener(ProxyHandler({}))
        with opener.open(Request(url,headers={'Cookie':cookie}),timeout=10) as response:
            self.assertEqual(response.status,200);html=response.read().decode()
        self.assertIn(company.name,html)
        assets=_Assets(html).urls
        self.assertTrue(assets)
        for resource in assets:
            self.assertFalse(urlsplit(resource).netloc,resource)
            self.assertFalse(urlsplit(resource).scheme,resource)
            if resource.startswith('/static/'):
                with opener.open(self.live_server_url+resource,timeout=10) as response:
                    self.assertEqual(response.status,200)
                    self.assertGreater(len(response.read()),0)


class IndependentCustomerPDFTests(SimpleTestCase):
    def pdf(self, *, scanned):
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        from PIL import Image,ImageDraw
        output=BytesIO();pdf=canvas.Canvas(output,pagesize=(500,700))
        if scanned:
            image=Image.new('RGB',(1000,1400),'white')
            ImageDraw.Draw(image).text((50,50),'SYNTHETIC SITE HEIGHT 30 m',fill='black')
            pdf.drawImage(ImageReader(image),0,0,width=500,height=700)
        else:
            pdf.drawString(25,650,'SYNTHETIC SITE HEIGHT 30 m')
        pdf.showPage();pdf.save()
        return output.getvalue()

    def source(self, raw):
        from .survey_evidence import extract_sources
        return next(extract_sources([], [{'id':88,'filename':'synthetic.pdf','raw':raw,
            'sha256':hashlib.sha256(raw).hexdigest()}]))

    def test_scanned_pdf_ocr_unavailable_still_delivers_preserved_page_image_for_review(self):
        from .survey_evidence import analyse_source
        from .test_ai_settings_independent import image_provider_fixture
        from PIL import Image
        raw=self.pdf(scanned=True);source=self.source(raw)
        self.assertTrue(source['metadata']['local_ocr_required'])
        self.assertEqual(source['text'],'')
        with image_provider_fixture() as (base,requests),patch('core.local_evidence_tools._ocr_engine',side_effect=ImportError('synthetic unavailable')):
            result=analyse_source(source,'qwen3.5:4b',base_url=base)
        self.assertEqual(result['local_ocr']['status'],'unavailable')
        self.assertEqual(result['local_ocr']['provenance']['verification_status'],'unverified_source_text')
        self.assertTrue(any('Local OCR is unavailable' in value for value in result['missing']))
        self.assertEqual(result['verification_status'],'needs_review')
        self.assertEqual(result['sha256'],hashlib.sha256(raw).hexdigest())
        chat=[body for route,body in requests if route=='/api/chat']
        self.assertEqual(len(chat),1)
        with Image.open(BytesIO(base64.b64decode(chat[0]['messages'][1]['images'][0],validate=True))) as preview:
            self.assertGreater(min(preview.size),100)
        self.assertIn('UNTRUSTED_EVIDENCE_JSON',chat[0]['messages'][1]['content'])
        self.assertEqual(result['findings'],[])

    def test_digital_pdf_uses_real_text_and_image_without_optional_ocr_engine(self):
        from .survey_evidence import analyse_source
        from .test_ai_settings_independent import image_provider_fixture
        raw=self.pdf(scanned=False);source=self.source(raw)
        self.assertFalse(source['metadata']['local_ocr_required'])
        self.assertIn('HEIGHT 30 m',source['text'])
        with image_provider_fixture() as (base,requests),patch('core.local_evidence_tools.local_ocr',side_effect=AssertionError('Digital text needs no OCR')):
            result=analyse_source(source,'qwen3.5:4b',base_url=base)
        self.assertNotIn('local_ocr',result)
        chat=[body for route,body in requests if route=='/api/chat']
        self.assertEqual(len(chat),1)
        self.assertIn('HEIGHT 30 m',chat[0]['messages'][1]['content'])
        self.assertEqual(result['verification_status'],'needs_review')
