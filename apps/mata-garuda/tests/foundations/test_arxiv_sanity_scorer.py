import pytest
from mata_garuda.foundations.arxiv_sanity_scorer import (
    ArxivSanityScorer,
    LabeledPaper,
)


def test_scorer_trains_and_predicts_higher_score_for_in_class():
    positive_papers = [
        LabeledPaper(id="p1", abstract="agentic LLM RAG retrieval", label=1),
        LabeledPaper(id="p2", abstract="RAG corrective self-RAG retrieval augmented", label=1),
        LabeledPaper(id="p3", abstract="agentic deep research multi-agent", label=1),
    ]
    negative_papers = [
        LabeledPaper(id="n1", abstract="quantum chromodynamics lattice gauge", label=0),
        LabeledPaper(id="n2", abstract="cosmology dark matter halo simulation", label=0),
        LabeledPaper(id="n3", abstract="condensed matter superconductivity bcs", label=0),
    ]

    scorer = ArxivSanityScorer()
    scorer.train(positive_papers + negative_papers)

    in_class = scorer.score("agentic RAG corrective retrieval")
    out_class = scorer.score("quantum lattice gauge theory")

    assert in_class > out_class
    assert 0.0 <= in_class <= 1.0
    assert 0.0 <= out_class <= 1.0


def test_scorer_raises_if_predict_before_train():
    scorer = ArxivSanityScorer()
    with pytest.raises(RuntimeError, match="not trained"):
        scorer.score("anything")


def test_scorer_handles_single_class_training_gracefully():
    """If user has only positive samples, scorer should not crash."""
    only_positive = [
        LabeledPaper(id="p1", abstract="agentic LLM", label=1),
        LabeledPaper(id="p2", abstract="RAG retrieval", label=1),
    ]
    scorer = ArxivSanityScorer()
    with pytest.raises(ValueError, match="at least two classes"):
        scorer.train(only_positive)


def test_scorer_three_papers_unbalanced_raises_before_sklearn_rejects_cv():
    """External-review fix (Codex/DeepSeek 2026-05-08): old code computed
    cv = min(3, len(papers)//2 or 2) = 1 for 3 papers (sklearn rejects cv=1).
    New code requires min_class >= 2 and gives a clear error."""
    insufficient = [
        LabeledPaper(id="p1", abstract="agentic LLM", label=1),
        LabeledPaper(id="p2", abstract="RAG retrieval", label=1),
        LabeledPaper(id="n1", abstract="quantum lattice", label=0),
    ]
    scorer = ArxivSanityScorer()
    with pytest.raises(ValueError, match=">=2 samples"):
        scorer.train(insufficient)


def test_scorer_four_papers_two_per_class_works():
    """Minimum balanced training set must succeed (cv=2)."""
    papers = [
        LabeledPaper(id="p1", abstract="agentic LLM RAG", label=1),
        LabeledPaper(id="p2", abstract="RAG retrieval LLM", label=1),
        LabeledPaper(id="n1", abstract="quantum lattice gauge", label=0),
        LabeledPaper(id="n2", abstract="cosmology dark matter", label=0),
    ]
    scorer = ArxivSanityScorer()
    scorer.train(papers)  # must not raise
    assert 0.0 <= scorer.score("agentic RAG") <= 1.0
