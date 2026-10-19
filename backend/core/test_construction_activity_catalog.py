"""Granular construction activities have traceable, project-defined test records."""
from django.test import SimpleTestCase
from .standard_checklists import build_standard,STAGES,LEGACY_STAGES,STRUCTURAL_STAGES
from .template_service import validate_definition

class ConstructionActivityCatalogTests(SimpleTestCase):
    def test_each_activity_ends_with_repeating_test_register(self):
        for stage in STAGES:
            with self.subTest(stage=stage):
                definition=build_standard('construction_inspection_all',stages=[stage]);validate_definition(definition)
                section=definition['sections'][1]
                self.assertEqual(section['id'],stage)
                self.assertEqual(section['fields'][-1]['type'],'table')
                self.assertLessEqual(len(section['fields'][-1]['columns']),20)
                self.assertTrue(all(field['type']=='inspection' for field in section['fields'][:-1]))
                self.assertEqual(section['fields'][-1]['required'],stage in STRUCTURAL_STAGES)
                self.assertIn('na_reason',{c['id'] for c in section['fields'][-1]['columns']})
    def test_density_and_concrete_registers_capture_traceability_without_thresholds(self):
        definition=build_standard('construction_inspection_all',stages=['field_density_test','foundation_concrete'])
        density={c['id'] for c in definition['sections'][1]['fields'][-1]['columns']}
        self.assertTrue({'layer','location','method','criteria','moisture','wet_density','dry_density','reference_density','compaction','report','laboratory','decision','retest'}<=density)
        concrete={c['id'] for c in definition['sections'][2]['fields'][-1]['columns']}
        self.assertTrue({'batch','location','date','times','slump','units','specimens','lab_result','report','criteria','decision','retest'}<=concrete)
        self.assertTrue(all('value' not in f for s in definition['sections'] for f in s['fields']))
    def test_legacy_stages_remain_supported_and_full_coordination_is_concise(self):
        self.assertTrue(set(LEGACY_STAGES)<=set(STAGES))
        legacy=build_standard('construction_inspection_all',stages=['grey_structure'])
        full=build_standard('construction_inspection_all')
        grey=next(s for s in full['sections'] if s['id']=='grey_structure')
        self.assertLess(len(grey['fields']),len(legacy['sections'][1]['fields']))
        ids=[s['id'] for s in full['sections']]
        self.assertLess(ids.index('excavation'),ids.index('foundation_concrete'))
        self.assertLess(ids.index('other_floor_concrete'),ids.index('mep'))
    def test_structural_room_context_and_maximum_bounds(self):
        definition=build_standard('construction_inspection_all',stages=['foundation_reinforcement'],rooms=[{'type':'bedroom','name':'Bedroom 1'}])
        self.assertIn('Room walls',str(definition['sections'][-1]))
        self.assertTrue(all(f['room_context']['name']=='Bedroom 1' for f in definition['sections'][-1]['fields']))
        maximum=build_standard('construction_inspection_all',rooms=[{'type':'bathroom','name':'Room '+str(i)} for i in range(40)])
        validate_definition(maximum)
        self.assertLessEqual(len(maximum['sections']),100)
        self.assertLessEqual(sum(len(s['fields']) for s in maximum['sections']),3000)
    def test_other_floor_cycles_are_explicit_replicable_templates_not_fake_floors(self):
        definition=build_standard('construction_inspection_all',stages=['other_floor_reinforcement','other_floor_concrete'])
        self.assertEqual(len(definition['sections']),3)
        self.assertTrue(all('replicate per floor' in s['title'] for s in definition['sections'][1:]))
