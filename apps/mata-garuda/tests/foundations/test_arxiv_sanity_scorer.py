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
