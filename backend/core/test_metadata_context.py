"""Full catalog context improves retrieval without turning hints into evidence."""
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from .photo_metadata import match_metadata
from .field_photo_service import metadata_workflow

class MetadataContextTests(SimpleTestCase):
    def observation(self):return {'caption':'An antenna is mounted above a concrete foundation.','objects':['antenna','foundation'],'visible_text':[],'issues':[],'uncertainties':[]}
    def schema(self,fields):return {'sections':[{'id':'tower','title':'Tower antenna foundation','description':'Structural support','group':'Tower','fields':fields}]}
    def test_description_can_anchor_but_section_and_group_alone_cannot(self):
        fields=[{'id':'supported','label':'Equipment photo','description':'Antenna foundation','type':'photo'},{'id':'generic','label':'Equipment photo','type':'photo'},{'id':'measurement','label':'Antenna foundation','type':'number'},{'id':'defect','label':'Equipment photo','description':'Antenna rust','type':'photo'}]
        candidates=match_metadata(self.observation(),self.schema(fields),photo_group='Tower')
        self.assertEqual([item['field_id'] for item in candidates],['supported'])
        self.assertIsNone(candidates[0]['value'])
        self.assertEqual(candidates[0]['uncertainty'],'medium')
        self.assertIn('reviewer hint',candidates[0]['reason'])
    def test_multiple_supported_candidates_stay_low_strength_for_review(self):
        fields=[{'id':name,'label':'Antenna foundation','type':'photo'} for name in ['first','second']]
        candidates=match_metadata(self.observation(),self.schema(fields))
        self.assertEqual(len(candidates),2)
        self.assertTrue(all(item['uncertainty']=='high' and item['value'] is None for item in candidates))
    @patch('core.field_photo_service.placements')
    def test_unmatched_and_multiple_candidates_remain_explicit_confirmation_work(self,placements):
        placements.return_value.values.return_value=[{'photo_id':1,'status':'confirmed'},{'photo_id':2,'status':'proposed'},{'photo_id':2,'status':'proposed'}]
        photos=[SimpleNamespace(pk=number) for number in [1,2,3]]
        analysis={'analyzed_photo_ids':[1,2,3],'current_matching_photo_ids':[1],'unprocessed_photo_ids':[]}
        result=metadata_workflow(None,photos,{1:True,2:True,3:True},analysis,[])
        self.assertEqual(result['stage'],'awaiting_confirmation')
        self.assertEqual(result['unmatched_photo_ids'],[3])
        self.assertEqual(result['multiple_proposal_photo_ids'],[2])
        self.assertEqual(result['review_photo_ids'],[2,3])
        self.assertEqual(result['rematch_recommended_photo_ids'],[2,3])
        self.assertTrue(result['requires_confirmation'])
    @patch('core.field_photo_service.placements')
    def test_queued_and_stale_jobs_do_not_claim_metadata_extraction_is_running(self,placements):
        placements.return_value.values.return_value=[]
        analysis={'analyzed_photo_ids':[],'current_matching_photo_ids':[],'unprocessed_photo_ids':[1]}
        result=metadata_workflow(None,[SimpleNamespace(pk=1)],{1:False},analysis,[{'status':'queued','progress':{}},{'status':'running','current_schema':False,'progress':{'stage':'matching_checklist'}}])
        self.assertEqual(result['stage'],'pending_analysis')
