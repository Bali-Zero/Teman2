"""SEO Guardian Cell — a living organ in the Nuzantara organism.

Supersedes the legacy `apps/evaluator/seo_guardian_*.py` scripts with a
proper cell following the SYMBIOSIS lifecycle (sense→think→act→reflect→
dream→mature). Uses cell-core PulseLoop as the heartbeat.

Lifecycle (per decision memo 2026-04-19 v2.1):
  pre_natal (NEW — sense-only, learning-locked)
    ↓ unlock: 80 GSC query + 3 website_organic lead + 28gg age
  embrione → neonato → giovane → adulto

Placement rationale: lives in apps/evaluator/ (not apps/mata-garuda/)
because mata-garuda is Zero's private OSINT blindato and forbids HTTP
APIs to Google (GSC, GA4) + cross-app imports from backend-rag
(event_bus) and bali-intel-scraper (gemini_seo_optimizer). The SEO Cell
is Bali Zero commercial tooling, not OSINT. This overrides the original
v2.1 memo point 1 ("sister of sentinel_cell in mata-garuda").

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md
Decision memo: ~/.claude/projects/-Users-nuzantara/memory/
                decision_seo_guardian_cell_v2_1.md
"""
from apps.evaluator.seo_cell.cell import create_seo_cell
from apps.evaluator.seo_cell.phase import SEOPhase, is_pre_natal

__all__ = ["create_seo_cell", "SEOPhase", "is_pre_natal"]
