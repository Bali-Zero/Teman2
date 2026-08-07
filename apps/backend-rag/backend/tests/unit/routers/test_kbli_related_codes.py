"""`related_codes` must never show a client the same sibling code twice.

The KG holds **1,341 duplicated (source, sector) `BELONGS_TO` rows** — every
duplicated pair appears exactly twice. The endpoint's query applied `LIMIT 6`
BEFORE any dedup or self-exclusion, so the duplicates both showed AND ate the
budget: measured on prod, `inspect_kbli 79122` returned
`['79110', '79110', '79121', '79121']` — six rows spent on two codes — and
`56101` returned `['56102', '56102', '56210', '56210']`.

The fix puts `DISTINCT` and the self-exclusion in SQL (so the limit is spent on
six real siblings) and keeps this pure mapper as an independent second line.
"""

from backend.app.routers.kbli_notebook import related_codes_from_rows


class TestRelatedCodesFromRows:
    def test_collapses_the_duplicate_rows_the_graph_actually_holds(self):
        """GUILT — the exact prod payload that made 79122 show two codes twice."""
        rows = ["kbli:79110", "kbli:79110", "kbli:79121", "kbli:79121"]
        assert related_codes_from_rows(rows, "79122") == ["79110", "79121"]

    def test_excludes_the_code_being_inspected(self):
        rows = ["kbli:56101", "kbli:56102", "kbli:56210"]
        assert related_codes_from_rows(rows, "56101") == ["56102", "56210"]

    def test_excludes_self_even_when_duplicated(self):
        rows = ["kbli:56101", "kbli:56101", "kbli:56102"]
        assert related_codes_from_rows(rows, "56101") == ["56102"]

    def test_preserves_the_query_ordering(self):
        """INNOCENCE — the SQL orders by entity id; dedup must not resort."""
        rows = ["kbli:79903", "kbli:79110", "kbli:79121"]
        assert related_codes_from_rows(rows, "79122") == ["79903", "79110", "79121"]

    def test_keeps_every_distinct_sibling(self):
        """INNOCENCE — dedup must not swallow codes that merely look similar."""
        rows = [f"kbli:7910{n}" for n in range(6)]
        assert related_codes_from_rows(rows, "79122") == [f"7910{n}" for n in range(6)]

    def test_strips_only_the_leading_prefix(self):
        """A bare code is passed through; `kbli:` is not stripped mid-string."""
        assert related_codes_from_rows(["kbli:56102", "56210"], "56101") == [
            "56102",
            "56210",
        ]

    def test_drops_blank_rows_instead_of_emitting_an_empty_code(self):
        assert related_codes_from_rows(["kbli:", "  ", "kbli:56102"], "56101") == [
            "56102"
        ]

    def test_empty_input_is_empty_output(self):
        assert related_codes_from_rows([], "56101") == []

    def test_accepts_a_generator_not_just_a_list(self):
        """The caller passes a generator expression over the fetched rows."""
        rows = (r for r in ["kbli:79110", "kbli:79110"])
        assert related_codes_from_rows(rows, "79122") == ["79110"]
