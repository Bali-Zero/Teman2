#!/usr/bin/env python3
"""lint_public_asset_refs.py — CI antidote for "the code names a static asset
that was never in public/" (2026-08-07, found while answering a question about
a DIFFERENT page).

THE DISEASE: `apps/mouth/src/app/kbli/page.tsx` shipped
`<video src="/videos/kbli-demo.mp4" autoPlay loop playsInline controls>` inside
the tablet mock-up of the KBLI landing hero. `public/videos/` (PLURAL) has never
existed — the only real directory is `public/video/` (SINGULAR). One letter. On
Vercel a missing static path does not 404 loudly: it falls through to the app
router and answers **HTTP 200 with `content-type: text/html`**, so every probe
that stops at the status code reads "fine". Production served a broken player,
with visible controls, on the flagship product's landing page, and no gate saw
it. A second instance (`/videos/kbli-logo-puzzle.mp4`) sat in a component with
zero importers — same defect, invisible because the component never rendered.

This is superscar #2 (esiste ≠ armato) pointed at static assets: the ASSERTING
organ (a `src=` in JSX) and the KNOWING organ (the filesystem under public/) are
different organs with no nerve between them. Nothing re-checks the reference
after the asset is renamed, moved, or never committed in the first place.

THE ANTIDOTE: for each configured (src root, public root) pair, scan code files
for LITERAL string paths that carry an asset extension and FAIL when the file is
absent from the public root.

DECLARED LIMIT (a guard that overstates its reach is worse than a narrow one):
this sees only **literal** string paths — `"/video/x.mp4"`, `'/images/y.png'`,
`` `/assets/z.svg` `` with no interpolation. Paths built at runtime
(`` `/covers/${slug}.jpg` ``, `path.join(...)`, values from a CMS or the DB) are
invisible to it and always will be. It also does not read `.mdx` content. Both
gaps are stated here so nobody reads a green run as "every asset reference in
the app is proven".

FALSE-POSITIVE DISCIPLINE (superscar #3: no guard without guilt AND innocence):
three classes are excluded by config, each for a reason, not for convenience —
  1. `exclude_path_globs` — test and type-declaration files. A fixture that
     writes `/broken.png` on purpose to prove a fallback renders is not a defect;
     flagging it would train people to delete honest tests.
  2. `framework_served` — paths Next.js serves from the `app/` file convention
     (`app/favicon.ico`, `app/robots.ts` → `/robots.txt`, `app/sitemap.ts` →
     `/sitemap.xml`). These are absent from public/ BY DESIGN and are verified
     live (HTTP 200) before being listed.
  3. `ignore_prefixes` — build output and API routes, never public/ files.

KNOWN-MISSING REGISTRY (monotone, shrink-only): `known_missing` carries
references that are genuinely broken today but whose cure is not this PR's
scope. It is NOT an exemption list, and the lint keeps it honest in both
directions:
  - anything missing and NOT registered → exit 1 (the gate's job);
  - a registered entry that is no longer missing, or no longer referenced by any
    code file → exit 1 as STALE, so the registry can only shrink. An
    allow-list nobody prunes becomes the place defects go to die quietly.
  (Caveat, W109b: two concurrent PRs that each shrink this registry will each
  look like GROWTH from the other's base. Merge main and re-derive; there is no
  textual conflict for git to flag.)

Exit codes: 0 = clean · 1 = missing reference(s) or stale registry entry ·
4 = operational error (config unreadable, or a configured root matched ZERO
code files — a scan that scanned nothing is not "clean", W84 discipline:
fail-visible on blind scans rather than silent-pass).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "infra" / "asset-lint" / "public-asset-refs-config.json"

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_OPERATIONAL = 4


def load_config(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(_operational(f"config unreadable at {path}: {exc}"))


def _operational(msg: str) -> int:
    print(f"lint_public_asset_refs: OPERATIONAL ERROR — {msg}", file=sys.stderr)
    return EXIT_OPERATIONAL


def build_pattern(extensions: list[str]) -> re.Pattern[str]:
    """Literal quoted paths ending in a configured asset extension.

    The closing-quote requirement is load-bearing: it is what keeps a path
    MENTIONED in prose (a code comment explaining why an asset was removed)
    from being read as a reference. A quoted path inside a comment IS still
    matched — deliberately: quoting it makes it indistinguishable from code,
    and the honest fix there is to unquote the prose.
    """
    ext = "|".join(re.escape(e.lstrip(".")) for e in extensions)
    return re.compile(
        r"""["'`](/[^"'`\s{}$]*\.(?:""" + ext + r"""))(?:[?#][^"'`]*)?["'`]""",
        re.IGNORECASE,
    )


def is_excluded(rel_path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel_path, g) for g in globs)


def scan_root(
    repo_root: Path, root_cfg: dict[str, str], cfg: dict[str, Any]
) -> tuple[dict[str, list[str]], int, int]:
    """Return ({asset_path: [referencing files]}, candidates, scanned).

    `candidates` counts files matching the configured suffixes BEFORE exclusion;
    `scanned` counts what survived it. The blind-scan guard (W84) keys off
    `candidates`, because the failure it exists to catch is "the root or the
    suffix list is wrong", not "this directory happens to hold only tests" —
    keying it off `scanned` would turn a legitimate all-excluded tree into a
    spurious operational error. Found by the corpus, not by review.
    """
    src_root = repo_root / root_cfg["src"]
    public_root = repo_root / root_cfg["public"]
    suffixes = tuple(cfg["code_suffixes"])
    exclude = cfg.get("exclude_path_globs", [])
    ignore_prefixes = tuple(cfg.get("ignore_prefixes", []))
    framework = set(cfg.get("framework_served", []))
    pattern = build_pattern(cfg["asset_extensions"])

    missing: dict[str, list[str]] = {}
    candidates = 0
    scanned = 0

    for path in sorted(src_root.rglob("*")):
        if not path.is_file() or not path.name.endswith(suffixes):
            continue
        candidates += 1
        rel = path.relative_to(repo_root).as_posix()
        if is_excluded(rel, exclude):
            continue
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in pattern.finditer(text):
            url = match.group(1)
            if url.startswith("//") or url.startswith(ignore_prefixes):
                continue
            if url in framework:
                continue
            if (public_root / url.lstrip("/")).is_file():
                continue
            missing.setdefault(url, [])
            if rel not in missing[url]:
                missing[url].append(rel)

    return missing, candidates, scanned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    cfg = load_config(args.config)

    roots = cfg.get("roots") or []
    if not roots:
        return _operational("config declares no roots")

    all_missing: dict[str, list[str]] = {}
    total_scanned = 0
    for root_cfg in roots:
        if not (repo_root / root_cfg["src"]).is_dir():
            return _operational(f"src root absent: {root_cfg['src']}")
        found, candidates, scanned = scan_root(repo_root, root_cfg, cfg)
        if candidates == 0:
            return _operational(
                f"root {root_cfg['src']} matched ZERO code files — "
                "refusing to report a blind scan as clean (W84)"
            )
        total_scanned += scanned
        for url, refs in found.items():
            all_missing.setdefault(url, []).extend(refs)

    known = {entry["path"]: entry for entry in cfg.get("known_missing", [])}
    unregistered = {u: r for u, r in all_missing.items() if u not in known}
    stale = sorted(set(known) - set(all_missing))

    if args.json:
        print(
            json.dumps(
                {
                    "scanned": total_scanned,
                    "missing": all_missing,
                    "unregistered": unregistered,
                    "stale_registry_entries": stale,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"lint_public_asset_refs: scanned {total_scanned} code file(s)")
        if unregistered:
            print(f"\nMISSING from public/ and NOT registered ({len(unregistered)}):")
            for url in sorted(unregistered):
                print(f"  {url}")
                for ref in sorted(unregistered[url]):
                    print(f"      ← {ref}")
        if stale:
            print(f"\nSTALE known_missing entries ({len(stale)}) — remove them:")
            for url in stale:
                print(f"  {url}  (no longer missing, or no longer referenced)")
        registered = len(known) - len(stale)
        if registered:
            print(
                f"\n{registered} known-missing reference(s) still open "
                "— real defects carried in the registry, not exemptions."
            )
        if not unregistered and not stale:
            print("\nOK — every unregistered literal asset reference exists in public/.")

    return EXIT_FINDINGS if (unregistered or stale) else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
