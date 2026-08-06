"""Regression checks for generators that previously wrote inside the checkout."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_kbli_generators_share_external_runtime_contract() -> None:
    generators = (
        "apps/backend-rag/scripts/kbli_enrichment_pipeline.py",
        "apps/backend-rag/scripts/kbli_silver_parallel.py",
        "apps/backend-rag/scripts/kbli_silver_validate.py",
    )

    for generator in generators:
        source = _read(generator)
        assert "NUZANTARA_RUNTIME_STATE_DIR" in source
        assert "KBLI_ENRICHMENT_OUTPUT_DIR" in source
        assert 'SCRIPT_DIR / "output"' not in source


def test_nlm_wrapper_defaults_outside_project_root() -> None:
    source = _read("apps/evaluator/nlm_deep_research/scripts/run_multimodal.sh")

    assert "NUZANTARA_ARTIFACT_ROOT" in source
    assert "NLM_DEEP_RESEARCH_OUTPUT_DIR" in source
    assert 'LOG_DIR="$PROJECT_ROOT/apps/evaluator' not in source


def test_c5a_renderer_defaults_to_desktop_archive() -> None:
    source = _read("research/visa/c5a-render-2026-05-26/render_c5a_report.py")

    assert "C5A_OUTPUT_DIR" in source
    assert "Path.home()" in source
    assert 'OUT_DIR = Path("/Users/' not in source
