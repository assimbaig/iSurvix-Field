"""Scientific symbols retain their meaning before evidence enters a draft."""
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .survey_processing import numeric_evidence_value, prepare_checklist
from .survey_evidence import reconcile_results


class ScientificUnitRegressionTests(SimpleTestCase):
    def test_case_sensitive_prefixes_convert_without_changing_meaning(self):
        cases = [
            ('V', '1', 'mV', '0.001'),
            ('V', '1', 'MV', '1000000'),
            ('Hz', '1', 'mHz', '0.001'),
            ('Hz', '1', 'MHz', '1000000'),
            ('mV', '1', 'V', '1000'),
            ('MV', '1', 'V', '0.000001'),
            ('mHz', '1', 'Hz', '1000'),
            ('MHz', '1', 'Hz', '0.000001'),
        ]
        for expected, value, observed, converted in cases:
            with self.subTest(expected=expected, observed=observed):
                self.assertEqual(numeric_evidence_value(
                    {'unit': expected}, {'value': value, 'unit': observed}),
                    (converted, expected))

    def test_existing_length_and_electrical_conversions_remain_supported(self):
        cases = [
            ('m', '1200', 'mm', '1.2'),
            ('m', '120', 'cm', '1.2'),
            ('m', '1.2', 'km', '1200'),
            ('V', '0.1', 'kV', '100'),
            ('A', '1200', 'mA', '1.2'),
            ('W', '1.2', 'kW', '1200'),
            ('Hz', '1.2', 'kHz', '1200'),
            ('Hz', '1.2', 'GHz', '1200000000'),
        ]
        for expected, value, observed, converted in cases:
            with self.subTest(expected=expected, observed=observed):
                self.assertEqual(numeric_evidence_value(
                    {'unit': expected}, {'value': value, 'unit': observed}),
                    (converted, expected))

    def test_unknown_equal_units_do_not_bypass_supported_vocabulary(self):
        for unit in ('unknown', 'furlong', 'arbitrary-unit'):
            with self.subTest(unit=unit), self.assertRaises(ValidationError):
                numeric_evidence_value({'unit': unit}, {'value': '1', 'unit': unit})

    def test_ambiguous_or_unapproved_scaled_symbol_case_is_rejected(self):
        for unit in ('mv', 'mhz', 'MHZ', 'KV', 'Ma', 'MM'):
            with self.subTest(unit=unit), self.assertRaises(ValidationError):
                numeric_evidence_value({'unit': unit}, {'value': '1', 'unit': unit})

    def test_unitless_field_accepts_bare_numbers_and_supported_observations(self):
        self.assertEqual(numeric_evidence_value({}, {'value': '1.20', 'unit': ''}), ('1.2', ''))
        self.assertEqual(numeric_evidence_value({}, {'value': '1.20', 'unit': 'm'}), ('1.2', 'm'))
        self.assertEqual(numeric_evidence_value({}, {'value': '1', 'unit': 'MV'}), ('1', 'MV'))
        with self.assertRaises(ValidationError):
            numeric_evidence_value({}, {'value': '1', 'unit': 'unknown'})

    def test_default_checklist_battery_capacity_and_quantity_are_preserved(self):
        self.assertEqual(numeric_evidence_value({'unit': 'AH'}, {'value': '100', 'unit': 'AH'}), ('100', 'Ah'))
        self.assertEqual(numeric_evidence_value({'unit': 'Ah'}, {'value': '1000', 'unit': 'mAh'}), ('1', 'Ah'))
        self.assertEqual(numeric_evidence_value({'unit': 'Qty'}, {'value': '2', 'unit': 'Qty'}), ('2', 'Qty'))

    def test_explicit_base_and_angle_aliases_are_safe(self):
        cases = [('V', 'v', 'V'), ('A', 'a', 'A'), ('W', 'w', 'W'),
                 ('Hz', 'hz', 'Hz'), ('deg', 'degrees', 'deg'), ('°', 'deg', 'deg')]
        for expected, observed, canonical in cases:
            with self.subTest(expected=expected, observed=observed):
                self.assertEqual(numeric_evidence_value({'unit': expected}, {'value': '1', 'unit': observed}),
                                 ('1', canonical))

    def test_whitespace_is_trimmed_without_folding_prefix_case(self):
        self.assertEqual(numeric_evidence_value({'unit': ' V '}, {'value': '1', 'unit': ' MV '}),
                         ('1000000', 'V'))

    def test_nonfinite_and_excessive_numbers_remain_rejected(self):
        for value in ('NaN', 'sNaN', 'Infinity', '-Infinity', 'not-a-number', '1e99999999', '1e-99999999'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                numeric_evidence_value({'unit': 'V'}, {'value': value, 'unit': 'V'})

    def test_exact_decimal_conversion_preserves_recorded_precision(self):
        value = '123456789012345678901234567890.123456'
        self.assertEqual(numeric_evidence_value({'unit': 'm'}, {'value': value, 'unit': 'mm'}),
                         ('123456789012345678901234567.890123456', 'm'))
        self.assertEqual(numeric_evidence_value({'unit': 'V'}, {'value': value, 'unit': 'MV'}),
                         ('123456789012345678901234567890123456', 'V'))

    def test_incompatible_dimensions_and_missing_units_remain_rejected(self):
        for expected, observed in [('V', 'm'), ('m', 'V'), ('Ah', 'A'), ('Qty', 'm'), ('m', '')]:
            with self.subTest(expected=expected, observed=observed), self.assertRaises(ValidationError):
                numeric_evidence_value({'unit': expected}, {'value': '1', 'unit': observed})

    def package(self, expected, observations):
        snapshot = {'site_id': 'SYNTHETIC-UNITS', 'answers': {'custom': {}},
                    'schema': {'sections': [{'id': 'recorded', 'title': 'Recorded', 'fields': [
                        {'id': 'recorded_value', 'label': 'Recorded voltage', 'type': 'number', 'unit': expected}]}]}}
        reconciliation = {'findings': [
            {'field_hint': 'recorded_value', 'component': 'meter', 'category': 'measurement',
             'value': value, 'unit': unit, 'basis': 'recorded', 'confidence': 'medium',
             'evidence_quote': f'Synthetic label: {value} {unit}', 'source_id': f'photo:{index}',
             'reference': 'original'} for index, (value, unit) in enumerate(observations, 1)]}
        before = deepcopy(reconciliation)
        payload = prepare_checklist(snapshot, reconciliation)
        self.assertEqual(reconciliation, before)
        return payload, payload['checklist_items'][0]

    def test_conflicting_milli_and_mega_evidence_is_not_silently_merged(self):
        payload, item = self.package('V', [('1', 'mV'), ('1', 'MV')])
        self.assertIsNone(item['value'])
        self.assertTrue(item['conflict'])
        self.assertTrue(payload['conflicts'])
        self.assertEqual([x['unit'] for x in payload['findings']], ['mV', 'MV'])

    def test_invalid_equal_units_are_withheld_and_original_findings_retained(self):
        payload, item = self.package('unknown', [('1', 'unknown')])
        self.assertIsNone(item['value'])
        self.assertEqual(item['status'], 'Missing')
        self.assertTrue(payload['missing'])
        self.assertEqual(payload['findings'][0]['unit'], 'unknown')

    def test_valid_conversion_is_used_by_checklist_proposals(self):
        payload, item = self.package('V', [('0.1', 'kV')])
        self.assertEqual(item['value'], '100')
        self.assertEqual(item['unit'], 'V')
        self.assertEqual(item['sources'], [{'source_id': 'photo:1', 'reference': 'original'}])
        self.assertEqual(payload['missing'], [])

    def test_unitless_field_does_not_choose_identical_numbers_with_different_units(self):
        payload, item = self.package('', [('1', 'mV'), ('1', 'MV')])
        self.assertTrue(item['conflict'])
        self.assertIsNone(item['value'])
        self.assertTrue(payload['conflicts'])


class ExactUnitReconciliationTests(SimpleTestCase):
    def reconcile(self, observations, category='measurement'):
        results = [{'source_id': f'photo:{index}', 'findings': [
            {'field_hint': 'recorded_value', 'component': 'meter', 'category': category,
             'value': value, 'unit': unit, 'confidence': 'medium'}]}
            for index, (value, unit) in enumerate(observations, 1)]
        before = deepcopy(results)
        payload = reconcile_results(results)
        self.assertEqual(results, before)
        self.assertEqual(len(payload['findings']), len(results))
        return payload

    def test_milli_and_mega_prefixes_cannot_hide_reconciliation_conflicts(self):
        for first, second in [('mV', 'MV'), ('mHz', 'MHz')]:
            with self.subTest(first=first, second=second):
                self.assertEqual(len(self.reconcile([(1, first), (1, second)])['conflicts']), 1)

    def test_nearby_distinct_float_measurements_are_not_rounded_together(self):
        payload = self.reconcile([(30.00000000001, 'm'), (30.00000000002, 'm')])
        self.assertEqual(len(payload['conflicts']), 1)

    def test_large_integers_are_not_rounded_to_the_same_float(self):
        payload = self.reconcile([(9007199254740992, 'V'), (9007199254740993, 'V')])
        self.assertEqual(len(payload['conflicts']), 1)

    def test_equivalent_numeric_strings_and_base_symbols_do_not_conflict(self):
        cases = [[('30', 'm'), ('30000', 'mm')], [('1', 'kV'), ('1000', 'V')],
                 [('0.001', 'V'), ('1', 'mV')], [('100', 'AH'), ('100000', 'mAh')],
                 [('1', 'V'), ('1.0', 'v')]]
        for observations in cases:
            with self.subTest(observations=observations):
                self.assertEqual(self.reconcile(observations)['conflicts'], [])

    def test_long_decimal_measurements_preserve_every_recorded_digit(self):
        payload = self.reconcile([
            ('123456789012345678901234567890.123456', 'mm'),
            ('123456789012345678901234567.890123456', 'm')])
        self.assertEqual(payload['conflicts'], [])

    def test_unsupported_symbol_case_is_not_reinterpreted_as_a_valid_prefix(self):
        payload = self.reconcile([(1, 'mv'), (1, 'MV')])
        self.assertEqual(len(payload['conflicts']), 1)

    def test_numeric_looking_equipment_labels_keep_their_text_identity(self):
        payload = self.reconcile([('001', ''), ('1', '')], category='equipment')
        self.assertEqual(len(payload['conflicts']), 1)

    def test_extreme_numeric_text_does_not_overflow_reconciliation(self):
        payload = self.reconcile([('1e99999999', 'm'), ('1e99999999', 'm')])
        self.assertEqual(payload['conflicts'], [])
