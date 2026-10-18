"""Large photo sets remain bounded without truncating review evidence."""
import json
from django.test import SimpleTestCase,TestCase
from django.contrib.auth.models import User
from .checklist_ai_review import review_batches,snapshot,digest_snapshot
from .models import Checklist,Project,PhotoEvidence


class ReviewPhotoScalingTests(SimpleTestCase):
    def test_four_hundred_photos_on_one_field_are_all_reviewed_in_bounded_chunks(self):
        ids=list(range(1,401))
        data={'schema':{'sections':[{'id':'tower','fields':[{'id':'base','label':'Tower base','type':'inspection'}]}]},'answers':{},'remarks':{},'images':{},'photos':[{'id':pid,'analysis_metadata':{'caption':'Visible tower support and concrete foundation. '*8}} for pid in ids],'photo_observations':[{'field_id':'base','photo_id':pid,'reason':'Verify the visible support and foundation.'} for pid in ids],'placements':[]}
        batches=list(review_batches(data))
        items=[item for batch in batches for item in batch]
        self.assertGreater(len(items),1)
        self.assertEqual([photo['id'] for item in items for photo in item['photo_evidence']],ids)
        self.assertEqual([obs['photo_id'] for item in items for obs in item['observations']],ids)
        self.assertTrue(all(sum(len(json.dumps(item,ensure_ascii=False).encode()) for item in batch)<=14000 for batch in batches))


class PhotoMetadataReviewTests(TestCase):
    def test_changed_visual_observations_invalidate_prior_review_snapshot(self):
        user=User.objects.create_user('metadata_review_fixture')
        project=Project.objects.create(name='Metadata review fixture')
        checklist=Checklist.objects.create(user=user,project=project,site_id='SYNTHETIC')
        photo=PhotoEvidence.objects.create(checklist=checklist,filename='synthetic.png',sha256='synthetic',analysis_metadata={'caption':'Initial unverified observation'},analysis_signature='old')
        before=snapshot(checklist)
        photo.analysis_metadata={'caption':'Changed unverified observation'}
        photo.analysis_signature='new'
        photo.save(update_fields=['analysis_metadata','analysis_signature'])
        after=snapshot(checklist)
        self.assertNotEqual(digest_snapshot(before),digest_snapshot(after))
        self.assertEqual(after['photos'][0]['analysis_metadata'],photo.analysis_metadata)
        checklist.refresh_from_db()
        self.assertEqual(checklist.answer_data,{})
        self.assertEqual(checklist.section_approvals,{})
