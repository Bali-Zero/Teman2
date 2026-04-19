"""Oracle — Layer 4 cognitive (design §17.4).

Weekly Consiglio esteso (4 voces + judge) that proposes ≤3 "ultra moves"
to Zero — non-obvious strategic opportunities that synthesize everything
else the organism has produced.

Structural diversity (§3.1 Pilastro 4): the 4 proponents come from 4
architecturally different models, plus a separate Claude judge.

    V1 · claude -p (Opus)           — strategic analyst, McKinsey-style
    V2 · gemini -p (Pro)            — compliance lawyer, Indonesian bar
    V3 · DeepSeek R1 HTTP           — behavioural economist
    V4 · Ollama gemma4:26b          — skeptic devil's advocate (refuse groupthink)
    Judge · claude -p (Sonnet)      — synthesises to ≤3 UltraMove

Simpler than ToneCouncil (Sprint 3): we don't need the Round-1 challenge
step because the voices are already producing action proposals (not tonal
choices). The judge's job is to synthesize — or veto — not to select.

All calls go through :class:`CLIRunner` (Legge 1; DeepSeek HTTP is the
documented exception).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.services.cognitive.models import (
    UltraMove,
    UltraMoveCreate,
)
from backend.services.cognitive.repository import CognitiveRepository
from backend.services.council.cli_runners import CLIRunner

logger = logging.getLogger(__name__)


MAX_MOVES = 3
MIN_PROPONENT_VOTES = 1   # minimum voices that back a move for it to survive
DEFAULT_ROUND_TIMEOUT = 150
DEFAULT_JUDGE_TIMEOUT = 180


PROPONENT_PERSONAS: dict[str, str] = {
    "claude": "strategic analyst in McKinsey style, focused on opportunity sizing",
    "gemini": "compliance lawyer from the Indonesian bar, Jakarta office",
    "deepseek": "behavioural economist, looking for second-order effects",
    "ollama": "skeptic devil's advocate — your job is to refuse consensus",
}


# ── Data contracts ────────────────────────────────────────────


@dataclass
class OracleProposal:
    author: str
    moves: list[dict[str, Any]] = field(default_factory=list)
    raw_output: str = ""
    ok: bool = True
    error: str | None = None


@dataclass
class OracleResult:
    ran_at: datetime
    context_chars: int = 0
    proposals: list[OracleProposal] = field(default_factory=list)
    judged_moves: list[UltraMoveCreate] = field(default_factory=list)
    inserted: list[UltraMove] = field(default_factory=list)
    skipped_duplicates: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def degraded(self) -> bool:
        valid = [p for p in self.proposals if p.ok]
        return len(valid) < len(self.proposals)


# ── Prompt templates ──────────────────────────────────────────


_PROPOSE_PROMPT = """Sei un proponente Oracle del Consiglio Nuzantara.
Persona: {persona}.

CONTESTO (Strategos brief, tesi, alerts, metriche, cicatrici):
{context}

COMPITO: proponi fino a {max_moves} "mosse ultra" — opportunità strategiche
NON richieste da nessuno, che sintetizzino il contesto. Ogni mossa deve
essere AZIONABILE, CONCRETA, NUOVA.

Rispondi SOLO JSON strict:

{{
  "moves": [
    {{
      "thesis": "tesi in 1 riga (massimo 300 char)",
      "narrative": "2-4 righe — perché questa mossa, ora",
      "target_query": "descrizione testuale del segmento cliente o entità impattata (facoltativo)",
      "estimated_cost": "1 riga — tempo/soldi/risorse (facoltativo)",
      "estimated_value": "1 riga — che ritorno atteso (facoltativo)",
      "recommended_tone_register": "rituale|analitico|ironico|militante|pedagogico|poetico|tecnico"
    }}
  ]
}}

Regole:
- NON replicare azioni già nel Strategos brief.
- Se non trovi mosse concrete, rispondi {{"moves": []}}. Meglio zero che rumore."""


_JUDGE_PROMPT = """Sei il giudice Oracle del Consiglio Nuzantara.

Queste sono le proposte delle 4 voci:

{proposals_block}

CONTESTO ORIGINALE:
{context}

COMPITO: seleziona/sintetizza al massimo {max_moves} UltraMove da proporre a
Zero. Preferisci mosse che più voci hanno toccato (convergenza reale).
SCARTA mosse che appaiono solo in una voce, a meno che non siano
particolarmente forti. Se nessuna mossa supera la soglia, produci [].

Rispondi SOLO JSON strict:

{{
  "final_moves": [
    {{
      "thesis": "...",
      "narrative": "...",
      "target_query": "...",
      "estimated_cost": "...",
      "estimated_value": "...",
      "recommended_tone_register": "...",
      "source_voices": ["claude", "gemini", ...]
    }}
  ]
}}"""


# ── Council ───────────────────────────────────────────────────


class OracleCouncil:
    """4-voice propose + judge synthesize.

    Parameters
    ----------
    proponents : dict[str, CLIRunner]
        Name → runner. Typically 4 entries (claude/gemini/deepseek/ollama).
    judge : CLIRunner
        Separate Claude runner.
    max_moves : int
        Cap applied in prompts and post-validation.
    """

    def __init__(
        self,
        proponents: dict[str, CLIRunner],
        judge: CLIRunner,
        *,
        max_moves: int = MAX_MOVES,
        round_timeout: int = DEFAULT_ROUND_TIMEOUT,
        judge_timeout: int = DEFAULT_JUDGE_TIMEOUT,
    ) -> None:
        if not proponents:
            raise ValueError("OracleCouncil requires >= 1 proponent")
        self.proponents = proponents
        self.judge = judge
        self.max_moves = max_moves
        self.round_timeout = round_timeout
        self.judge_timeout = judge_timeout
        self.logger = logger

    async def deliberate(
        self,
        *,
        context: str,
    ) -> tuple[list[OracleProposal], list[UltraMoveCreate]]:
        """Returns (proposals, final_moves).

        Never raises; failures become per-proposal errors.
        """
        proposals = await self._round_propose(context=context)
        final_moves = await self._round_judge(
            proposals=proposals, context=context,
        )
        return proposals, final_moves

    # ── Round 1: propose ────────────────────────────────────

    async def _round_propose(
        self,
        *,
        context: str,
    ) -> list[OracleProposal]:
        import asyncio

        async def _one(name: str, runner: CLIRunner) -> OracleProposal:
            persona = PROPONENT_PERSONAS.get(name, name)
            prompt = _PROPOSE_PROMPT.format(
                persona=persona,
                context=context,
                max_moves=self.max_moves,
            )
            parsed, result = await runner.run_json(
                prompt, timeout=self.round_timeout,
            )
            if not result.ok or parsed is None:
                return OracleProposal(
                    author=name,
                    raw_output=result.output,
                    ok=False,
                    error=result.error or "invalid JSON",
                )
            moves = parsed.get("moves")
            if not isinstance(moves, list):
                moves = []
            return OracleProposal(
                author=name,
                moves=[m for m in moves if isinstance(m, dict)],
                raw_output=result.output,
                ok=True,
            )

        return await asyncio.gather(
            *[_one(name, runner) for name, runner in self.proponents.items()]
        )

    # ── Round 2: judge synthesize ───────────────────────────

    async def _round_judge(
        self,
        *,
        proposals: list[OracleProposal],
        context: str,
    ) -> list[UltraMoveCreate]:
        valid = [p for p in proposals if p.ok and p.moves]
        if not valid:
            # Nothing to synthesize; don't call the judge.
            return []

        proposals_block = json.dumps(
            [
                {
                    "author": p.author,
                    "moves": p.moves,
                }
                for p in valid
            ],
            ensure_ascii=False,
        )
        prompt = _JUDGE_PROMPT.format(
            proposals_block=proposals_block,
            context=context,
            max_moves=self.max_moves,
        )
        parsed, result = await self.judge.run_json(
            prompt, timeout=self.judge_timeout,
        )
        if not result.ok or parsed is None:
            # Fallback: pick moves that appear in ≥2 voices verbatim-ish,
            # else top from first ok proposal.
            return _fallback_merge(valid, cap=self.max_moves)

        raw_moves = parsed.get("final_moves")
        if not isinstance(raw_moves, list):
            return _fallback_merge(valid, cap=self.max_moves)

        out: list[UltraMoveCreate] = []
        for raw in raw_moves[: self.max_moves]:
            move = _coerce_move(raw)
            if move is not None:
                out.append(move)
        return out


# ── Orchestrator ─────────────────────────────────────────────


class OracleOrchestrator:
    """Weekly Oracle sweep: context → Council → insert pending UltraMoves.

    Idempotency: the orchestrator does NOT de-duplicate against pending
    moves (each week is a fresh deliberation). The caller (CLI or cron)
    should decide whether to clear previous pending moves first; we
    deliberately don't touch prior weeks' decisions.
    """

    def __init__(
        self,
        cognitive_repo: CognitiveRepository,
        council: OracleCouncil,
        context_fn: ContextFn,
    ) -> None:
        self.cognitive_repo = cognitive_repo
        self.council = council
        self.context_fn = context_fn
        self.logger = logger

    async def run_once(self) -> OracleResult:
        result = OracleResult(ran_at=datetime.now(timezone.utc))
        try:
            context = await self.context_fn()
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"context: {type(exc).__name__}: {exc}")
            return result
        result.context_chars = len(context)

        try:
            proposals, final_moves = await self.council.deliberate(
                context=context,
            )
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"council: {type(exc).__name__}: {exc}")
            return result
        result.proposals = proposals
        result.judged_moves = final_moves

        for move in final_moves:
            try:
                inserted = await self.cognitive_repo.insert_ultra_move(move)
                result.inserted.append(inserted)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(
                    f"insert {move.thesis[:50]}: {type(exc).__name__}: {exc}"
                )

        return result


from collections.abc import Awaitable, Callable  # noqa: E402

ContextFn = Callable[[], Awaitable[str]]


# ── Helpers ──────────────────────────────────────────────────


def _coerce_move(raw: Any) -> UltraMoveCreate | None:
    if not isinstance(raw, dict):
        return None
    thesis = str(raw.get("thesis") or "").strip()
    narrative = str(raw.get("narrative") or "").strip()
    if not thesis or not narrative:
        return None
    source_inputs: dict[str, Any] = {}
    for key in ("source_voices", "sources", "source_ids"):
        if key in raw and raw[key] is not None:
            source_inputs[key] = raw[key]
    try:
        return UltraMoveCreate(
            thesis=thesis[:500],
            narrative=narrative,
            target_query=_trim(raw.get("target_query"), 1000),
            estimated_cost=_trim(raw.get("estimated_cost"), 400),
            estimated_value=_trim(raw.get("estimated_value"), 400),
            recommended_tone_register=_trim(
                raw.get("recommended_tone_register"), 50,
            ),
            source_inputs=source_inputs,
        )
    except Exception as exc:  # noqa: BLE001 — Pydantic validation errors
        logger.debug("coerce_move failed: %s", exc)
        return None


def _trim(value: Any, max_chars: int) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:max_chars]


def _fallback_merge(
    proposals: list[OracleProposal],
    *,
    cap: int,
) -> list[UltraMoveCreate]:
    """Judge-unavailable fallback: pick top move from each proposal until cap.

    Simple round-robin keeps diversity: we take the first move of each
    voice in turn, then loop back for the second move, and so on.
    Validity gate via ``_coerce_move``; invalid → skipped.
    """
    merged: list[UltraMoveCreate] = []
    max_moves_per_proposer = max(
        (len(p.moves) for p in proposals), default=0,
    )
    for idx in range(max_moves_per_proposer):
        for proposal in proposals:
            if idx >= len(proposal.moves):
                continue
            move = _coerce_move(proposal.moves[idx])
            if move is not None:
                merged.append(move)
                if len(merged) >= cap:
                    return merged
    return merged[:cap]
