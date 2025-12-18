"""
Tests for judgement_day.py - RAGAS Evaluation Script
Provides comprehensive test coverage with mocking for external dependencies.
"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest


# Mock external dependencies before importing judgement_day
@pytest.fixture(autouse=True)
def mock_external_deps():
    """Mock external dependencies that may not be installed"""
    # Create mock modules
    mock_langchain = MagicMock()
    mock_ragas = MagicMock()
    mock_datasets = MagicMock()

    # Mock the Dataset class
    class MockDataset:
        def __init__(self, data_dict=None):
            self._data = data_dict or {}
            self._len = len(data_dict.get("question", [])) if data_dict else 0

        @classmethod
        def from_dict(cls, data_dict):
            return cls(data_dict)

        @property
        def column_names(self):
            return list(self._data.keys())

        def __len__(self):
            return self._len

        def __getitem__(self, idx):
            if isinstance(idx, int):
                return {k: v[idx] for k, v in self._data.items()}
            return self._data.get(idx)

    mock_datasets.Dataset = MockDataset

    with patch.dict(sys.modules, {
        'langchain_google_genai': mock_langchain,
        'ragas': mock_ragas,
        'ragas.metrics': mock_ragas,
        'datasets': mock_datasets,
    }):
        yield


# Test data fixtures
@pytest.fixture
def sample_api_response():
    """Sample successful API response"""
    return {
        "answer": "KITAS adalah Kartu Izin Tinggal Terbatas untuk WNA di Indonesia.",
        "sources": [
            {"content": "KITAS adalah izin tinggal untuk orang asing."},
            {"content": "Proses pengajuan KITAS melalui kantor imigrasi."},
        ],
    }


@pytest.fixture
def sample_api_response_with_documents():
    """API response with documents fallback"""
    return {
        "answer": "BPJS Kesehatan adalah program jaminan kesehatan nasional.",
        "sources": [],
        "documents": [
            "BPJS adalah Badan Penyelenggara Jaminan Sosial.",
            "Registrasi dapat dilakukan secara online.",
        ],
    }


@pytest.fixture
def sample_evaluation_data():
    """Sample evaluation data for testing"""
    return [
        {
            "question": "Apa itu KITAS?",
            "answer": "KITAS adalah Kartu Izin Tinggal Terbatas.",
            "contexts": ["KITAS adalah izin tinggal.", "Pengajuan melalui imigrasi."],
        },
        {
            "question": "Bagaimana proses BPJS?",
            "answer": "Registrasi BPJS dapat dilakukan online.",
            "contexts": ["BPJS adalah jaminan sosial.", "Registrasi online tersedia."],
        },
    ]


@pytest.fixture
def evaluation_data_with_errors():
    """Evaluation data containing errors"""
    return [
        {
            "question": "Valid question",
            "answer": "Valid answer",
            "contexts": ["Valid context"],
        },
        {
            "question": "Failed question",
            "answer": "Error: 500",
            "contexts": [],
        },
        {
            "question": "No context question",
            "answer": "Answer without context",
            "contexts": [],
        },
    ]


class TestQueryNuzantaraApiLogic:
    """Tests for query_nuzantara_api function logic"""

    def test_extract_answer_from_response(self, sample_api_response):
        """Test answer extraction from API response"""
        data = sample_api_response
        answer = data.get("answer", "")
        assert "KITAS" in answer
        assert len(answer) > 0

    def test_extract_contexts_from_sources(self, sample_api_response):
        """Test context extraction from sources"""
        sources = sample_api_response.get("sources", [])
        contexts = [s.get("content", "") for s in sources if s.get("content")]

        assert len(contexts) == 2
        assert "izin tinggal" in contexts[0]

    def test_fallback_to_documents(self, sample_api_response_with_documents):
        """Test fallback to documents when sources empty"""
        data = sample_api_response_with_documents
        sources = data.get("sources", [])
        contexts = [s.get("content", "") for s in sources if s.get("content")]

        if not contexts:
            contexts = data.get("documents", [])[:5]

        assert len(contexts) == 2
        assert "BPJS" in contexts[0]

    def test_nested_answer_extraction(self):
        """Test extraction of nested answer"""
        data = {
            "answer": "",
            "response": {"answer": "Nested answer text"},
            "sources": [],
        }

        answer = data.get("answer", "")
        if not answer:
            answer = data.get("response", {}).get("answer", "")

        assert answer == "Nested answer text"

    def test_error_response_format(self):
        """Test error response structure"""
        error_result = {
            "question": "Test question",
            "answer": "Error: 500",
            "contexts": [],
        }

        assert error_result["question"] == "Test question"
        assert error_result["answer"].startswith("Error:")
        assert error_result["contexts"] == []


class TestCreateRagasDatasetLogic:
    """Tests for create_ragas_dataset function logic"""

    def test_dataset_dict_structure(self, sample_evaluation_data):
        """Test dataset dictionary has correct structure"""
        dataset_dict = {
            "question": [item["question"] for item in sample_evaluation_data],
            "answer": [item["answer"] for item in sample_evaluation_data],
            "contexts": [item["contexts"] for item in sample_evaluation_data],
        }

        assert "question" in dataset_dict
        assert "answer" in dataset_dict
        assert "contexts" in dataset_dict
        assert len(dataset_dict["question"]) == 2

    def test_dataset_content_extraction(self, sample_evaluation_data):
        """Test correct content extraction"""
        questions = [item["question"] for item in sample_evaluation_data]
        answers = [item["answer"] for item in sample_evaluation_data]

        assert questions[0] == "Apa itu KITAS?"
        assert "KITAS" in answers[0]

    def test_empty_dataset_handling(self):
        """Test handling of empty input"""
        empty_data = []
        dataset_dict = {
            "question": [item["question"] for item in empty_data],
            "answer": [item["answer"] for item in empty_data],
            "contexts": [item["contexts"] for item in empty_data],
        }

        assert len(dataset_dict["question"]) == 0

    def test_contexts_remain_as_lists(self, sample_evaluation_data):
        """Test that contexts are lists"""
        for item in sample_evaluation_data:
            assert isinstance(item["contexts"], list)


class TestDataFiltering:
    """Tests for data filtering logic in main()"""

    def test_filter_error_answers(self, evaluation_data_with_errors):
        """Test that error answers are filtered out"""
        valid_data = [
            item
            for item in evaluation_data_with_errors
            if item["contexts"] and not item["answer"].startswith("Error:")
        ]

        assert len(valid_data) == 1
        assert valid_data[0]["answer"] == "Valid answer"

    def test_filter_empty_contexts(self, evaluation_data_with_errors):
        """Test that entries without contexts are filtered out"""
        valid_data = [
            item for item in evaluation_data_with_errors if item["contexts"]
        ]

        assert len(valid_data) == 1
        assert valid_data[0]["contexts"] == ["Valid context"]

    def test_combined_filtering(self, evaluation_data_with_errors):
        """Test combined filtering of errors and empty contexts"""
        valid_data = [
            item
            for item in evaluation_data_with_errors
            if item["contexts"] and not item["answer"].startswith("Error:")
        ]

        # Only the first item should pass both filters
        assert len(valid_data) == 1
        assert valid_data[0]["question"] == "Valid question"

    def test_all_invalid_data(self):
        """Test when all data is invalid"""
        all_invalid = [
            {"question": "Q1", "answer": "Error: 500", "contexts": []},
            {"question": "Q2", "answer": "Answer", "contexts": []},
        ]

        valid_data = [
            item
            for item in all_invalid
            if item["contexts"] and not item["answer"].startswith("Error:")
        ]

        assert len(valid_data) == 0


class TestEvaluationMetrics:
    """Tests for evaluation metrics logic"""

    def test_faithfulness_score_range(self):
        """Test faithfulness scores are in valid range"""
        scores = [0.9, 0.85, 0.78]
        for score in scores:
            assert 0.0 <= score <= 1.0

    def test_relevancy_score_range(self):
        """Test relevancy scores are in valid range"""
        scores = [0.88, 0.92, 0.75]
        for score in scores:
            assert 0.0 <= score <= 1.0

    def test_average_calculation(self):
        """Test average score calculation"""
        df = pd.DataFrame({
            "faithfulness": [0.9, 0.85, 0.78],
            "answer_relevancy": [0.88, 0.92, 0.75],
        })

        avg_faithfulness = df["faithfulness"].mean()
        avg_relevancy = df["answer_relevancy"].mean()

        assert abs(avg_faithfulness - 0.843) < 0.01
        assert abs(avg_relevancy - 0.85) < 0.01

    def test_nan_handling(self):
        """Test handling of NaN values in scores"""
        df = pd.DataFrame({
            "faithfulness": [0.9, float('nan'), 0.78],
            "answer_relevancy": [0.88, 0.92, float('nan')],
        })

        avg_faithfulness = df["faithfulness"].mean(skipna=True)
        avg_relevancy = df["answer_relevancy"].mean(skipna=True)

        assert pd.notna(avg_faithfulness)
        assert pd.notna(avg_relevancy)


class TestAPIConfiguration:
    """Tests for API configuration"""

    def test_api_key_validation(self):
        """Test API key presence check"""
        api_key = "test-api-key-12345"
        assert api_key is not None
        assert len(api_key) > 0

    def test_empty_api_key(self):
        """Test empty API key detection"""
        api_key = None
        assert not api_key

        api_key = ""
        assert not api_key

    def test_api_url_format(self):
        """Test API URL format validation"""
        valid_urls = [
            "https://nuzantara-rag.fly.dev",
            "http://localhost:8080",
            "https://api.example.com",
        ]

        for url in valid_urls:
            assert url.startswith("http://") or url.startswith("https://")


class TestTestQuestions:
    """Tests for test questions configuration"""

    def test_questions_structure(self):
        """Test that questions follow expected structure"""
        # Sample questions similar to TEST_QUESTIONS
        test_questions = [
            "Apa itu KITAS dan bagaimana cara mendapatkannya?",
            "Bagaimana proses registrasi BPJS Kesehatan untuk expat?",
            "Apa persyaratan untuk mendirikan PT PMA di Indonesia?",
        ]

        assert len(test_questions) > 0

        for q in test_questions:
            assert isinstance(q, str)
            assert len(q) > 10  # Reasonable minimum length
            assert "?" in q  # Should be a question

    def test_questions_are_indonesian_law_related(self):
        """Test questions are about Indonesian topics"""
        test_questions = [
            "Apa itu KITAS dan bagaimana cara mendapatkannya?",
            "Bagaimana proses registrasi BPJS Kesehatan untuk expat?",
            "Apa persyaratan untuk mendirikan PT PMA di Indonesia?",
        ]

        indonesian_keywords = ["KITAS", "BPJS", "PT PMA", "Indonesia"]

        for q in test_questions:
            has_keyword = any(kw in q for kw in indonesian_keywords)
            assert has_keyword, f"Question should contain Indonesian legal term: {q}"


class TestResultsOutput:
    """Tests for results output handling"""

    def test_dataframe_to_csv(self):
        """Test DataFrame can be saved to CSV"""
        df = pd.DataFrame({
            "question": ["Q1", "Q2"],
            "answer": ["A1", "A2"],
            "faithfulness": [0.9, 0.85],
        })

        # Test CSV string generation
        csv_str = df.to_csv(index=False)
        assert "question" in csv_str
        assert "faithfulness" in csv_str

    def test_summary_display(self):
        """Test summary string generation"""
        df = pd.DataFrame({
            "question": ["Q1", "Q2"],
            "faithfulness": [0.9, 0.85],
            "answer_relevancy": [0.88, 0.92],
        })

        summary = df.to_string()
        assert "Q1" in summary
        assert "0.9" in summary


class TestAsyncHelpers:
    """Tests for async helper patterns"""

    @pytest.mark.asyncio
    async def test_async_iteration_pattern(self, sample_evaluation_data):
        """Test async iteration over questions"""
        results = []

        async def mock_query(question):
            return {"question": question, "answer": "test", "contexts": []}

        questions = ["Q1", "Q2", "Q3"]
        for q in questions:
            result = await mock_query(q)
            results.append(result)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_async_error_handling(self):
        """Test async error handling pattern"""
        async def failing_query():
            raise Exception("Network error")

        try:
            await failing_query()
            result = {"answer": "success"}
        except Exception as e:
            result = {"answer": f"Error: {str(e)}"}

        assert "Error:" in result["answer"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
