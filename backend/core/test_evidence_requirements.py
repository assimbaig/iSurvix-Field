"""Published evidence requirements use confirmed sources and saved assessments only."""
from copy import deepcopy
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from .models import Project,Checklist,ChecklistTemplate,PhotoEvidence,PhotoPlacement
from .template_service import validate_definition,missing_required
from .field_photo_service import schema_digest
from .evidence_learning import get_or_create_analysis
from .evidence_rules import evaluate_evidence

class EvidenceRequirementTests(TestCase):
    def setUp(self):
        self.field={'id':'sign','label':'Site identification sign condition','type':'inspection','required':True,'photo_required':True,'evidence_rules':{'min_photos':2}}
        self.schema={'sections':[{'id':'general','title':'General','fields':[self.field]}]}
        self.template=ChecklistTemplate.objects.create(name='Reviewed evidence schema',definition=self.schema,published=True)
        self.project=Project.objects.create(name='Reviewed evidence project',checklist_template=self.template)
        self.user=User.objects.create_user('requirements_engineer')
        self.checklist=Checklist.objects.create(user=self.user,project=self.project,site_id='SITE-1',answer_data={'custom':{'sign':{'result':'Checked','remarks':'Human reviewed source'}}})
        self.number=0
    def photo(self,status='confirmed'):
        self.number+=1
        photo=PhotoEvidence.objects.create(checklist=self.checklist,sha256=str(self.number).zfill(64),filename='synthetic.png')
        PhotoPlacement.objects.create(photo=photo,field_id='sign',section_id='general',status=status,schema_digest=schema_digest(self.checklist))
        return photo
    def change_rules(self,rules):
        self.checklist.schema_snapshot['sections'][0]['fields'][0]['evidence_rules']=rules
        self.checklist.save(update_fields=['schema_snapshot'])
    def analysis(self,photo,gps=True,identifier='SITE-1',version='test-v1'):
        metadata={'caption':'A large site identification sign is visible on a support.','objects':['sign'],'visible_text':['Site ID: '+identifier],'issues':[],'uncertainties':[]}
        tools={'capture_facts':{'gps':{'latitude':24,'longitude':46}} if gps else {}}
        versions={key:version for key in ['rules_version','model_version','tool_version','prompt_version']}
        assessments=evaluate_evidence(metadata,self.checklist.schema_snapshot,tools)
        payload={'assessments':assessments,'observations':metadata,'tools':tools,'drafts':[],'versions':versions}
        return get_or_create_analysis(self.checklist,photo,payload,versions)[0]
    def test_schema_rejects_unsupported_or_unsafe_rules(self):
        for rules in [{'auto_pass':True},{'min_photos':False},{'require_qr':'yes'}]:
            schema=deepcopy(self.schema);schema['sections'][0]['fields'][0]['evidence_rules']=rules
            with self.assertRaises(ValidationError):validate_definition(schema)
        validate_definition(self.schema)
    def test_distinct_confirmed_sources_only_and_human_answer_still_required(self):
        self.photo('proposed');self.photo('rejected')
        self.assertTrue(any('distinct confirmed' in text for text in missing_required(self.checklist)))
        self.photo('confirmed');self.photo('manual')
        self.assertEqual(missing_required(self.checklist),[])
        self.checklist.answer_data={};self.checklist.save()
        self.assertIn('Site identification sign condition',missing_required(self.checklist))
    @patch('core.photo_service.ollama',side_effect=AssertionError('Inference on validation is forbidden'))
    def test_saved_supported_assessment_required_without_inference_on_reads(self,native):
        self.change_rules({'require_gps':True})
        photo=self.photo()
        self.assertTrue(any('0 available' in text for text in missing_required(self.checklist)))
        self.analysis(photo,gps=False)
        self.assertTrue(missing_required(self.checklist))
        self.analysis(photo,gps=True,version='test-v2')
        self.assertEqual(missing_required(self.checklist),[])
        native.assert_not_called()
    def test_old_schema_or_changed_source_hash_cannot_satisfy_requirements(self):
        self.change_rules({'require_gps':True})
        photo=self.photo();self.analysis(photo)
        self.assertEqual(missing_required(self.checklist),[])
        photo.sha256='f'*64;photo.save(update_fields=['sha256'])
        self.assertTrue(missing_required(self.checklist))
        self.checklist.schema_snapshot['sections'][0]['fields'][0]['description']='Explicitly revised criterion'
        self.checklist.save(update_fields=['schema_snapshot'])
        self.assertTrue(any('distinct confirmed' in text for text in missing_required(self.checklist)))
    def test_known_identity_contradiction_blocks_even_with_other_supported_source(self):
        self.change_rules({'expected_site_id':'SITE-1'})
        first=self.photo();self.analysis(first)
        wrong=self.photo();self.analysis(wrong,identifier='WRONG-2')
        self.assertTrue(any('contradictory' in text for text in missing_required(self.checklist)))
    def test_existing_no_rule_schema_keeps_previous_evidence_behavior(self):
        self.change_rules({})
        self.photo('manual')
        self.assertEqual(missing_required(self.checklist),[])
