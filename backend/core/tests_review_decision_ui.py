from types import SimpleNamespace
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class ReviewDecisionPresentationTests(SimpleTestCase):
    def render_panel(self, **changes):
        route=dict(can_act=True, can_attempt_approve=True, can_approve=True,
                   can_approve_with_comments=True, can_reject=True, mode='review',
                   stage='quality_engineer', layers=4, token='synthetic-token',
                   events=[], approval_block_reason='')
        route.update(changes)
        return render_to_string('dashboards/_review_route.html',
                                {'review_route':route,'checklist':SimpleNamespace(pk=7)})

    def test_assigned_reviewer_can_choose_comment_approval_beside_ordinary_decision(self):
        html=self.render_panel()
        self.assertIn('value="approve_with_comments"',html)
        self.assertIn('Approve with comments',html)
        self.assertIn('value="reject"',html)
        self.assertRegex(html,r'value="approve"[^>]*formnovalidate')
        self.assertNotRegex(html,r'value="approve_with_comments"[^>]*formnovalidate')

    def test_gated_approval_is_visible_disabled_with_real_reason(self):
        html=self.render_panel(can_approve=False,can_approve_with_comments=False,
                               approval_block_reason='Complete the 17 outstanding evidence checks.')
        self.assertRegex(html,r'value="approve"[^>]*disabled')
        self.assertRegex(html,r'value="approve_with_comments"[^>]*disabled')
        self.assertIn('Complete the 17 outstanding evidence checks.',html)

    def test_history_is_compact_table_and_escapes_comment(self):
        event=SimpleNamespace(sequence=1,action='approve',reason='<img src=x onerror=alert(1)>',
                              actor='Synthetic Reviewer',created_at='2026-10-26',
                              from_stage='quality_engineer',to_stage='team_lead')
        html=self.render_panel(events=[event])
        self.assertIn('class="review-route-history-table"',html)
        self.assertIn('Approved with comments',html)
        for label in ('Actor','Time','Decision','From → to','Comment'):
            self.assertIn(label,html)
        self.assertIn('&lt;img',html)
        self.assertNotIn('<img src=x',html)
