#!/usr/bin/env python3
"""Burn lane 3: TP1 batch port of the Subhi EN->ID article translation.

The canonical pipeline (scripts/translate-articles.py) runs on LOCAL Ollama
(SEA-LION); this runner spends the 2026-10 TP1 quota on the untranslated EN
originals instead, reusing the canonical prompt and frontmatter conventions
verbatim (imported from translate-articles.py, not re-derived).

EN originals are mdx files whose stem carries NO locale dot (codex review
2026-10-05 #4: filtering only *.id.mdx misread .it/.fr/.ru translations as
English originals). Drafts ONLY: output lands in
data/burn_drafts/id_mdx/<rel>.id.mdx, never in the content tree — Subhi/the
canonical pipeline promotes after review (Legge 5 spirit, generator!=grader).

Model follows the window: qwen3.8-max + effort high at night (Night 50% Off),
qwen3.7-plus + effort low by day. Guard: tp1_burn_common.BurnGuard caps,
reserved atomically at submit.
"""
import importlib.util
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deepseek_client import complete, DeepSeekBudgetExceeded  # noqa: E402
from tp1_burn_common import BurnGuard, window_effort, window_model  # noqa: E402

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("translate_articles", _HERE / "translate-articles.py")
ta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ta)

WT = _HERE.parent
ARTICLES = WT / "apps" / "mouth" / "src" / "content" / "articles"
DRAFTS = WT / "data" / "burn_drafts" / "id_mdx"


def strip_wrap_fence(text: str) -> str:
    """Remove ONLY a wrapping code fence, never inner ones (codex review #10)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rstrip()
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()


def discover(limit):
    """EN originals (stem with no locale dot), refreshed as drafts.

    Measured 2026-10-05: every original already carries a .id.mdx target and
    every locale translation has its id sibling — the missing-file backlog is
    ZERO. The canonical pipeline's real work is FRESHNESS (re-translate when
    the EN source moves), so this burn lane refreshes ALL originals as drafts;
    Subhi/the canonical pipeline promotes the better ones after review.
    """
    todo = []
    for en in sorted(ARTICLES.rglob("*.mdx")):
        if "." in en.stem:  # locale-suffixed translation (.id/.it/.fr/.ru), not an original
            continue
        rel = en.relative_to(ARTICLES)
        draft = DRAFTS / rel.with_name(rel.stem + ".id.mdx")
        if draft.exists():
            continue
        todo.append(en)
        if limit and len(todo) >= limit:
            break
    return todo


def translate_one(en: Path, guard):
    text = en.read_text(encoding="utf-8")
    fm, body = ta.split_frontmatter(text)
    if not body.strip():
        return en, None, "empty body"
    prompt = ta.TRANSLATION_PROMPT.format(lang_name="Indonesian", content=body)
    for attempt in range(3):
        if not guard.ok():
            return en, None, "guard"
        model = window_model()
        try:
            result = complete(
                prompt,
                model=model,
                reasoning_effort=window_effort(),
                timeout=900,
                purpose="burn-translate-id",
            )
            guard.add(result.usage)
            out = strip_wrap_fence(result.text)
            if not out:
                raise ValueError("empty translation")
            if fm:
                out = ta.patch_frontmatter_locale(fm, "id") + out
            return en, out, model
        except DeepSeekBudgetExceeded:
            raise
        except Exception:
            if attempt == 2:
                return en, None, "api/parse fail"
            guard.add_attempt()
            time.sleep(1.5 * (attempt + 1))
    return en, None, "unreachable"


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    workers = int(os.environ.get("BURN_WORKERS", "16"))
    guard = BurnGuard()
    todo = discover(args.limit)
    DRAFTS.mkdir(parents=True, exist_ok=True)
    print(f"burn-translate-id: {len(todo)} untranslated originals, workers={workers} "
          f"cap={guard.stats()}", flush=True)

    done = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = set()
        for en in todo:
            if not guard.reserve():
                print("burn guard cap reached — stopping submission", flush=True)
                break
            futs.add(ex.submit(translate_one, en, guard))
        for f in as_completed(futs):
            if f.cancelled():
                continue
            en, out, info = f.result()
            if out:
                rel = en.relative_to(ARTICLES)
                draft = DRAFTS / rel.with_name(rel.stem + ".id.mdx")
                draft.parent.mkdir(parents=True, exist_ok=True)
                draft.write_text(out + "\n", encoding="utf-8")
                done += 1
            else:
                failed += 1
            if (done + failed) % 25 == 0:
                print(f"  {done + failed}/{len(todo)} | ok={done} fail={failed} | "
                      f"{guard.stats()}", flush=True)
            if not guard.ok():
                pending = sum(1 for p in futs if p.cancel())
                print(f"burn guard cap reached mid-run — cancelled {pending} pending, "
                      f"draining running", flush=True)
    print(f"DONE burn-translate-id: ok={done} fail={failed} | {guard.stats()} "
          f"-> {DRAFTS}", flush=True)


if __name__ == "__main__":
    main()
