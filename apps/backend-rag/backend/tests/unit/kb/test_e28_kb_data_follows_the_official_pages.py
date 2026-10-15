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
import copy
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
    # cost_visa is the catalogue price, not a page figure: bound separately below
    texts = [v for k, v in row.items() if k != "cost_visa" for v in ([v] if isinstance(v, str) else v or [])]
    written = figures(" ".join(t for t in texts if isinstance(t, str)))
    on_page = figures(page_text(code))
    assert written, f"{code}: row states no threshold at all"
    assert written <= on_page, f"{code}: figures not on the page: {sorted(written - on_page)}"


def _bare_numbers(text: str) -> set[int]:
    return {int(n.replace(".", "")) for n in re.findall(r"\d{1,3}(?:\.\d{3})+", text)}


def test_cost_visa_is_exactly_the_ruled_price_and_nothing_else():
    assert _bare_numbers(FIXES["E28A"]["cost_visa"]) == {17_000_000, 19_000_000}
    assert not re.search(r"\d\s*[-\u2013]\s*\d", FIXES["E28A"]["cost_visa"])
    for code in ("E28B", "E28C", "E28D", "E28F"):
        assert FIXES[code]["cost_visa"] == "Contact for Quote"
    for code in ("E28G",):
        assert not _bare_numbers(FIXES[code]["cost_visa"])


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
    assert re.search(r"17\.000\.000 \(Offshore\)", cost) and re.search(r"19\.000\.000 \(Onshore\)", cost)
    assert cost == "IDR 17.000.000 (Offshore) / 19.000.000 (Onshore), all-inclusive"


def test_e28a_activities_are_what_the_page_lists_and_its_steps_hold_no_separate_fee():
    page = page_text("E28A")
    assert "wisata, dan mengunjungi teman" in page and "pembelian barang" not in page.split("Dengan visa ini")[1].split("Jenis visa")[0]
    acts = " ".join(FIXES["E28A"]["allowed_activities"]).lower()
    assert "shopping" not in acts and "tourism and visiting" in acts
    steps = " ".join(FIXES["E28A"]["process_steps"])
    assert not re.search(r"pnbp|bayar biaya|pay the (government )?fee", steps, re.I)
    assert "included in the price" in steps
    assert "90 days from issuance" in steps and "Masa berlaku visa adalah 90 hari" in page
    assert "Re-entry Permit" in steps


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


class PgTx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        self.snap = copy.deepcopy(self.conn.rows)
        return self

    async def __aexit__(self, et, ev, tb):
        if et is not None:
            self.conn.rows = self.snap  # ROLLBACK
        return False


class PgFake:
    """In-memory visa_types that understands exactly the SQL the migration emits."""

    def __init__(self, rows, fail_on=None):
        self.rows = copy.deepcopy(rows)
        self.fail_on = fail_on
        self.executes = 0

    async def set_type_codec(self, *a, **k):
        pass

    async def fetch(self, q, codes):
        assert q.lstrip().startswith("SELECT") and "ANY($1" in q
        return [dict(r) for c, r in self.rows.items() if c in codes]

    def transaction(self):
        return PgTx(self)

    async def execute(self, sql, *values):
        assert sql.startswith("UPDATE visa_types SET") and "DELETE" not in sql.upper()
        self.executes += 1
        code = values[-1]
        assert sql.rstrip().endswith(f"WHERE code = ${len(values)}")
        if code == self.fail_on:
            raise RuntimeError("injected failure")
        row = self.rows[code]
        for f, i in re.findall(r"(\w+) = \$(\d+)(?!::jsonb)", sql.split("WHERE")[0]):
            if f != "metadata":
                row[f] = values[int(i) - 1]
        m = re.search(r"metadata = COALESCE\(.*?\|\| \$(\d+)::jsonb", sql)
        if m:
            row["metadata"] = {**(row.get("metadata") or {}), **values[int(m.group(1)) - 1]}
        return "UPDATE 1"

    async def close(self):
        pass


def _prod_rows(skip=()):
    return {
        c: {"code": c, "name": f"old {c}", "duration": "old", "cost_visa": "old", "requirements": ["old"],
            "restrictions": ["old"], "allowed_activities": ["old"], "benefits": None, "process_steps": ["old"],
            "tips": None, "metadata": {"source": "keep"}, "foreign_eligible": True, "processing_time_normal": "old",
            "extensions": "old", "total_stay": "old", "processing_time_express": "old"}
        for c in FIXES if c not in skip
    }


def _wire(monkeypatch, mig, conn):
    async def fake_connect(url):
        return conn

    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/fake")
    monkeypatch.setattr(mig.asyncpg, "connect", fake_connect)


def test_migration_dry_run_prints_one_preimage_line_and_writes_nothing(monkeypatch, capsys):
    mig = _load(MIG_PATH, "migration_128_dry")
    conn = PgFake(_prod_rows())
    _wire(monkeypatch, mig, conn)
    assert asyncio.run(mig.run_migration()) is True
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.startswith("PREIMAGE ")]
    assert len(lines) == 1 and out.count("\n") == 1, "stdout must carry the preimage line only"
    pre = json.loads(lines[0][len("PREIMAGE "):])
    assert set(pre) == set(FIXES) and pre["E28B"]["name"] == "old E28B"
    assert conn.executes == 0 and conn.rows == _prod_rows()


def test_migration_apply_commits_every_field_and_a_second_apply_is_a_no_op(monkeypatch, capsys):
    mig = _load(MIG_PATH, "migration_128_apply")
    conn = PgFake(_prod_rows())
    _wire(monkeypatch, mig, conn)
    assert asyncio.run(mig.run_migration(apply=True)) is True
    for code, fix in FIXES.items():
        for field, value in fix.items():
            if field == "metadata":
                assert all(conn.rows[code]["metadata"][k] == v for k, v in value.items())
            else:
                assert conn.rows[code][field] == value, (code, field)
    assert conn.rows["E28G"]["metadata"]["source"] == "keep", "metadata is merged, not replaced"
    n = conn.executes
    assert n == len(FIXES)
    assert asyncio.run(mig.run_migration(apply=True)) is True
    assert conn.executes == n
    assert capsys.readouterr().out.count("PREIMAGE ") == 2


def test_an_error_injected_on_e28b_leaves_zero_rows_changed(monkeypatch, capsys):
    mig = _load(MIG_PATH, "migration_128_atomic")
    start = _prod_rows()
    conn = PgFake(start, fail_on="E28B")
    _wire(monkeypatch, mig, conn)
    assert asyncio.run(mig.run_migration(apply=True)) is False
    assert conn.rows == start, "E28A (updated before the failure) must be rolled back too"
    assert conn.executes == 2, "the loop stops at the first error"


def test_the_migration_refuses_when_a_row_is_missing_and_prints_no_preimage(monkeypatch, capsys):
    mig = _load(MIG_PATH, "migration_128_missing_row")
    conn = PgFake(_prod_rows(skip=("E28F",)))
    _wire(monkeypatch, mig, conn)
    assert asyncio.run(mig.run_migration(apply=True)) is False
    assert conn.executes == 0 and "PREIMAGE" not in capsys.readouterr().out


def test_a_post_write_check_that_fails_rolls_everything_back(monkeypatch):
    mig = _load(MIG_PATH, "migration_128_verify")
    start = _prod_rows()
    conn = PgFake(start)
    real = conn.execute

    async def lossy(sql, *values):  # E28D's write silently does not stick
        r = await real(sql, *values)
        if values[-1] == "E28D":
            conn.rows["E28D"]["name"] = "old E28D"
        return r

    conn.execute = lossy
    _wire(monkeypatch, mig, conn)
    assert asyncio.run(mig.run_migration(apply=True)) is False
    assert conn.rows == start


# ---- E28G retirement: the list skips it, the detail lookup still answers --------------


def _router():
    return _load(ROOT / "apps/backend-rag/backend/app/routers/knowledge_visa.py", "_kv_router_under_test")


def test_retired_flag_matcher_guilt_and_innocence():
    r = _router()
    assert r._is_retired({"retired": True}) and r._is_retired('{"retired": true}')
    assert not r._is_retired({"retired": False}) and not r._is_retired({}) and not r._is_retired(None)
    assert not r._is_retired({"retired": "yes"}) and not r._is_retired("not json")
    assert FIXES["E28G"]["metadata"]["retired"] is True
    for code in LIVE_CODES:
        assert not r._is_retired(FIXES[code].get("metadata"))


def _row(code, metadata):
    base = dict.fromkeys(("duration", "extensions", "total_stay", "processing_time_normal",
                          "processing_time_express", "processing_timeline", "cost_visa", "cost_extension",
                          "cost_details", "last_updated", "created_at", "foreign_eligible", "renewable"))
    return {**base, "id": 1, "code": code, "name": code, "category": "KITAS", "metadata": metadata,
            "requirements": [], "restrictions": [], "allowed_activities": [], "benefits": [],
            "process_steps": [], "tips": []}


class _Pool:
    def __init__(self, rows):
        self.rows = rows

    def acquire(self):
        pool = self

        class Ctx:
            async def __aenter__(self):
                return pool

            async def __aexit__(self, *a):
                return False

        return Ctx()

    async def fetch(self, q, *a):
        return self.rows if "FROM visa_types" in q and "DISTINCT" not in q else [{"category": "KITAS"}]

    async def fetchrow(self, q, code):
        return next((r for r in self.rows if r["code"].upper() == code.upper()), None)


def test_the_list_endpoint_skips_retired_rows_and_the_detail_endpoint_still_answers():
    r = _router()
    pool = _Pool([_row("E28A", {}), _row("E28G", FIXES["E28G"]["metadata"]), _row("E28B", None)])
    listed = asyncio.run(r.list_visa_types(category=None, pool=pool))
    assert [i.code for i in listed.items] == ["E28A", "E28B"] and listed.total == 2
    detail = asyncio.run(r.get_visa_by_code("E28G", pool=pool))
    assert detail.code == "E28G" and detail.metadata["retired"] is True


# ---- 2. seed in sync --------------------------------------------------------------


@pytest.mark.parametrize("code", sorted(FIXES))
def test_the_seed_carries_every_field_the_migration_writes(code):
    seed = SEED[code]
    for field, value in FIXES[code].items():
        if field == "metadata":
            assert all(seed["metadata"].get(k) == v for k, v in value.items()), f"{code}.metadata"
        else:
            assert seed.get(field) == value, f"{code}.{field}: seed drifts from migration_128"
    assert forbidden_hits(row_strings(seed)) == []


def test_every_seed_e28_name_is_the_name_migration_128_writes():
    named = [c for c in FIXES if "name" in FIXES[c]]
    assert {c: SEED[c]["name"] for c in named} == {c: FIXES[c]["name"] for c in named}


def test_migration_128_leaves_the_live_e28a_name_alone():
    assert "name" not in FIXES["E28A"]
    assert set(FIXES) - {"E28A"} <= {c for c in FIXES if "name" in FIXES[c]}


def test_the_seed_writer_writes_the_optional_columns():
    src_text = SEED_PATH.read_text()
    for col in ("restrictions", "allowed_activities", "process_steps", "benefits"):
        assert f'"{col}"' in src_text.split("OPTIONAL_COLUMNS = (")[1].split(")")[0]


def test_the_seed_does_not_describe_e28g_as_a_product():
    text = " ".join(row_strings(SEED["E28G"]))
    assert "Parent Company Representative" not in text and "Perwakilan Perusahaan Induk" not in text
    assert SEED["E28G"]["metadata"]["retired"] is True


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


FORBIDDEN_CONCEPT = [r"15 miliar", r"15 billion", r"E28[^\n]*all variants", r"Pasal 176\(2\)\(c\)", r"E28A requires"]


def test_the_kitap_concept_makes_no_e28_kitap_claim_the_sources_do_not_support(src):
    text = next(d for d in src.CONCEPT_DOCS if d["concept_id"] == "nb2-kitap-conversion")["text"]
    assert not [p for p in FORBIDDEN_CONCEPT if re.search(p, text)]
    # innocence: the unrelated E31 line and the neutral E28 line survive
    assert "E31 series, all variants" in text and "Investors (E28 series): KITAP eligibility is NOT stated" in text
    # guilt: the PROD old text trips the matcher
    old = text.replace("Investors (E28 series): KITAP eligibility is NOT stated on the official visa pages; confirm before advising",
                       "Investors (E28 series, all variants)") + "\n- KITAP E28A requires: **Rp 15 billion** in shares (Pasal 176(2)(c))"
    assert len([p for p in FORBIDDEN_CONCEPT if re.search(p, old)]) >= 3


@pytest.mark.parametrize("code", LIVE_CODES)
def test_the_stated_stay_claims_are_neutral_where_the_page_is_silent(src, code):
    rule = src.RULES[code]
    assert rule.extension_days is None and rule.max_total_days is None, "unknown is None, never 0"
    assert rule.kitap_eligible is None and rule.kitap_years_required is None
    assert rule.visa_validity == "90 days from issuance", "visa validity is the ENTRY window (every page: 90 days)"
    assert "Masa berlaku visa adalah 90 hari" in page_text(code)
    block = src.build_stay_section(rule)
    assert "730" not in block.replace("730 days (2 years)", "") and "Max total stay" not in block
    assert "not stated on the official Imigrasi page" in block and "length not stated" in block
    assert "Visa validity (entry window)**: 90 days" in block
    md = src.build_metadata({"stay_extension_days": 730, "stay_max_extensions": 1, "stay_initial_days": 1825}, rule)
    assert "stay_extension_days" not in md and "stay_max_extensions" not in md and "stay_max_total_days" not in md
    assert md["visa_validity"] == "90 days from issuance"
    if code == "E28A":
        assert md["stay_initial_days"] == 730 and "stay_tier_days" not in md
    else:
        assert md["stay_tier_days"] == [1825, 3650] and "stay_initial_days" not in md, "both tiers kept"


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


OLD_SECTION = (
    "## E28A KITAS vs KITAP threshold (IMPORTANT)\n- KITAS E28A requires: Rp 10 billion in shares\n"
    "- KITAP E28A requires: **Rp 15 billion** in shares (Permenkumham 11/2024 Pasal 176(2)(c))\n\n"
)
NEUTRAL = "- Investors (E28 series): KITAP eligibility is NOT stated on the official visa pages; confirm before advising"


def _old_concept_text(fx, src):
    new = next(d for d in src.CONCEPT_DOCS if d["concept_id"] == fx.CONCEPT_ID)["text"].strip()
    anchor = "## Document checklist (Pasal 176)"
    b = "- NB-2 has no documented age-based exemption"
    c = "- **E31A spouse of WNI**"
    assert NEUTRAL in new and anchor in new and b in new and c in new
    old = new.replace(NEUTRAL, "- Investors (E28 series, all variants)").replace(anchor, OLD_SECTION + anchor)
    old = old.replace(c, "- **E28B/E28G Golden Visa**: direct KITAP-INV after 5 years (skip language test, maintain investment)\n" + c)
    return old.replace(b, "- Exemption: Golden Visa investors (E28B, E28G)\n" + b)


def _old_concept(fx, src):
    return {"id": fx.CONCEPT_POINT_ID, "payload": {"text": _old_concept_text(fx, src), "metadata": {"code": fx.CONCEPT_CODE, "k": 1}}, "vector": {"dense": [0.3]}}


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
        self.fail_on_write_number: int | None = None  # 1-based index of the write that errors
        self.backup_path: Path | None = None
        self.backup_existed_at_first_write: bool | None = None
        self._writes_seen = 0

    def _is_write(self, request, path):
        return request.method == "PUT" or path.endswith(("/payload", "/delete")) and request.method == "POST"

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        path = request.url.path
        self.log.append((request.url.host, path, body))
        assert request.headers["api-key"] == SECRET
        if self._is_write(request, path):
            self._writes_seen += 1
            if self.backup_existed_at_first_write is None and self.backup_path is not None:
                self.backup_existed_at_first_write = self.backup_path.exists()
            if self._writes_seen == self.fail_on_write_number:
                return httpx.Response(500, json={"status": {"error": "injected"}})
        if request.method == "PUT" and path == "/collections/visa_oracle/points/payload":
            for pid in body["points"]:
                self.points[pid]["payload"] = json.loads(json.dumps(body["payload"]))  # overwrite
            return httpx.Response(200, json={"result": {"status": "completed"}})
        if request.method == "PUT" and path == "/collections/visa_oracle/points":
            for p in body["points"]:
                self.points[p["id"]] = {"id": p["id"], "payload": p["payload"], "vector": p["vector"]}
            return httpx.Response(200, json={"result": {"status": "completed"}})
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
        return [(p, b) for _, p, b in self.log if p.endswith(("/payload", "/delete"))]  # POST set/delete only


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
    fake.backup_path = backup
    code, out, err = _run(fx, fake, ["--apply", "--backup", str(backup)], capsys)
    assert code == 0, err
    assert fake.backup_existed_at_first_write is True, "the backup must exist BEFORE the first write"
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
    md_a = fake.points[fx.CODE_POINTS["E28A"]]["payload"]["metadata"]
    assert "stay_extension_days" not in md_a and md_a["stay_initial_days"] == 730 and md_a["visa_validity"] == "90 days from issuance"
    md_b = fake.points[fx.CODE_POINTS["E28B"]]["payload"]["metadata"]
    assert md_b["stay_tier_days"] == [1825, 3650] and "stay_initial_days" not in md_b
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


def test_a_text_with_neither_the_old_sentence_nor_the_new_notes_refuses(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    fake.points[fx.CODE_POINTS["E28B"]]["payload"]["text"] = "something arbitrary and corrupted"
    code, _, err = _run(fx, fake, ["--apply", "--backup", str(tmp_path / "b.json")], capsys)
    assert code == 3 and fake.writes() == [] and "neither the expected old sentence" in err


@pytest.mark.parametrize("bad", [{"text": 5, "metadata": {"code": "E28B"}}, {"text": "x", "metadata": "no"}, {"metadata": {"code": "E28B"}}])
def test_a_payload_with_the_wrong_keys_or_types_refuses(fx, src, capsys, tmp_path, bad):
    fake = FakeQdrant(fx, src)
    fake.points[fx.CODE_POINTS["E28B"]]["payload"] = bad
    code, _, err = _run(fx, fake, ["--apply", "--backup", str(tmp_path / "b.json")], capsys)
    assert code == 3 and fake.writes() == []


def test_the_concept_note_that_lost_its_old_anchors_but_is_not_the_new_text_refuses(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    t = fake.points[fx.CONCEPT_POINT_ID]["payload"]["text"]
    fake.points[fx.CONCEPT_POINT_ID]["payload"]["text"] = t.replace("Rp 15 billion", "Rp 15 bn")
    code, _, err = _run(fx, fake, ["--apply", "--backup", str(tmp_path / "b.json")], capsys)
    assert code == 3 and "old anchor" in err and fake.writes() == []


def test_a_mid_run_error_stops_at_once_and_prints_the_exact_restore_command(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    fake.fail_on_write_number = 3
    b = tmp_path / "b.json"
    code, out, err = _run(fx, fake, ["--apply", "--backup", str(b)], capsys)
    assert code == 5 and len(fake.writes()) == 3, "stopped at the failing write, no further calls"
    assert f"python3 scripts/fix_visa_oracle_e28_points.py --restore {b} --apply" in err
    assert SECRET not in out + err


def test_restore_puts_every_payload_back_exactly_and_recreates_the_deleted_point(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    original = json.loads(json.dumps(fake.points))
    b = tmp_path / "b.json"
    assert _run(fx, fake, ["--apply", "--backup", str(b)], capsys)[0] == 0
    assert fx.E28G_POINT_ID not in fake.points
    code, out, err = _run(fx, fake, ["--restore", str(b)], capsys)  # dry-run: no write
    assert code == 0 and "dry-run" in out and fx.E28G_POINT_ID not in fake.points
    code, out, err = _run(fx, fake, ["--restore", str(b), "--apply"], capsys)
    assert code == 0, err
    assert {pid: p["payload"] for pid, p in fake.points.items()} == {pid: p["payload"] for pid, p in original.items()}
    assert fake.points[fx.E28G_POINT_ID]["vector"] == original[fx.E28G_POINT_ID]["vector"]
    assert SECRET not in out + err
    assert not any("embed" in p for _, p, _ in fake.log)


def test_restore_after_a_partial_run_returns_to_the_original(fx, src, capsys, tmp_path):
    fake = FakeQdrant(fx, src)
    original = {pid: json.loads(json.dumps(p["payload"])) for pid, p in fake.points.items()}
    fake.fail_on_write_number = 4
    b = tmp_path / "b.json"
    assert _run(fx, fake, ["--apply", "--backup", str(b)], capsys)[0] == 5
    fake.fail_on_write_number = None
    assert _run(fx, fake, ["--restore", str(b), "--apply"], capsys)[0] == 0
    assert {pid: p["payload"] for pid, p in fake.points.items()} == original


@pytest.mark.parametrize("code", ["E28A", "E28B", "E28C", "E28D", "E28F"])
def test_no_e28_row_promises_a_path_to_kitap(code):
    # the live rows carried "Path to KITAP"; no E28 page states a KITAP route
    assert FIXES[code]["benefits"] == ["Legal stay in Indonesia", "Multiple entry/exit"]
    assert not any("kitap" in t.lower() for t in row_strings(FIXES[code]))

