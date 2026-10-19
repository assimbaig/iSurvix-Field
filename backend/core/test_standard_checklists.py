"""Pure standard starter generation preserves master and room-instance identity."""
from copy import deepcopy
from django.test import SimpleTestCase
from .standard_checklists import build_standard,catalog_entries,ROOM_TYPES,STAGES
from .template_service import default_definition,validate_definition

class StandardChecklistsTests(SimpleTestCase):
    def test_master_sections_and_fields_are_exactly_preserved(self):
        before=default_definition();generated=build_standard('telecom_survey_default')
        self.assertEqual({k:v for k,v in generated.items() if k!='standard_catalog'},before)
        self.assertEqual(sum(bool(f.get('excel_row')) for s in generated['sections'] for f in s['fields']),172)
        self.assertEqual(default_definition(),before)
    def test_four_catalog_entries_and_all_definitions_validate(self):
        entries=catalog_entries();self.assertEqual(len(entries),4)
        for entry in entries:
            with self.subTest(key=entry['key']):
                definition=build_standard(entry['key']);validate_definition(definition)
                self.assertEqual(entry['fields_count'],sum(len(s['fields']) for s in definition['sections']))
                self.assertEqual(entry['sections_count'],len(definition['sections']))
                self.assertEqual(definition['standard_catalog']['workflow_type'],entry['workflow_type'])
    def test_same_room_type_gets_distinct_sections_fields_and_floor_context(self):
        rooms=[{'type':'bedroom','name':'Bedroom 1','floor':'Ground'},{'type':'bedroom','name':'Bedroom 1','floor':'First'},{'type':'bathroom','name':'Bath','floor':'First'}]
        definition=build_standard('construction_inspection_all',rooms=rooms)
        sections=[s for s in definition['sections'] if s.get('room')]
        self.assertEqual(len(sections),3)
        self.assertEqual(len({f['id'] for s in sections for f in s['fields']}),sum(len(s['fields']) for s in sections))
        self.assertNotEqual(sections[0]['id'],sections[1]['id'])
        for section in sections:
            for field in section['fields']:
                self.assertEqual(field['room_context'],section['room'])
                self.assertTrue(field['label'].startswith(section['title']+' - '))
                self.assertNotIn('evidence_rules',field)
        self.assertIn('Wet-area waterproofing',str(sections[2]))
        self.assertNotIn('Wet-area waterproofing',str(sections[0]))
        validate_definition(definition)
    def test_stage_selection_canonical_order_and_room_specific_stair_checks(self):
        definition=build_standard('construction_inspection_all',stages=['finishing','design'],rooms=[{'type':'staircase','name':'Main stair'}])
        self.assertEqual(definition['standard_catalog']['stages'],['design','finishing'])
        self.assertEqual([s['id'] for s in definition['sections']],['site_information','design','finishing','room_01'])
        self.assertIn('Stair geometry',str(definition))
        self.assertNotIn('Concrete placement',str(definition))
    def test_strict_invalid_inputs(self):
        bad=[{'stages':[]},{'stages':['design','design']},{'stages':['unknown']},{'stages':'design'},{'rooms':{}},{'rooms':[{'type':'unknown','name':'X'}]},{'rooms':[{'type':'bedroom','name':'X','admin':True}]},{'rooms':[{'type':'bedroom','name':'  '}]},{'rooms':[{'type':'bedroom','name':'X\nY'}]},{'rooms':[{'type':'bedroom','name':'X'},{'type':'bedroom','name':' x '}]},{'rooms':[{'type':'bedroom','name':str(i)} for i in range(41)]}]
        for kwargs in bad:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):build_standard('construction_inspection_all',**kwargs)
        with self.assertRaises(ValueError):build_standard('unknown')
        with self.assertRaises(ValueError):build_standard('telecom_inspection_bts',stages=['design'])
        with self.assertRaises(ValueError):build_standard('telecom_survey_default',rooms=[{'type':'bedroom','name':'X'}])
    def test_maximum_rooms_stays_within_schema_limits(self):
        rooms=[{'type':ROOM_TYPES[i%len(ROOM_TYPES)],'name':f'Room {i+1}','floor':'Ground'} for i in range(40)]
        definition=build_standard('construction_inspection_all',rooms=rooms);validate_definition(definition)
        self.assertLessEqual(len(definition['sections']),100)
        self.assertLessEqual(sum(len(s['fields']) for s in definition['sections']),3000)
    def test_every_common_room_type_keeps_explicit_context_without_photo_text_gate(self):
        rooms=[{'type':kind,'name':kind.replace('_',' ').title(),'floor':'Level 1'} for kind in ROOM_TYPES]
        definition=build_standard('construction_inspection_all',rooms=rooms)
        validate_definition(definition)
        sections=[s for s in definition['sections'] if s.get('room')]
        self.assertEqual({s['room']['type'] for s in sections},set(ROOM_TYPES))
        for section in sections:
            self.assertTrue(all(f['room_context']==section['room'] for f in section['fields']))
            self.assertTrue(all('evidence_rules' not in f for f in section['fields']))

    def test_returned_data_and_caller_inputs_are_isolated(self):
        rooms=[{'type':'kitchen','name':'Kitchen'}];original=deepcopy(rooms)
        first=build_standard('construction_inspection_all',rooms=rooms);first['sections'][0]['fields'][0]['label']='Changed'
        first['standard_catalog']['rooms'][0]['name']='Changed'
        self.assertEqual(rooms,original)
        second=build_standard('construction_inspection_all',rooms=rooms)
        self.assertEqual(second['sections'][0]['fields'][0]['label'],'Site ID')
        self.assertEqual(second['standard_catalog']['rooms'][0]['name'],'Kitchen')
    def test_inspections_are_human_results_without_fabricated_thresholds(self):
        for key in ['telecom_inspection_bts','telecom_inspection_colocation','construction_inspection_all']:
            definition=build_standard(key)
            self.assertIn('technical qualification',definition['technical_notice'])
            self.assertTrue(all('value' not in f and 'answer' not in f for s in definition['sections'] for f in s['fields']))
            self.assertFalse(any(f.get('require_photo') for s in definition['sections'] for f in s['fields']))
            self.assertEqual(definition['sections'][0]['fields'][0]['system'],'site_id')
