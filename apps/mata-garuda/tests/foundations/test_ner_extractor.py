import pytest
from unittest.mock import patch, MagicMock
from mata_garuda.foundations.ner_extractor import (
    NERExtractor,
    NamedEntity,
)


def test_extract_returns_named_entities():
    fake_pipeline_output = [
        {"entity_group": "PERSON", "word": "Bimo Wijayanto", "score": 0.99, "start": 0, "end": 14},
        {"entity_group": "ORG", "word": "DJP", "score": 0.95, "start": 18, "end": 21},
    ]

    with patch("mata_garuda.foundations.ner_extractor.pipeline") as mock_pipeline_factory:
        mock_pipeline = MagicMock(return_value=fake_pipeline_output)
        mock_pipeline_factory.return_value = mock_pipeline

        extractor = NERExtractor()
        entities = extractor.extract("Bimo Wijayanto dari DJP")

    assert len(entities) == 2
    assert isinstance(entities[0], NamedEntity)
    assert entities[0].label == "PERSON"
    assert entities[0].text == "Bimo Wijayanto"
    assert entities[1].label == "ORG"


def test_extract_empty_text_returns_empty_list():
    with patch("mata_garuda.foundations.ner_extractor.pipeline") as mock_pipeline_factory:
        mock_pipeline = MagicMock(return_value=[])
        mock_pipeline_factory.return_value = mock_pipeline

        extractor = NERExtractor()
        entities = extractor.extract("")

    assert entities == []


def test_filter_by_label_only_returns_matching():
    fake_pipeline_output = [
        {"entity_group": "PERSON", "word": "Bimo", "score": 0.99, "start": 0, "end": 4},
        {"entity_group": "ORG", "word": "DJP", "score": 0.95, "start": 8, "end": 11},
    ]
    with patch("mata_garuda.foundations.ner_extractor.pipeline") as mock_pipeline_factory:
        mock_pipeline = MagicMock(return_value=fake_pipeline_output)
        mock_pipeline_factory.return_value = mock_pipeline

        extractor = NERExtractor()
        people = extractor.extract("Bimo dari DJP", labels=("PERSON",))

    assert len(people) == 1
    assert people[0].text == "Bimo"
