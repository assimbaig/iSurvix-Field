"""Explicit numeric evidence vocabulary shared by conversion and reconciliation.

Scientific symbols retain their case: milli and mega are different quantities.
Only the listed legacy aliases are accepted; unknown units require confirmation.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError


NUMERIC_EVIDENCE_UNITS = {
    'mm': ('length', Decimal('.001')), 'cm': ('length', Decimal('.01')),
    'm': ('length', Decimal(1)), 'km': ('length', Decimal(1000)),
    'mV': ('voltage', Decimal('.001')), 'V': ('voltage', Decimal(1)),
    'kV': ('voltage', Decimal(1000)), 'MV': ('voltage', Decimal(1000000)),
    'mA': ('current', Decimal('.001')), 'A': ('current', Decimal(1)),
    'W': ('power', Decimal(1)), 'kW': ('power', Decimal(1000)),
    'mHz': ('frequency', Decimal('.001')), 'Hz': ('frequency', Decimal(1)),
    'kHz': ('frequency', Decimal(1000)), 'MHz': ('frequency', Decimal(1000000)),
    'GHz': ('frequency', Decimal(1000000000)),
    'deg': ('angle', Decimal(1)),
    # These quantities occur in shipped checklist defaults. Battery capacity
    # is distinct from current, and a count is not a physical length.
    'mAh': ('battery_capacity', Decimal('.001')), 'Ah': ('battery_capacity', Decimal(1)),
    'Qty': ('count', Decimal(1)),
}
_UNIT_ALIASES = {
    # Unprefixed legacy symbols and angle words are unambiguous. Scaled
    # symbols are deliberately NOT casefolded: mV/MV and mHz/MHz differ.
    'v': 'V', 'a': 'A', 'w': 'W', 'hz': 'Hz',
    'degree': 'deg', 'degrees': 'deg', '°': 'deg',
    'AH': 'Ah', 'ah': 'Ah', 'qty': 'Qty',
}


def numeric_evidence_unit(value):
    unit = str(value).strip()
    canonical = _UNIT_ALIASES.get(unit, unit)
    if canonical and canonical not in NUMERIC_EVIDENCE_UNITS:
        raise ValidationError('The recorded measurement uses an unsupported unit; confirm its symbol and case.')
    return canonical
