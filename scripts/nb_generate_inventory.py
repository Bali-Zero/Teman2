#!/usr/bin/env python3
"""Deterministic NB health-gather for nb-curator-daily.sh.

Runs `nlm notebook list --json` ONCE to enumerate all notebooks, then runs
`nlm source list <uuid> --json` for each of the 5 NB-INTEL notebooks.
Writes a machine-owned JSON to research/nb-health/nb-inventory-live.json
(--write flag) that the nb-curator brain reads instead of making ~88
sequential `nlm query` calls.

Stdlib-only apart from PyYAML, which the redactor needs and /usr/bin/python3
on Pro has. Compatible with /usr/bin/python3 (no venv required).

Titles are REDACTED before the file is written. The brain that reads this file
is a cloud model (agy/Gemini, Claude fallback), and it copies titles into the
health report that gets promoted to the repo. Some NotebookLM titles name a
client (Builder Contract §4), so they go through `scripts/_redact_pii.py`
(`nb_titles` + pass1-3 of `agent-library/config/redaction-rules.yaml`). If the
redactor cannot load, titles are WITHHELD, never written raw.

Exit codes:
  0  ok (dry-run or written)
  3  nlm failure (nlm not found / returncode != 0 / JSON parse error)

Stdout: single JSON line summary -> {"notebooks": N, "nb_intel": 5, "written": bool}
Stderr / logging: progress + warnings.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nb-inventory")

NLM_CLI = str(Path.home() / ".local" / "bin" / "nlm")
NLM_TIMEOUT = 90
NEAR_CAP_THRESHOLD = 480

# NB-INTEL live UUIDs (post 2026-05-18 switch). Keep in sync with
# apps/bali-intel-scraper/scripts/nb_dedup_exact_url.py — same NB_INTEL dict.
NB_INTEL: dict[str, str] = {
    "immigration": "1ed02e54-542f-426a-94f8-53c5ffde4b7d",
    "tax": "7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f",
    "press": "9d262101-abeb-4e15-af9c-c38e028c62fe",
    "regulation": "a17f134e-b9ab-42d9-bfc2-5bbc45165c76",
    "ai_research": "dc5d01cd-e99f-4c8f-aae4-75060b43d0de",
}

# Output path: <repo-root>/research/nb-health/nb-inventory-live.json
# __file__ is scripts/nb_generate_inventory.py → parent.parent = repo root.
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "research" / "nb-health" / "nb-inventory-live.json"
REDACT_PII_PATH = Path(__file__).resolve().parent / "_redact_pii.py"


# ── Pure I/O helpers (testable via mock) ───────────────────────────────────────

def fetch_notebooks() -> list[dict]:
    """Run `nlm notebook list --json` and return parsed list.

    Raises RuntimeError on non-zero exit, json.JSONDecodeError on bad JSON,
    subprocess.TimeoutExpired on timeout.
    """
    result = subprocess.run(
        [NLM_CLI, "notebook", "list", "--json"],
        capture_output=True,
        text=True,
        timeout=NLM_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"nlm notebook list failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return json.loads(result.stdout or "[]")


def fetch_sources(notebook_id: str) -> list[dict]:
    """Run `nlm source list <uuid> --json` and return parsed list.

    Raises RuntimeError on non-zero exit, json.JSONDecodeError on bad JSON,
    subprocess.TimeoutExpired on timeout.
    """
    result = subprocess.run(
        [NLM_CLI, "source", "list", notebook_id, "--json"],
        capture_output=True,
        text=True,
        timeout=NLM_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"nlm source list failed for {notebook_id} (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return json.loads(result.stdout or "[]")


# ── Pure logic (unit-testable without nlm) ─────────────────────────────────────

def classify_notebook(nb: dict, near_cap_threshold: int = NEAR_CAP_THRESHOLD) -> dict:
    """Enrich a notebook dict with 'health' and 'near_cap' fields.

    Pure function — no I/O. Takes a single notebook dict (from
    `nlm notebook list --json` output) and returns a new dict with two
    added fields:
      health:   'healthy' if source_count > 0, 'empty' otherwise.
      near_cap: True if source_count >= near_cap_threshold.

    Fields from nlm: id, title, source_count, updated_at.
    """
    count: int = nb.get("source_count", 0) or 0
    return {
        **nb,
        "health": "empty" if count == 0 else "healthy",
        "near_cap": count >= near_cap_threshold,
    }


def build_inventory(
    notebooks: list[dict],
    nb_intel_sources: dict[str, list[dict]],
    near_cap_threshold: int = NEAR_CAP_THRESHOLD,
) -> dict:
    """Build the full inventory dict from raw nlm output lists.

    Pure function — no I/O. Intended for unit-testing with fabricated inputs.

    Args:
        notebooks:         Output of fetch_notebooks() — list of notebook dicts.
        nb_intel_sources:  Mapping key -> fetch_sources(uuid) for each NB_INTEL entry.
        near_cap_threshold: Source count at/above which near_cap is True.

    Returns:
        Inventory dict containing:
          generated_at    ISO-8601 UTC timestamp (set at call time).
          notebook_count  Number of notebooks in the list.
          notebooks       Classified notebook list (each enriched by classify_notebook).
          nb_intel        Per-key section: uuid, source_count, titles list, near_cap.
    """
    classified = [classify_notebook(nb, near_cap_threshold) for nb in notebooks]

    nb_intel_section: dict[str, dict] = {}
    for key, sources in nb_intel_sources.items():
        count = len(sources)
        nb_intel_section[key] = {
            "uuid": NB_INTEL[key],
            "source_count": count,
            "titles": [s.get("title", "") for s in sources],
            "near_cap": count >= near_cap_threshold,
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notebook_count": len(classified),
        "notebooks": classified,
        "nb_intel": nb_intel_section,
    }


# ── Redaction (fail closed) ────────────────────────────────────────────────────

def load_title_redactor(path: Path = REDACT_PII_PATH) -> Any:
    """The repo redactor with static rules, or None if it cannot load (logged)."""
    try:
        spec = importlib.util.spec_from_file_location("nuzantara_redact_pii", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no loader for {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module  # dataclasses resolve their module by name
        spec.loader.exec_module(module)
        return module.Redactor.load_static()
    except Exception as e:  # noqa: BLE001 — any failure must end in WITHHELD, not raw
        logger.error("title redactor unavailable, titles withheld: %s: %s", type(e).__name__, e)
        return None


def redact_inventory(inventory: dict, redactor: Any) -> dict:
    """Replace every free-text title in the inventory, in place, and return it.

    Notebook titles go through `redact_notebook_title` (id-aware); NB-INTEL source
    titles (press/regulation headlines) through `redact_fragment`. With no redactor,
    both are withheld: an empty-looking inventory is loud, a raw one is a leak.
    """
    for nb in inventory.get("notebooks", []):
        nid = str(nb.get("id") or "")
        if redactor is None:
            nb["title"] = f"[NB-TITLE-WITHHELD:{nid[:8]}]"
        else:
            nb["title"] = redactor.redact_notebook_title(nb.get("title") or "", nid)
    for section in inventory.get("nb_intel", {}).values():
        section["titles"] = [
            "[SOURCE-TITLE-WITHHELD]" if redactor is None else redactor.redact_fragment(t or "")
            for t in section.get("titles", [])
        ]
    inventory["redaction"] = "withheld" if redactor is None else "applied"
    return inventory


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate live NB inventory JSON for nb-curator brain."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=f"Write JSON to {OUTPUT_PATH}",
    )
    args = parser.parse_args()

    # Step 1: fetch all notebooks (1 nlm call)
    logger.info("Fetching notebook list from nlm...")
    try:
        notebooks = fetch_notebooks()
    except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        logger.error("nlm notebook list error: %s", e)
        return 3

    logger.info("Got %d notebooks", len(notebooks))

    # Step 2: fetch sources for each NB-INTEL (5 nlm calls)
    nb_intel_sources: dict[str, list[dict]] = {}
    for key, uuid in NB_INTEL.items():
        logger.info("Fetching sources for NB-INTEL-%s (%s)...", key, uuid)
        try:
            nb_intel_sources[key] = fetch_sources(uuid)
            logger.info("  -> %d sources", len(nb_intel_sources[key]))
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.error("nlm source list error for %s (%s): %s", key, uuid, e)
            return 3

    # Step 3: build inventory (pure), then redact titles before anything reads it
    inventory = redact_inventory(build_inventory(notebooks, nb_intel_sources), load_title_redactor())

    # Step 4: optionally write JSON
    written = False
    if args.write:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT_PATH.open("w", encoding="utf-8") as f:
            json.dump(inventory, f, indent=2, ensure_ascii=False)
            f.write("\n")
        written = True
        size = OUTPUT_PATH.stat().st_size
        logger.info("Written %d bytes to %s", size, OUTPUT_PATH)

    # Step 5: print one-line JSON summary to stdout (for wrapper log parsing)
    print(json.dumps({
        "notebooks": len(notebooks),
        "nb_intel": len(NB_INTEL),
        "written": written,
        "redaction": inventory["redaction"],
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
