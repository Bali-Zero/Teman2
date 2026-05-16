#!/usr/bin/env python3
"""
Diff zantara_core (v1) vs zantara_core_v2 (v2).

Renders both system prompts and runs structural assertions:
- LANGUAGE_PROTOCOL is byte-identical (the meta-rule must not drift).
- All v1 sections appear in v2 master template (or have a v2 replacement).
- Multi-language business phrases from business_rules_i18n surface in v2.
- v2 contains ALL three language variants for verify_with_team,
  redirect_to_indonesia, temporary_system_issue (these are the three
  business phrases re-authored in PR-16b/17 for multi-lang switching).
- Runtime placeholders survive both templates ({user_memory},
  {rag_results}, {query}).

Usage:
    PYTHONPATH=apps/backend-rag python3 scripts/zantara_prompt_canary/diff_prompts.py
    # Optional flags:
    #   --json     emit machine-readable report on stdout
    #   --strict   exit 1 on any assertion failure (default: exit 0 + summary)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _add_backend_to_path() -> None:
    """Best-effort sys.path setup so we can import backend.* without PYTHONPATH."""
    backend_app = REPO_ROOT / "apps" / "backend-rag"
    if backend_app.exists() and str(backend_app) not in sys.path:
        sys.path.insert(0, str(backend_app))


def _load_modules() -> tuple[object, object, dict]:
    _add_backend_to_path()
    try:
        from backend.prompts import zantara_core, zantara_core_v2  # type: ignore
        from backend.prompts.business_rules_i18n import (  # type: ignore
            BUSINESS_PHRASES_I18N,
        )
    except ImportError as exc:
        sys.stderr.write(
            f"❌ failed to import backend prompts modules: {exc}\n"
            "   make sure you ran:  PYTHONPATH=apps/backend-rag python3 ...\n",
        )
        raise SystemExit(2) from exc
    return zantara_core, zantara_core_v2, BUSINESS_PHRASES_I18N


def assert_protocol_unchanged(v1: object, v2: object) -> tuple[bool, str]:
    same = getattr(v1, "LANGUAGE_PROTOCOL") == getattr(v2, "LANGUAGE_PROTOCOL")
    return same, (
        "LANGUAGE_PROTOCOL byte-identical between v1 and v2"
        if same
        else "LANGUAGE_PROTOCOL DRIFTED — meta-rule must stay verbatim across v1/v2"
    )


def assert_section_presence(v2: object) -> tuple[bool, str]:
    master = getattr(v2, "ZANTARA_MASTER_TEMPLATE")
    required = (
        "SECURITY_BOUNDARY",
        "TOOL_USAGE_POLICY",
        "SYSTEM_INSTRUCTIONS",
        "KNOWLEDGE_GOVERNANCE",
        "LANGUAGE_PROTOCOL",
        "GREETING_RULES",
        "CITATION_RULES",
        "ESCALATION_PROTOCOL",
        "CRASH_PROTOCOL",
        "CLOSING_PHRASES",
        "INTERNAL_MONOLOGUE",
    )
    missing = [name for name in required if getattr(v2, name) not in master]
    if missing:
        return False, f"v2 master template missing sections: {missing}"
    return True, f"all {len(required)} required sections wired into v2 master"


def assert_multilang_phrases_surfaced(
    v2: object, phrases: dict,
) -> tuple[bool, list[str]]:
    """For each multi-lang phrase Gemini will pick at runtime, all 3 variants
    must end up inside the v2 master template — otherwise LANGUAGE_PROTOCOL
    has nothing to choose from."""
    master = getattr(v2, "ZANTARA_MASTER_TEMPLATE")
    must_surface = ("verify_with_team", "redirect_to_indonesia", "temporary_system_issue")
    missing: list[str] = []
    for key in must_surface:
        for lang, text in phrases.get(key, {}).items():
            if text not in master:
                missing.append(f"{key}/{lang}: {text!r}")
    if missing:
        return False, missing
    return True, []


def assert_runtime_placeholders(v1: object, v2: object) -> tuple[bool, str]:
    placeholders = ("{user_memory}", "{rag_results}", "{query}")
    bad: list[str] = []
    for label, mod in (("v1", v1), ("v2", v2)):
        master = getattr(mod, "ZANTARA_MASTER_TEMPLATE")
        for ph in placeholders:
            if ph not in master:
                bad.append(f"{label} missing {ph}")
    if bad:
        return False, "; ".join(bad)
    return True, "all runtime placeholders preserved in v1 and v2"


def template_size_delta(v1: object, v2: object) -> dict:
    v1_master = getattr(v1, "ZANTARA_MASTER_TEMPLATE")
    v2_master = getattr(v2, "ZANTARA_MASTER_TEMPLATE")
    return {
        "v1_chars": len(v1_master),
        "v2_chars": len(v2_master),
        "delta_chars": len(v2_master) - len(v1_master),
        "delta_pct": (
            round(((len(v2_master) - len(v1_master)) / len(v1_master)) * 100, 1)
            if len(v1_master)
            else 0.0
        ),
    }


def language_variant_coverage(v2: object, phrases: dict) -> dict:
    """How many phrase keys from business_rules_i18n surface in v2 master, per lang."""
    master = getattr(v2, "ZANTARA_MASTER_TEMPLATE")
    coverage: dict = {"per_phrase": {}, "summary": {"en": 0, "it": 0, "id": 0}}
    for key, langs in phrases.items():
        per_lang = {
            lang: text in master for lang, text in langs.items()
        }
        coverage["per_phrase"][key] = per_lang
        for lang, present in per_lang.items():
            if present and lang in coverage["summary"]:
                coverage["summary"][lang] += 1
    return coverage


def _pretty(label: str, ok: bool, detail: str | list[str]) -> str:
    icon = "✅" if ok else "❌"
    if isinstance(detail, list):
        joined = "\n    - ".join(detail) if detail else "(none)"
        return f"{icon} {label}\n    - {joined}"
    return f"{icon} {label} — {detail}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument(
        "--strict", action="store_true", help="exit 1 on any assertion failure",
    )
    args = parser.parse_args(argv)

    v1, v2, phrases = _load_modules()

    protocol_ok, protocol_msg = assert_protocol_unchanged(v1, v2)
    sections_ok, sections_msg = assert_section_presence(v2)
    multilang_ok, multilang_missing = assert_multilang_phrases_surfaced(v2, phrases)
    placeholders_ok, placeholders_msg = assert_runtime_placeholders(v1, v2)

    size = template_size_delta(v1, v2)
    coverage = language_variant_coverage(v2, phrases)

    all_ok = all((protocol_ok, sections_ok, multilang_ok, placeholders_ok))

    if args.json:
        report = {
            "all_ok": all_ok,
            "protocol_unchanged": {"ok": protocol_ok, "msg": protocol_msg},
            "sections_present": {"ok": sections_ok, "msg": sections_msg},
            "multilang_surfaced": {
                "ok": multilang_ok,
                "missing": multilang_missing,
            },
            "placeholders": {"ok": placeholders_ok, "msg": placeholders_msg},
            "size": size,
            "phrase_coverage": coverage,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("=== zantara_core v1 → v2 prompt diff ===")
        print(_pretty("LANGUAGE_PROTOCOL byte-identical", protocol_ok, protocol_msg))
        print(_pretty("v2 sections wired into master", sections_ok, sections_msg))
        print(_pretty(
            "multi-lang business phrases surfaced in v2",
            multilang_ok,
            multilang_missing if not multilang_ok else "verify_with_team, "
            "redirect_to_indonesia, temporary_system_issue all present in en/it/id",
        ))
        print(_pretty("runtime placeholders preserved", placeholders_ok, placeholders_msg))
        print()
        print(
            f"📐 template size: v1={size['v1_chars']} chars, "
            f"v2={size['v2_chars']} chars, "
            f"Δ={size['delta_chars']:+d} ({size['delta_pct']:+.1f}%)",
        )
        print(
            "📊 per-language phrase coverage in v2 master: "
            f"en={coverage['summary']['en']}, "
            f"it={coverage['summary']['it']}, "
            f"id={coverage['summary']['id']}",
        )
        print()
        print(("✅ READY for canary" if all_ok else "❌ FIX before canary"))

    return 0 if all_ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
