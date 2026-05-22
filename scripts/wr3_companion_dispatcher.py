#!/usr/bin/env python3
"""WR3 Companion Dispatcher — wr2_episode_published → WR3 brief translation.

Triggered by the WR3 supervisor when a `wr2_episode_published` event arrives
on the PG eventbus. Reads the WR2 brief.json + slides.json sidecars, translates
them into a WR3-shape brief.json (with `mode=companion_from_carousel` and a
`sub_mode` field), and emits `wr3_episode_brief_requested` so the standard
WR3 supervisor route picks it up.

Critical contract (Law 2): NB source_ids are NEVER re-queried — claim_ids are
inherited verbatim from the WR2 brief. brief-interpreter is SKIPPED entirely.

Sub-mode selection (one of three):
  * story_15s         — default (always runs unless WR2 brief.companion_skip=true)
  * reel_60s          — opt-in via WR2 brief.companion_expand=true
  * comment_interactive — opt-in via WR2 brief.companion_engage=true

Multiple sub-modes can be requested simultaneously (e.g. --expand AND --engage
both set) → one companion event per sub-mode.

ENVIRONMENT
  DATABASE_URL           Postgres DSN (local pg-proxy port 15432)
  WR3_DRY_RUN            if 'true', log decisions, do NOT emit
  WR3_REPO_ROOT          repo root override (default: parent of this script)

USAGE
  Invoked programmatically from scripts/wr3_supervisor.py route_event() when
  channel == 'wr2_episode_published'. Also runnable standalone for backfill:

      python scripts/wr3_companion_dispatcher.py \\
          --wr2-slug kep71-spt-2025 \\
          --sub-modes story_15s,reel_60s
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

REPO_ROOT = Path(os.environ.get("WR3_REPO_ROOT", str(HERE.parent)))
COMPANION_MODE_YAML = (
    REPO_ROOT / "docs" / "wr3" / "contracts" / "modes" / "companion-mode.yaml"
)

logger = logging.getLogger("wr3-companion-dispatcher")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Required keys in the wr2_episode_published payload — also enforced at SQL
# layer by publish_wr2_episode_published_event() (migration 186).
# ---------------------------------------------------------------------------
REQUIRED_PAYLOAD_KEYS: tuple[str, ...] = (
    "slug",
    "slides_count",
    "hero_image_path",
    "primary_claim_ids",
    "domain",
    "audience_segment",
    "brief_path",
    "slides_path",
)


class CompanionDispatchError(RuntimeError):
    """Raised when payload validation OR brief translation fails irrecoverably."""


@dataclass(frozen=True)
class CompanionModeConfig:
    """In-memory view of docs/wr3/contracts/modes/companion-mode.yaml."""

    mode_name: str
    mode_version: str
    sub_modes: dict[str, dict[str, Any]]
    inherit_from_wr2: dict[str, bool]
    output_dir_template: str

    @property
    def default_sub_mode(self) -> str:
        for name, cfg in self.sub_modes.items():
            if cfg.get("is_default"):
                return name
        raise CompanionDispatchError(
            "companion-mode.yaml: no sub_mode marked is_default=true"
        )


def load_companion_mode_config(
    path: Path = COMPANION_MODE_YAML,
) -> CompanionModeConfig:
    """Load + minimally validate the mode YAML."""
    if not path.exists():
        raise CompanionDispatchError(f"companion-mode.yaml not found: {path}")
    raw = yaml.safe_load(path.read_text())
    if raw.get("mode_name") != "companion_from_carousel":
        raise CompanionDispatchError(
            f"Unexpected mode_name in {path.name}: {raw.get('mode_name')!r}"
        )
    if not raw.get("sub_modes"):
        raise CompanionDispatchError(f"No sub_modes declared in {path}")
    return CompanionModeConfig(
        mode_name=raw["mode_name"],
        mode_version=raw["mode_version"],
        sub_modes=dict(raw["sub_modes"]),
        inherit_from_wr2=dict(raw.get("inherit_from_wr2") or {}),
        output_dir_template=raw["output_dir_template"],
    )


def _validate_payload(payload: dict[str, Any]) -> None:
    missing = [k for k in REQUIRED_PAYLOAD_KEYS if k not in payload]
    if missing:
        raise CompanionDispatchError(
            f"wr2_episode_published payload missing keys: {missing}. "
            f"Required: {list(REQUIRED_PAYLOAD_KEYS)}"
        )
    if not isinstance(payload["primary_claim_ids"], list):
        raise CompanionDispatchError(
            "primary_claim_ids must be a list (got "
            f"{type(payload['primary_claim_ids']).__name__})"
        )


def _read_wr2_sidecar(payload: dict[str, Any], *, key: str) -> dict[str, Any]:
    """Read a WR2 sidecar JSON (brief or slides). Returns {} if absent.

    Absence is non-fatal — the mode-level failure_modes.missing_wr2_brief
    handler downgrades to slide-hook-only translation.
    """
    rel_path = payload.get(key)
    if not rel_path:
        return {}
    p = REPO_ROOT / rel_path if not Path(rel_path).is_absolute() else Path(rel_path)
    if not p.exists():
        logger.warning("WR2 sidecar %s not found at %s — degrading", key, p)
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        logger.warning("WR2 sidecar %s malformed (%s) — degrading", key, e)
        return {}


def _resolve_requested_sub_modes(
    wr2_brief: dict[str, Any], config: CompanionModeConfig
) -> list[str]:
    """Inspect WR2 brief for Antonello flags + return ordered list of sub-modes.

    `companion_skip: true` → return [] (no companion at all)
    `companion_expand: true` → add reel_60s
    `companion_engage: true` → add comment_interactive
    Default story_15s is always added unless `companion_skip=true`.
    """
    if wr2_brief.get("companion_skip"):
        return []
    out: list[str] = [config.default_sub_mode]
    if wr2_brief.get("companion_expand") and "reel_60s" in config.sub_modes:
        out.append("reel_60s")
    if wr2_brief.get("companion_engage") and "comment_interactive" in config.sub_modes:
        out.append("comment_interactive")
    return out


def _build_wr3_brief(
    payload: dict[str, Any],
    *,
    sub_mode: str,
    config: CompanionModeConfig,
    wr2_brief: dict[str, Any],
    wr2_slides: dict[str, Any],
) -> dict[str, Any]:
    """Translate WR2 sidecars + payload → WR3 brief.json shape.

    NB source_ids are NEVER copied — only claim_ids (already vetted).
    """
    sub_mode_cfg = config.sub_modes[sub_mode]
    output_dir = config.output_dir_template.format(
        wr2_slug=payload["slug"], sub_mode=sub_mode
    )
    # Hook line(s) from slides — first slide's headline if present, else fallback.
    hook = ""
    if wr2_slides and "slides" in wr2_slides:
        first = (wr2_slides["slides"] or [{}])[0]
        hook = first.get("headline") or first.get("text") or ""

    return {
        "wr3_brief_version": "1.0.0",
        "source_pipeline": "wr2_companion",
        "mode": config.mode_name,
        "sub_mode": sub_mode,
        "wr2_handoff": {
            "slug": payload["slug"],
            "slides_count": payload["slides_count"],
            "hero_image_path": payload["hero_image_path"],
            "brief_path": payload["brief_path"],
            "slides_path": payload["slides_path"],
        },
        # ── Claim inheritance (Law 2 — no re-query) ──────────────────
        "primary_claim_ids": list(payload["primary_claim_ids"]),
        "inherited_from_wr2": True,
        "skip_brief_interpreter": True,
        "skip_nb_query": True,
        # ── Domain / audience inherited verbatim ─────────────────────
        "domain": payload["domain"],
        "audience_segment": payload["audience_segment"],
        # ── Sub-mode rendering parameters ────────────────────────────
        "target_duration_s": sub_mode_cfg["target_duration_s"],
        "clip_count": sub_mode_cfg["clip_count"],
        "has_voiceover": sub_mode_cfg["has_voiceover"],
        "has_video": sub_mode_cfg["has_video"],
        "output_format": sub_mode_cfg["output_format"],
        "voice_register": sub_mode_cfg["voice_register"],
        "output_dir": output_dir,
        # ── Critic gate mask (mode-level, overrides default 4-lane) ──
        "critic_lane_mask": sub_mode_cfg["critic_lane_mask"],
        # ── Source material hint for script-editor (slide hooks) ─────
        "hook_from_wr2": hook,
        # ── Budget envelope (carried through to dispatch_agent) ──────
        "cost_ceiling_unit": sub_mode_cfg["cost"]["ceiling_unit"],
        "cost_ceiling_usd": sub_mode_cfg["cost"]["ceiling_usd"],
        # ── Provenance ────────────────────────────────────────────────
        "translated_at": datetime.now(timezone.utc).isoformat(),
        "translator": "wr3_companion_dispatcher.py",
        "mode_config_version": config.mode_version,
    }


async def dispatch_companion(
    payload: dict[str, Any],
    *,
    pg_conn: Any | None = None,
    config: CompanionModeConfig | None = None,
    dry_run: bool | None = None,
) -> list[dict[str, Any]]:
    """Main entry point.

    Reads WR2 sidecars, resolves the requested sub-modes (1-3), builds one
    WR3 brief per sub-mode, and emits `wr3_episode_brief_requested` for each
    via `publish_wr3_event()` on the supervisor's PG connection.

    Args:
        payload: the wr2_episode_published payload dict (already validated
            at SQL layer; we double-check at Python layer for safety).
        pg_conn: an asyncpg connection. If None, only return the translated
            briefs without emitting (useful for tests / backfill).
        config: optional pre-loaded CompanionModeConfig (else loaded from disk).
        dry_run: if True, never emit even with a live connection. Defaults
            to env var WR3_DRY_RUN.

    Returns:
        List of translated WR3 brief dicts (one per requested sub-mode).
    """
    if dry_run is None:
        dry_run = os.environ.get("WR3_DRY_RUN", "").lower() == "true"

    _validate_payload(payload)
    cfg = config or load_companion_mode_config()

    wr2_brief = _read_wr2_sidecar(payload, key="brief_path")
    wr2_slides = _read_wr2_sidecar(payload, key="slides_path")

    requested = _resolve_requested_sub_modes(wr2_brief, cfg)
    if not requested:
        logger.info(
            "WR2 carousel %s: companion_skip=true — emitting nothing",
            payload["slug"],
        )
        return []

    briefs: list[dict[str, Any]] = []
    for sub_mode in requested:
        brief = _build_wr3_brief(
            payload,
            sub_mode=sub_mode,
            config=cfg,
            wr2_brief=wr2_brief,
            wr2_slides=wr2_slides,
        )
        briefs.append(brief)
        logger.info(
            "Translated WR2 %s → WR3 brief sub_mode=%s (claim_ids=%d, output=%s)",
            payload["slug"],
            sub_mode,
            len(brief["primary_claim_ids"]),
            brief["output_dir"],
        )

        if pg_conn is None or dry_run:
            logger.info(
                "[%s] would emit wr3_episode_brief_requested (slug=%s sub_mode=%s)",
                "DRY_RUN" if dry_run else "NO_CONN",
                payload["slug"],
                sub_mode,
            )
            continue

        # Live emission — defer import so this module is importable without
        # the supervisor's runtime deps (used by unit tests).
        from wr3_supervisor import publish  # noqa: WPS433 (local import by design)

        await publish(
            pg_conn,
            channel="wr3_episode_brief_requested",
            payload=brief,
        )

    return briefs


# ---------------------------------------------------------------------------
# Standalone CLI (backfill / manual replay)
# ---------------------------------------------------------------------------


def _cli() -> int:
    parser = argparse.ArgumentParser(description="WR3 companion dispatcher")
    parser.add_argument("--wr2-slug", required=True, help="WR2 carousel slug")
    parser.add_argument(
        "--payload-json",
        type=Path,
        help="Path to a JSON file with the full wr2_episode_published payload",
    )
    parser.add_argument(
        "--sub-modes",
        default="",
        help="Comma-separated override (e.g. 'story_15s,reel_60s'). "
        "If empty, falls back to companion_skip/expand/engage flags from WR2 brief.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Translate only — never emit (default if no DATABASE_URL)",
    )
    args = parser.parse_args()

    if args.payload_json:
        payload = json.loads(args.payload_json.read_text())
    else:
        # Minimal smoke payload — caller must edit before real backfill.
        payload = {
            "slug": args.wr2_slug,
            "slides_count": 10,
            "hero_image_path": f"apps/war-room/output/carousel/{args.wr2_slug}/slide-01.png",
            "primary_claim_ids": [],
            "domain": "tax",
            "audience_segment": "expat-35-55",
            "brief_path": f"apps/war-room/output/carousel/{args.wr2_slug}/brief.json",
            "slides_path": f"apps/war-room/output/carousel/{args.wr2_slug}/slides.json",
        }

    async def _run() -> list[dict[str, Any]]:
        return await dispatch_companion(payload, pg_conn=None, dry_run=True)

    briefs = asyncio.run(_run())
    print(json.dumps(briefs, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
