"""Tests for the visa/immigration subgraph — legacy identification helpers.

The heavy end-to-end planner behavior now lives in test_visa_planner.py.
This file preserves only the _identify_visa_type regression tests.
"""

import pytest

from nuzantara_graph.subgraphs.visa.specs import VISA_SPECS, _identify_visa_type
from nuzantara_schemas.domain.visa import VisaType
from nuzantara_schemas.state import GraphState


class TestIdentifyVisaType:
    def test_kitas_from_entities(self):
        state = GraphState(query="test", extracted_entities={"visa_type": "kitas"})
        assert _identify_visa_type(state) == VisaType.KITAS

    def test_kitap_from_query(self):
        state = GraphState(query="How to get a permanent stay permit KITAP?")
        assert _identify_visa_type(state) == VisaType.KITAP

    def test_voa_from_query(self):
        state = GraphState(query="Visa on arrival for tourists")
        assert _identify_visa_type(state) == VisaType.VOA

    def test_b211a_from_query(self):
        state = GraphState(query="B211A social visa requirements")
        assert _identify_visa_type(state) == VisaType.B211A

    def test_second_home_from_query(self):
        state = GraphState(query="Indonesia second home visa for retirees")
        assert _identify_visa_type(state) == VisaType.SECOND_HOME

    def test_work_permit_implies_kitas(self):
        state = GraphState(query="How to get a work permit in Indonesia?")
        assert _identify_visa_type(state) == VisaType.KITAS

    def test_default_is_kitas(self):
        state = GraphState(query="What are the visa requirements?")
        assert _identify_visa_type(state) == VisaType.KITAS

    def test_specs_contains_expected_types(self):
        for vt in (VisaType.KITAS, VisaType.KITAP, VisaType.VOA,
                   VisaType.SECOND_HOME, VisaType.E_VISA):
            assert vt in VISA_SPECS
            assert "requirements" in VISA_SPECS[vt]
