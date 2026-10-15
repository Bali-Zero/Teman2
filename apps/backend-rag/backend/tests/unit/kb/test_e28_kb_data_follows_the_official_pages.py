"""The E28 rows Zantara and the MCP read from the knowledge stores say only what the
official Imigrasi pages say (PR C2, audit `research/visa/2026-10-15-e28-family-audit.md`
F40-F44 Qdrant, F70-F74 `visa_types`).

Four surfaces are pinned, each by ENTITY (a figure, a row, a point), never by a substring
of prose alone:

  1. `migration_128_fix_e28_family_rows.py` VISA_FIXES — every USD/IDR figure written into
     an E28A/B/C/D/F row must exist in that product's saved page text
     (`research/visa/2026-10-15-e28-pages/`), and the tier figures each page states must be
     present once.
  2. The seed script carries the same name/duration/cost/requirements, so a seed re-run
     cannot re-introduce the drift.
  3. `scripts/enrich_visa_oracle_stay_rules.py` (the source of the Qdrant text) has no E28G
     entry and no unsourced claim.
  4. `scripts/fix_visa_oracle_e28_points.py` against a FAKE Qdrant (httpx MockTransport, no
     network): dry-run changes nothing, apply is refused without a backup, apply issues
     exactly the intended set_payload / delete calls, a second run is a no-op, nothing ever
     reaches an embeddings endpoint, no vector is written, and a point that is not what we
     expect makes the whole run refuse.

Guilt AND innocence: every forbidden-phrase check is also run against the PROD "before"
text (must trip) and against legitimate neighbours (must not).
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
import os
import re
import stat
import sys
from pathlib import Path

import httpx
import pytest


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "apps").is_dir() and (p / "scripts").is_dir():
            return p
        p = p.parent
    raise AssertionError("repo root not found")


ROOT = _repo_root()
MIG_PATH = ROOT / "apps/backend-rag/backend/migrations/migration_128_fix_e28_family_rows.py"
SEED_PATH = ROOT / "apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py"
PAGES = ROOT / "research/visa/2026-10-15-e28-pages"
ENRICH_PATH = ROOT / "scripts/enrich_visa_oracle_stay_rules.py"
FIXER_PATH = ROOT / "scripts/fix_visa_oracle_e28_points.py"

LIVE_CODES = ["E28A", "E28B", "E28C", "E28D", "E28F"]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _literal(path: Path, var: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == var for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{var} not found in {path}")


FIXES: dict = _literal(MIG_PATH, "VISA_FIXES")
SEED = {e["code"]: e for e in _literal(SEED_PATH, "VISA_TYPES")}


# ---- page figures ----------------------------------------------------------------

_FIG = re.compile(r"(US\$|USD|Rp\.?)\s*(\d[\d.,]*)")


def figures(text: str) -> set[tuple[str, int]]:
    """(currency, integer amount) for every money figure in the text; USD == US$."""
    out: set[tuple[str, int]] = set()
    for cur, raw in _FIG.findall(text):
        raw = raw.rstrip(".,")
        raw = re.sub(r",00$", "", raw)
        digits = re.sub(r"[.,]", "", raw)
        if digits:
            out.add(("USD" if cur.startswith(("US", "USD")) else "IDR", int(digits)))
    return out


def page_text(code: str) -> str:
    for line in (PAGES / "e28-pages.receipts.jsonl").read_text().splitlines():
        rec = json.loads(line)
        if rec["key_phrase"] == code:
            files = list((PAGES / "text").glob(f"{rec['source_record_id'][:8]}-*.txt"))
            assert len(files) == 1, f"{code}: expected exactly one saved page, got {files}"
            return files[0].read_text(encoding="utf-8")
    raise AssertionError(f"no receipt for {code}")


def row_strings(row: dict) -> list[str]:
    out: list[str] = []
    for val in row.values():
        if isinstance(val, str):
            out.append(val)
        elif isinstance(val, list):
            out.extend(v for v in val if isinstance(v, str))
    return out


# What PROD served before this PR (quoted from the live read, 2026-10-15).
PROD_BEFORE = {
    "E28A": [
        "17.000.000 - 19.000.000 IDR",
        "Passport photo 4x6 red background",
        "Return/onward ticket",
    ],
    "E28B": ["Investasi minimal Rp 2.5 miliar", "Golden Visa 5 tahun", "Wajib maintain investasi"],
    "E28C": ["Dilarang bekerja", "Tidak perlu mendirikan PT PMA"],
    "E28G": ["Golden Visa 10 tahun", "Investasi Rp 5 miliar+"],
    "E28F-point": ["Investor Real Estate (IKN Nusantara or property-based). Threshold Rp 5 billion+ property."],
}

FORBIDDEN = [
    r"Rp\s?2\.5\s+miliar",
    r"Rp\s?5\s+(miliar|billion)",
    r"Return/onward ticket",
    r"4x6 red background",
    r"Golden Visa (5|10)\s?(Y|tahun)",
    r"Dilarang bekerja",
    r"Wajib maintain investasi",
    r"\d[\d.]*\s*-\s*\d[\d.]*\s*IDR",  # a price range
    r"Real Estate",
    r"Branch/Representative",
]


def forbidden_hits(texts: list[str]) -> list[str]:
    return [pat for pat in FORBIDDEN for t in texts if re.search(pat, t)]


# ---- 1. migration values vs the saved pages ---------------------------------------


def test_the_forbidden_matcher_trips_on_every_prod_before_text_and_spares_the_new_one():
    for label, texts in PROD_BEFORE.items():
        assert forbidden_hits(texts), f"matcher is blind to the PROD before text of {label}"
    # innocence: legitimate neighbours must not trip
    assert not forbidden_hits(["US$2.500.000 (masa tinggal 5 tahun)", "Rp10.000.000.000", "IDR 17.000.000 (offshore) / IDR 19.000.000 (onshore)"])


@pytest.mark.parametrize("code", LIVE_CODES)
def test_every_money_figure_written_into_a_row_is_on_that_products_page(code):
    row = FIXES[code]
    # cost_visa is the catalogue price, not a page figure (the page lists PNBP, which is never shown)
    texts = [v for k, v in row.items() if k != "cost_visa" for v in ([v] if isinstance(v, str) else v or [])]
    written = figures(" ".join(t for t in texts if isinstance(t, str)))
    on_page = figures(page_text(code))
    assert written, f"{code}: row states no threshold at all"
    assert written <= on_page, f"{code}: figures not on the page: {sorted(written - on_page)}"


@pytest.mark.parametrize(
    "code,expected",
    [
        ("E28A", {("IDR", 10_000_000_000), ("USD", 2000)}),
        ("E28B", {("USD", 2_500_000), ("USD", 5_000_000)}),
        ("E28C", {("USD", 350_000), ("USD", 700_000), ("USD", 1_000_000)}),
        ("E28D", {("USD", 25_000_000), ("USD", 50_000_000)}),
        ("E28F", {("USD", 5_000_000), ("USD", 10_000_000)}),
    ],
)
def test_the_tier_figures_each_page_states_are_on_the_page_and_in_the_row_exactly_once(code, expected):
    page = figures(page_text(code))
    assert expected <= page, f"{code}: the saved page no longer carries {sorted(expected - page)}"
    reqs = FIXES[code]["requirements"]
    for cur, amount in expected:
        hits = [r for r in reqs if (cur, amount) in figures(r)]
        assert hits, f"{code}: {cur} {amount} missing from requirements"
        everywhere = [s for s in row_strings(FIXES[code]) if (cur, amount) in figures(s)]
        # bank-statement floor (USD 2,000) appears in the base documents of every row; tiers once
        assert len(everywhere) == 1, f"{code}: {cur} {amount} stated {len(everywhere)} times"


@pytest.mark.parametrize("code", [*LIVE_CODES, "E28G"])
def test_no_e28_row_carries_a_forbidden_claim(code):
    assert forbidden_hits(row_strings(FIXES[code])) == []


def test_e28a_requirements_are_the_pages_documents_and_its_activities_hold_no_documents():
    row = FIXES["E28A"]
    page = page_text("E28A")
    reqs = " | ".join(row["requirements"])
    for needle in ("application letter", "6 months", "3 months", "Curriculum vitae", "Itinerary"):
        assert needle.lower() in reqs.lower(), needle
    assert "surat permohonan penerbitan visa" in page and "daftar riwayat hidup" in page
    for act in row["allowed_activities"]:
        assert not re.search(r"proof|bank|statement|decree|passport|photo", act, re.I), act
    assert row["duration"] == "2 years"
    assert row["processing_time_normal"] == "7-10 working days"


def test_e28a_cost_is_two_labelled_prices_not_a_range():
    cost = FIXES["E28A"]["cost_visa"]
    assert "17.000.000" in cost and "19.000.000" in cost
    assert re.search(r"17\.000\.000 \(offshore\)", cost) and re.search(r"19\.000\.000 \(onshore\)", cost)
    assert not re.search(r"17\.000\.000\s*[-–]\s*(IDR\s*)?19\.000\.000", cost)
    for code in ("E28B", "E28C", "E28D", "E28F"):
        assert FIXES[code]["cost_visa"] == "Contact for Quote"


def test_no_row_shows_a_pnbp_amount():
    pnbp = {("IDR", 13_000_000), ("IDR", 19_500_000), ("IDR", 7_000_000), ("IDR", 9_500_000)}
    for code, row in FIXES.items():
        assert not (figures(" ".join(row_strings(row))) & pnbp), code


def test_e28b_and_e28c_names_follow_the_page_titles():
    assert FIXES["E28B"]["name"] == "E28B - Investor Golden Visa (Company Establishment)"
    assert FIXES["E28C"]["name"] == "E28C - Investor Golden Visa (Capital Market)"
    assert "Pasar Modal" in page_text("E28C") and "Pendirian Perusahaan" in page_text("E28B")


def test_e28g_is_rewritten_as_not_a_current_visa_with_no_threshold():
    row = FIXES["E28G"]
    assert "not a current visa" in row["name"].lower()
    text = " ".join(row_strings(row))
    assert "E28B" in text and "E28C" in text
    assert not figures(text)
    assert row["allowed_activities"] == [] and row["restrictions"] == [] and row["tips"] == []
    assert row["process_steps"] == [] and row["benefits"] == []


def test_the_migration_only_ever_updates_by_code_and_is_idempotent_against_an_in_memory_table(monkeypatch):
    mig = _load(MIG_PATH, "migration_128_under_test")
    rows = {code: {"code": code, "name": f"old {code}"} for code in FIXES}
    queries: list[str] = []

    class FakeConn:
        async def fetchrow(self, query, *values):
            queries.append(query)
            assert query.strip().startswith("UPDATE visa_types"), query
            assert "DELETE" not in query.upper() and "INSERT" not in query.upper()
            sets = dict(re.findall(r"(\w+) = \$(\d+)", query.split("WHERE")[0]))
            code = values[-1]
            row = rows[code]
            new = {f: values[int(i) - 1] for f, i in sets.items()}
            if all(row.get(f, object()) == v for f, v in new.items()):
                return None  # IS DISTINCT FROM guard: nothing differs
            row.update(new)
            return {"code": code, "name": row.get("name")}

        async def fetchval(self, query, code):
            return 1 if code in rows else None

        async def close(self):
            pass

    async def fake_connect(url):
        return FakeConn()

    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/fake")
    monkeypatch.setattr(mig.asyncpg, "connect", fake_connect)
    assert asyncio.run(mig.run_migration()) is True
    first = {c: dict(r) for c, r in rows.items()}
    for code, fix in FIXES.items():
        for field, value in fix.items():
            assert first[code][field] == value
    n = len(queries)
    assert asyncio.run(mig.run_migration()) is True
    assert {c: dict(r) for c, r in rows.items()} == first
    assert len(queries) == 2 * n


def test_the_migration_reports_a_missing_row_as_failure(monkeypatch):
    mig = _load(MIG_PATH, "migration_128_missing_row")

    class FakeConn:
        async def fetchrow(self, query, *values):
            return None

        async def fetchval(self, query, code):
            return None

        async def close(self):
            pass

    async def fake_connect(url):
        return FakeConn()

    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/fake")
    monkeypatch.setattr(mig.asyncpg, "connect", fake_connect)
    assert asyncio.run(mig.run_migration()) is False


# ---- 2. seed in sync --------------------------------------------------------------


@pytest.mark.parametrize("code", sorted(FIXES))
def test_the_seed_carries_the_same_values_the_migration_writes(code):
    seed = SEED[code]
    for field in ("name", "duration", "cost_visa", "requirements"):
        if field in FIXES[code]:
            assert seed[field] == FIXES[code][field], f"{code}.{field}: seed drifts from migration_128"
    assert forbidden_hits(row_strings(seed)) == []


def test_the_seed_does_not_describe_e28g_as_a_product():
    text = " ".join(row_strings(SEED["E28G"]))
    assert "Parent Company Representative" not in text and "Perwakilan Perusahaan Induk" not in text


# ---- 3. the Qdrant text source ------------------------------------------------------


@pytest.fixture(scope="module")
def src():
    return _load(ENRICH_PATH, "_enrich_src_under_test")


def test_the_enrichment_source_has_no_e28g_and_no_unsourced_e28_claim(src):
    assert "E28G" not in src.RULES
    for doc in src.CONCEPT_DOCS:
        assert "E28G" not in doc["text"]
    notes = [src.RULES[c].notes or "" for c in LIVE_CODES]
    assert forbidden_hits(notes) == []
    assert not any("KITAP threshold" in n or "Pasal 176" in n for n in notes)
    kitap_concept = next(d for d in src.CONCEPT_DOCS if d["concept_id"] == "nb2-kitap-conversion")
    assert "Golden Visa" not in kitap_concept["text"]


@pytest.mark.parametrize("code", LIVE_CODES)
def test_the_stated_stay_claims_are_neutral_where_the_page_is_silent(src, code):
    rule = src.RULES[code]
    assert rule.extension_days == 0 and rule.max_total_days == 0
    assert rule.kitap_eligible is None and rule.kitap_years_required is None
    block = src.build_stay_section(rule)
    assert "730" not in block.replace("730 days (2 years)", "") and "Max total stay" not in block
    assert "not stated on the official Imigrasi page" in block


def test_e28a_keeps_its_two_year_stay_and_the_figures_in_each_note_are_on_the_page(src):
    assert src.RULES["E28A"].initial_days == 730
    for code in LIVE_CODES:
        assert figures(src.RULES[code].notes) <= figures(page_text(code)), code


def test_the_stay_block_replacement_is_idempotent_and_touches_nothing_outside_it(src):
    before = "# E28B\n\nIntro line.\n\n## KITAS Duration, Renewal & KITAP Path\n\n- old\n\n**Legal basis**: x\n\n## Base Legale\n\nUntouched tail.\n\n## Procedural Notes (Indonesia Immigration 2024-2026)\n\nkeep me\n"
    once = src.replace_stay_block(before, src.RULES["E28B"])
    assert once.startswith("# E28B\n\nIntro line.") and once.endswith("## Base Legale\n\nUntouched tail.\n\n## Procedural Notes (Indonesia Immigration 2024-2026)\n\nkeep me\n")
    assert src.replace_stay_block(once, src.RULES["E28B"]) == once
    assert "USD 2,500,000" in once and "- old" not in once


# ---- 4. the payload-only fixer against a fake Qdrant ---------------------------------

OLD_NOTES = {
    "E28A": "Investor in existing PT PMA. KITAS threshold: Rp 10 billion shares. KITAP threshold INCREASED to Rp 15 billion (Pasal 176(2)(c)).",
    "E28B": "Golden Visa Founder - PT PMA founder. USD 2.5M (5y) or USD 5M (10y) paid-up capital within 90 days. Direct KITAP-INV after 5y (no language test). 10y variant also requires proof of prior Indonesia entry.",
    "E28C": "Golden Visa Portfolio Investor - no company setup. USD 350k (5y) or USD 700k (10y).",
    "E28D": "Investor Branch/Representative Office. Parent company commits USD 25M (5y) or USD 50M (10y).",
    "E28F": "Investor Real Estate (IKN Nusantara or property-based). Threshold Rp 5 billion+ property.",
}
TAIL = "\n\n## Base Legale\n\nUntouched tail.\n\n## Procedural Notes (Indonesia Immigration 2024-2026)\n\nkeep me\n"
SECRET = "sk-test-qdrant-key-DO-NOT-PRINT"
URL = "https://qdrant.invalid:6333"


def _old_point(fx, code):
    text = (
        f"# {code}\n\nIntro for {code}.\n\n## KITAS Duration, Renewal & KITAP Path\n\n"
        f"- **Initial stay**: 730 days (2 years)\n- **KITAP conversion**: eligible after 3 consecutive years\n\n"
        f"**Legal basis**: Permenkumham 11/2024 Pasal 38-40\n\n**Operational notes**: {OLD_NOTES[code]}\n"
        + TAIL
    )
    meta = {"code": code, "stay_extension_days": 730, "kitap_eligible": True, "kitap_years_required": 3, "keep": "me"}
    return {"id": fx.CODE_POINTS[code], "payload": {"text": text, "metadata": meta}, "vector": {"dense": [0.1, 0.2]}}


def _old_concept(fx, src):
    new = next(d for d in src.CONCEPT_DOCS if d["concept_id"] == fx.CONCEPT_ID)["text"].strip()
    a = "- **E31A spouse of WNI**"
    b = "- NB-2 has no documented age-based exemption"
    assert a in new and b in new
    old = new.replace(a, "- **E28B/E28G Golden Visa**: direct KITAP-INV after 5 years (skip language test, maintain investment)\n" + a)
    old = old.replace(b, "- Exemption: Golden Visa investors (E28B, E28G)\n" + b)
    return {"id": fx.CONCEPT_POINT_ID, "payload": {"text": old, "metadata": {"code": fx.CONCEPT_CODE, "k": 1}}, "vector": {"dense": [0.3]}}


class FakeQdrant:
    def __init__(self, fx, src, *, ghost=True):
        self.points = {p["id"]: p for p in (_old_point(fx, c) for c in LIVE_CODES)}
        self.points[fx.CONCEPT_POINT_ID] = _old_concept(fx, src)
        if ghost:
            self.points[fx.E28G_POINT_ID] = {
                "id": fx.E28G_POINT_ID,
                "payload": {"text": "ghost", "metadata": {"code": "E28G"}},
                "vector": {"dense": [0.9]},
            }
        self.log: list[tuple[str, str, dict]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        path = request.url.path
        self.log.append((request.url.host, path, body))
        assert request.headers["api-key"] == SECRET
        if path == "/collections/visa_oracle/points":
            res = []
            for pid in body["ids"]:
                if pid in self.points:
                    p = self.points[pid]
                    item = {"id": pid, "payload": json.loads(json.dumps(p["payload"]))}
                    if body.get("with_vector"):
                        item["vector"] = p["vector"]
                    res.append(item)
            return httpx.Response(200, json={"result": res})
        if path == "/collections/visa_oracle/points/payload":
            for pid in body["points"]:
                self.points[pid]["payload"].update(body["payload"])
            return httpx.Response(200, json={"result": {"status": "completed"}})
        if path == "/collections/visa_oracle/points/delete":
            for pid in body["points"]:
                self.points.pop(pid, None)
            return httpx.Response(200, json={"result": {"status": "completed"}})
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    def writes(self):
        return [(p, b) for _, p, b in self.log if p.endswith(("/payload", "/delete"))]


@pytest.fixture(scope="module")
def fx():
    return _load(FIXER_PATH, "_fixer_under_test")


def _run(fx, fake, argv, capsys):
    def factory(u, k):
        return httpx.Client(base_url=u, headers={"api-key": k}, transport=httpx.MockTransport(fake.handler))

    code = fx.main(argv, client_factory=factory, env={"QDRANT_URL": URL, "QDRANT_API_KEY": SECRET})
    out = capsys.readouterr()
    return code, out.out, out.err


def test_the_fixer_point_ids_are_the_prod_ids_and_the_concept_id_is_its_uuid5(fx):
    import uuid

    assert str(uuid.uuid5(uuid.NAMESPACE_URL, "nb2-concept:nb2-kitap-conversion")) == fx.CONCEPT_POINT_ID
    assert fx.CODE_POINTS["E28A"].startswith("762c2f04") and fx.E28G_POINT_ID.startswith("225aed53")


def test_dry_run_prints_before_after_per_point_and_writes_nothing(fx, src, capsys):
    fake = FakeQdrant(fx, src)
    code, out, err = _run(fx, fake, [], capsys)
    assert code == 0 and fake.writes() == []
    for pid in [*fx.CODE_POINTS.values(), fx.CONCEPT_POINT_ID, fx.E28G_POINT_ID]:
        assert pid in out
    assert "7 change(s) planned (dry-run)" in out
    assert "Threshold Rp 5 billion+ property" in out and "metadata.kitap_eligible: True -> '<absent>'" in out
    assert SECRET not in out + err and "qdrant.invalid" not in out + err
    import logging

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING  # no request-URL logging


def test_apply_without_backup_is_refused_before_any_request(fx, src, capsys):
    fake = FakeQdrant(fx, src)
    code, out, err = _run(fx, fake, ["--apply"], capsys)
    assert code == 2 and fake.log == [] and "--backup" in err


def test_apply_issues_exactly_the_intended_calls_with_a_0600_backup_and_no_vector(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    backup = tmp_path / "backup.json"
    before = {pid: json.loads(json.dumps(p)) for pid, p in fake.points.items()}
    code, out, err = _run(fx, fake, ["--apply", "--backup", str(backup)], capsys)
    assert code == 0, err
    assert stat.S_IMODE(os.stat(backup).st_mode) == 0o600
    saved = json.loads(backup.read_text())["points"]
    assert {p["id"] for p in saved} == set(before) and all("vector" in p for p in saved)
    writes = fake.writes()
    sets = [b["points"][0] for p, b in writes if p.endswith("/payload")]
    dels = [b["points"][0] for p, b in writes if p.endswith("/delete")]
    assert sorted(sets) == sorted([*fx.CODE_POINTS.values(), fx.CONCEPT_POINT_ID])
    assert dels == [fx.E28G_POINT_ID] and len(writes) == 7
    for _p, b in writes:
        assert "vector" not in json.dumps(b), "a vector was written"
    assert fx.E28G_POINT_ID not in fake.points
    for pid, p in fake.points.items():  # vectors untouched
        assert p["vector"] == before[pid]["vector"]
    # content: new notes in, old claims out, rest of the text byte-identical
    e28f = fake.points[fx.CODE_POINTS["E28F"]]["payload"]
    assert "Real Estate" not in e28f["text"] and "IKN" in e28f["text"] and "USD 10,000,000" in e28f["text"]
    assert e28f["text"].endswith(TAIL) and e28f["text"].startswith("# E28F\n\nIntro for E28F.\n\n")
    assert "kitap_eligible" not in e28f["metadata"] and e28f["metadata"]["keep"] == "me"
    assert fake.points[fx.CODE_POINTS["E28A"]]["payload"]["metadata"]["stay_extension_days"] == 0
    assert "Direct KITAP" not in fake.points[fx.CODE_POINTS["E28B"]]["payload"]["text"]
    concept = fake.points[fx.CONCEPT_POINT_ID]["payload"]
    assert "E28G" not in concept["text"] and concept["metadata"] == {"code": fx.CONCEPT_CODE, "k": 1}
    assert "verified: re-read shows 0 pending changes" in out
    assert SECRET not in out + err


def test_a_second_run_is_a_no_op(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    _run(fx, fake, ["--apply", "--backup", str(tmp_path / "b1.json")], capsys)
    n = len(fake.writes())
    code, out, err = _run(fx, fake, ["--apply", "--backup", str(tmp_path / "b2.json")], capsys)
    assert code == 0 and "0 change(s) planned" in out
    assert len(fake.writes()) == n


def test_the_fixer_never_reaches_an_embeddings_endpoint_or_any_other_host(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    _run(fx, fake, ["--apply", "--backup", str(tmp_path / "b.json")], capsys)
    assert {h for h, _, _ in fake.log} == {"qdrant.invalid"}
    assert not any("embed" in p or "openai" in p for _, p, _ in fake.log)
    source = FIXER_PATH.read_text()
    assert "embed_dense" not in source and "OPENAI" not in source.replace("OPENAI/embedding", "")


def test_a_point_that_is_not_what_we_expect_refuses_the_whole_run(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    fake.points[fx.CODE_POINTS["E28D"]]["payload"]["metadata"]["code"] = "E28X"
    code, out, err = _run(fx, fake, ["--apply", "--backup", str(tmp_path / "b.json")], capsys)
    assert code == 3 and fake.writes() == [] and "REFUSED" in err and not (tmp_path / "b.json").exists()


def test_drift_outside_the_e28_lines_in_the_concept_note_refuses(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    fake.points[fx.CONCEPT_POINT_ID]["payload"]["text"] += "\n- someone edited an unrelated line"
    code, _, err = _run(fx, fake, ["--apply", "--backup", str(tmp_path / "b.json")], capsys)
    assert code == 3 and fake.writes() == [] and "unexpected drift" in err


def test_an_e28g_point_with_another_code_is_not_deleted(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    fake.points[fx.E28G_POINT_ID]["payload"]["metadata"]["code"] = "E33G"
    code, _, err = _run(fx, fake, ["--apply", "--backup", str(tmp_path / "b.json")], capsys)
    assert code == 3 and fx.E28G_POINT_ID in fake.points and fake.writes() == []


def test_an_existing_backup_file_is_never_overwritten(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    b = tmp_path / "b.json"
    b.write_text("precious")
    with pytest.raises(FileExistsError):
        _run(fx, fake, ["--apply", "--backup", str(b)], capsys)
    assert b.read_text() == "precious" and fake.writes() == []


def test_missing_credentials_refuse_without_a_request(fx, capsys):
    code = fx.main([], env={})
    assert code == 2
