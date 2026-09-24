# KG root: the generator that does not exist

> **Status**: SPEC + measured census. **No writes.** Nothing here has been applied to
> `kg_nodes` or `kg_edges`, and §6 asks the owner four questions that must be answered
> before anything is.
> **Measured**: 2026-09-22 on PROD via `scripts/pg.sh` (role `nuzantara_readonly`).
> Every number below is reproducible with `scripts/kbli_filiera/kg_root_census.py`,
> which ships in this PR for exactly that reason.
> **Supersedes as the live count**: the 2026-08-02 prose measurement in
> `.agents/skills/kbli-navigator/SKILL.md` §5.5 "F4 — root and upkeep". That probe was
> right about the shape and is corrected in two places below (§2.5).

---

## §1 — Consumer map: which reader lands on which node family

Four id shapes exist in `kg_nodes` for KBLI. Only one of them is queryable by the
readers. This table is the whole problem stated as a join failure.

| Reader                                                                            | Query line                                                                                                                      | Binds to             | Meets the duplicates?                                                                                                                                  |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `app/routers/kbli_notebook.py:845-848`                                            | `JOIN kg_edges e ON n.entity_id = e.target_entity_id WHERE e.source_entity_id = $1`, bound at 848 to `f"kbli:{code}"`           | `kbli:<code>` ONLY   | **No.** Edges hanging off `kbli_<code>` are structurally unreachable from this query. The licence list silently omits them.                            |
| `app/routers/kbli_notebook_chat.py:1573`                                          | `SELECT entity_id, name, properties FROM kg_nodes WHERE entity_type = 'kbli' AND (name ILIKE $1 OR entity_id ILIKE $1) LIMIT 5` | every family         | **Yes, and it cannot tell them apart.** No `ORDER BY`; the empty duplicates and the rich node compete for 5 slots.                                     |
| `app/routers/kbli_notebook_chat.py:1577`                                          | `code = row["entity_id"].replace("kbli:", "")`                                                                                  | —                    | **Yes, and it renders garbage.** `replace("kbli:", "")` is a **no-op** on `kbli_47721`; the `KBLISearchResult` is then built with `code="kbli_47721"`. |
| `services/rag/kg_auto_expansion.py:110` `normalize_entity_id()`, returning at 179 | `f"{prefix}:{normalized}"`                                                                                                      | writes `kbli:<code>` | **No** — and this is the one writer that gets it right.                                                                                                |
| `services/rag/kg_subgraph_company.py:225`                                         | `re.search(r"KBLI\s*(\d{5})", query)` then a `kbli:`-keyed lookup                                                               | `kbli:<code>`        | No.                                                                                                                                                    |
| `app/routers/kg_agentic.py:372`, `app/routers/health.py:936`                      | generic `kg_edges`/`kg_nodes` traversal, no id-shape filter                                                                     | every family         | **Yes.** A traversal that lands on an empty node reads nothing and the answer degrades to `"Verify at OSS"` — honest, but the answer is lost.          |
| `scripts/kbli_filiera/kbli_surface_conformance.py:182` (the detector)             | `WHERE n.entity_id ~ '^kbli:[0-9]{5}$'`                                                                                         | `kbli:<code>` ONLY   | **No.** §5 is about this line.                                                                                                                         |

**The two failure modes are different and both are live.** A `kbli:`-keyed reader is
_blind_ to the duplicates — it under-answers and never knows. A shape-agnostic reader
_finds_ them — and either renders nothing (`"Verify at OSS"`) or renders a malformed code.

---

## §2 — MEASURED state, 2026-09-22

Reproduce: `scripts/kbli_filiera/kg_root_census.py` (read-only, exit 4 on an empty read).

### 2.1 Node families by id shape × has-data

`has-data` is `properties ? 'kode'` — the 2026-08-02 probe correction: the rich rows are
NAMED by their title (`VILLA RENTAL (AKTIVITAS VILA)`), only the empty skeletons are named
`KBLI <code>`, so keying a data probe on `name` measures the dedup disease and calls it
absence.

| id shape               |      nodes | with `kode` |      empty | edge-reachable nodes |   in-edges |  out-edges |
| ---------------------- | ---------: | ----------: | ---------: | -------------------: | ---------: | ---------: |
| `kbli:<code>`          |      1,569 |       1,563 |      **6** |                1,567 |     11,591 |     24,510 |
| `kbli_<name>`          |      5,945 |           0 |      5,945 |                4,830 |      9,354 |     11,744 |
| `kbli_kbli_<name>`     |      5,026 |           0 |      5,026 |                4,319 |      6,153 |     15,315 |
| `<digits>` (no prefix) |        326 |           0 |        326 |                   54 |         54 |         49 |
| free text              |        828 |           0 |        828 |                  693 |      1,047 |      7,624 |
| **total**              | **13,694** |   **1,563** | **12,131** |           **11,463** | **28,199** | **59,242** |

**12,131 empty nodes; 9,896 of them are edge-reachable.** 49,306 of the graph's 271,417
edges (18.2%) have at least one end on an empty KBLI node.

The `entity_type` filter matters and no previous census used the right one: the store holds
`entity_type='kbli'` (13,684) **and** `entity_type='kbli_code'` (11). Reading only `'kbli'`
loses ten of the eleven, and those ten are the most interesting rows in the table (§2.4).

### 2.2 Provenance — who wrote each family, and when it last wrote

| family       | window                      | top `source_collection`                                                                                                   |
| ------------ | --------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `kbli:`      | 2026-01-28 … 2026-09-21     | `kbli_2025_import` 1,562 · `kg_seed` 6 · `kbli_2025_canonical` 1                                                          |
| `kbli_`      | 2026-02-04 … **2026-08-09** | `legal_unified_hybrid_hybrid` 2,020 · `kbli_unified` 1,778 · `legal_unified_hybrid` 1,128 · `visa_oracle` 637             |
| `kbli_kbli_` | 2026-02-05 … **2026-08-21** | `legal_unified_hybrid` 2,030 · `kbli_2025_final_hybrid` 1,615 · `legal_unified_hybrid_hybrid` 1,163 · `balizero_news` 167 |
| `<digits>`   | 2026-03-08 … 2026-03-10     | `legal_unified_hybrid_hybrid` 326 (one ingestion run)                                                                     |
| free text    | 2026-02-05 … 2026-03-28     | `legal_unified_hybrid_hybrid` 671                                                                                         |

**This is not archaeology.** The double-prefixed family took its last write **2026-08-21**,
seven weeks ago, from `balizero_news` — an ingestion path that is still scheduled. A cure
that only deletes is a cure the writers will undo.

`properties` also carries a second drift: **258 empty nodes hold `properties` as a jsonb
STRING scalar, not an object** (229 in `kbli_kbli_`, 29 in `kbli_`) — the `json.dumps`
double-encode already documented at `agents/services/kg_repository.py:77-83` and cured there
with `$4::text::jsonb`. The cure fixed the writer; these rows are what it left behind. The
readers defend against it by hand (`json.loads(row["properties"]) if isinstance(..., str)`,
`kbli_notebook_chat.py:1580`).

### 2.3 Edges into each family, by `relationship_type` (top 10)

| rank | `kbli:`           | `kbli_`            | `kbli_kbli_`     | free text        |
| ---- | ----------------- | ------------------ | ---------------- | ---------------- |
| 1    | APPLIES_TO 4,699  | APPLIES_TO 3,924   | APPLIES_TO 3,168 | PART_OF 380      |
| 2    | PENALTY_FOR 1,953 | PART_OF 1,323      | REQUIRES **815** | APPLIES_TO 246   |
| 3    | REQUIRES 1,299    | REFERENCES 1,285   | REFERENCES 741   | REFERENCES 152   |
| 4    | PART_OF 1,294     | REQUIRES **1,080** | PART_OF 738      | REQUIRES 114     |
| 5    | SAME_AS 1,038     | OPERATES_IN 476    | PENALTY_FOR 420  | CLASSIFIED_AS 75 |
| 6    | RELATED_TO 909    | CLASSIFIED_AS 400  | ISSUED_BY 107    | OPERATES_IN 24   |
| 7    | REFERENCES 249    | RELATED_TO 386     | CLASSIFIED_AS 74 | REGULATES 16     |
| 8    | CLASSIFIED_AS 109 | SAME_AS 266        | HAS_DURATION 31  | EXCLUDES 14      |
| 9    | SIMILAR_TO 39     | HAS_FEE 86         | AMENDS 25        | HAS_FEE 12       |
| 10   | HAS_DURATION 2    | ISSUED_BY 36       | HAS_FEE 23       | SAME_AS 5        |

**`REQUIRES` is the load-bearing one.** `kbli_notebook.py:845-848` builds the client's licence
list from `REQUIRES` edges whose SOURCE is `kbli:<code>`. **1,895 `REQUIRES` edges point into
an empty duplicate** (1,080 + 815) against 1,299 into the rich family: _more_ `REQUIRES`
assertions live on nodes the licence query cannot reach than on nodes it can.

### 2.4 The six `kbli:` nodes with no `kode` — and they are the detector's six failures

The surface detector's `kg_node_presence` check, run on PROD in this lane:

```
kg_node_presence (every canonical code has a KG node, and the reverse)
  forward failures (canonical code, no KG node): 0
  reverse failures (KG node, not canonical, no NOT_IN_KBLI_2025): 6
      55111  kg_status=None      68110  kg_status=None
      62011  kg_status=None      73110  kg_status=None
      62021  kg_status=None      74100  kg_status=None
```

Those six codes are **exactly** the six `kbli:` nodes that carry no `kode`, and the census
names their origin: `source_collection='kg_seed'`, `created_at=2026-01-28`,
`entity_type='kbli_code'`. They are the graph's FIRST KBLI nodes — hand-seeded a week
before the canonical import — and they carry three drifts at once:

- a **different `entity_type`** (`kbli_code`), which is why no `entity_type='kbli'` census
  has ever seen them;
- a **different property vocabulary** — `{"sector", "risk_level", "dnil_status",
"foreign_allowed", "source_docs", "special_permits"}`, with no `kode`, no `pma_status`,
  no `licensing_status`. `properties->>'licensing_status'` is therefore NULL, which is
  precisely why the detector prints `kg_status=None`;
- **codes that canonical KBLI-2025 does not carry**, which is why they fail in the reverse
  direction at all.

One of them is load-bearing prose: `kbli:68110` asserts `"foreign_allowed": true` next to
`"note": "Foreigners cannot own land freehold (Hak Milik)"`. That is a hand-written
2026-01 judgement in a vocabulary no reader speaks, on the single most
misunderstanding-prone code in the catalogue. **It is not reachable by any reader today**
— `kbli_notebook.py` reads `properties->>'kode'`-era fields — which is the only reason it
has not reached a client.

**This closes a loop the 2026-08-02 probe left open.** The detector could say six codes
were wrong; it could not say why, because its own snapshot query filters
`^kbli:[0-9]{5}$` and its `licensing_status` read returns NULL for a vocabulary it does not
know. The census answers it in one line of provenance.

### 2.5 The 1,139 phantom codes

Strip each node's prefix **once, per family** (never `replace("kbli:", "")`, which is a
no-op on `kbli_47721`) and ask what text the writer took for a code:

|                                         |     count |
| --------------------------------------- | --------: |
| distinct extracted tokens, all families |     8,960 |
| well-formed 5-digit                     |     2,702 |
| …backed by a rich `kbli:<code>` node    |     1,563 |
| **…PHANTOM: 5-digit, no data anywhere** | **1,139** |
| digits of the wrong length              |    ~2,036 |
| not numeric at all                      |    ~4,221 |

Phantom provenance:

| `source_collection`             | nodes | window                      |
| ------------------------------- | ----: | --------------------------- |
| `legal_unified_hybrid`          |   651 | 2026-02-05 … 2026-02-10     |
| `kbli_unified`                  |   530 | 2026-02-11                  |
| `legal_unified_hybrid_hybrid`   |   266 | 2026-03-08 … 2026-04-05     |
| `visa_oracle`                   |   139 | 2026-02-05                  |
| `training_conversations_hybrid` |    70 | 2026-02-05 … 2026-03-31     |
| `balizero_news`                 |    49 | 2026-02-11 … **2026-07-29** |
| `kbli_2025_final_hybrid`        |    45 | 2026-07-22 … **2026-08-10** |
| `kg_seed`                       |     6 | 2026-01-28 (§2.4)           |
| `immigration_circulars`         |     1 | 2026-07-26                  |

The `_hybrid` suffix marks LLM-assisted extraction. **1,087 of the 1,139 come from a
`_hybrid` or free-text-legal collection**, and the sector distribution is plausible
(`47*` 116, `19*` 60, `03*` 59, `85*` 57) — these are not random digits. They are codes a
model read out of a legal document: some retired KBLI-2020 codes, some typos in the source,
some hallucinated. **This spec does not distinguish them and must not try to** (§4c).

### 2.6 Duplicate fan-out — and a refutation that is one step from expiring

How many nodes does ONE well-formed code resolve to?

| nodes per code |  codes |
| -------------: | -----: |
|              1 |    557 |
|              2 |    907 |
|              3 |  1,144 |
|          **4** | **94** |

The 2026-08-02 probe suspected `kbli_notebook_chat.py`'s `LIMIT 5` (no `ORDER BY`) could
drop the rich node behind duplicates, **measured it, and refuted it at max 3 rows per code**
— recording the refutation rather than dropping it, with the note that "any future `LIMIT`
on that query is one duplicate-family away from becoming real."

**It moved.** The maximum is now **4**, on 94 codes — the fourth shape being the bare
`<digits>` family written 2026-03-08. The refutation still holds (4 < 5) and this spec does
not claim a live bug. It claims the margin is now one writer wide, and that the fix is free:
`ORDER BY entity_id LIKE 'kbli:%' DESC`. §6-D asks whether to take it now.

### 2.7 Cure surface

|                                                                  |  count |
| ---------------------------------------------------------------- | -----: |
| empty nodes whose code HAS a rich `kbli:` twin (**repointable**) |  2,859 |
| inbound edges landing on those                                   |  6,129 |
| outbound edges asserted BY those                                 | 16,819 |
| empty nodes with NO rich twin (phantom + malformed + free text)  |  9,272 |
| …of those, edge-reachable — edges with nowhere to go             |  7,290 |

**Only 2,859 of the 12,131 empties have somewhere to go.** The other 9,272 are not a
repointing problem — they are a status problem, and the temptation to "fix" them by
inventing a destination is the thing §4c exists to forbid.

---

## §3 — ROOT cause, and the generator contract that replaces it

### 3.1 There is no generator. There are four writers and one convention.

`git grep -n "entity_id = f\"" origin/main -- 'apps/backend-rag/**/*.py'` finds the formula
three times, and one place that does it differently:

| site                                                          | formula                                                    | produces          | family                 |
| ------------------------------------------------------------- | ---------------------------------------------------------- | ----------------- | ---------------------- |
| `app/routers/autonomous_agents.py:439`                        | `f"{entity_type}_{name.replace(' ', '_').lower()}"`        | `kbli_<name>`     | `kbli_`                |
| `app/routers/autonomous_agents.py:579`                        | same formula, second copy                                  | `kbli_<name>`     | `kbli_`                |
| `services/autonomous_agents/knowledge_graph_builder.py:300`   | `f"{entity_type}_{entity_name.replace(' ', '_').lower()}"` | `kbli_<name>`     | `kbli_` / `kbli_kbli_` |
| `agents/services/kg_repository.py:74` → `_generate_entity_id` | `f"{entity_type.lower()}_{canonical_name...}"`             | `<type>_<name>`   | `kbli_`                |
| **`services/rag/kg_auto_expansion.py:179`**                   | **`f"{prefix}:{normalized}"`**                             | **`kbli:<code>`** | **`kbli:` — correct**  |

**The separator is the first bug.** Three sites join with `_`, one with `:`. Readers query
`:`. Nothing in the repo states the convention, so a new writer has no way to be told.

**The name is the second bug**, and it is measurable. The formula interpolates a NAME, not a
CODE. `knowledge_graph_builder.py:299` reads
`entity_name = (match.group(1) if match.groups() else match.group(0))` — when the pattern
that fired had no capture group, or the extractor was an LLM returning the literal span, the
"name" is `"KBLI 01191"`, and `f"kbli_{name.lower()}"` yields `kbli_kbli_01191`.

The census proves this is the mechanism and not a theory: **5,026 of 5,026 double-prefixed
nodes have a `name` that already starts with `KBLI`** — 100%, no exceptions. (4,100 of the
single-prefix family do too: same extraction, id built from the capture group, name from the
whole match. Which is why the _name_ column is useless as a data probe, §2.1.)

`kbli_kbli_` appears in **no live writer on `origin/main`** — `git grep -ln "kbli_kbli_"
origin/main` returns only the corner skill, the PENDING-ARMS ledger, and one test fixture.
There is no string to grep for. The bug is a formula plus an input, and only the store shows
it.

### 3.2 The generator contract

One function. One id form. Derived from the CODE, never from the name.

```python
def kbli_entity_id(code: str) -> str:
    """The ONLY id form for a KBLI node. `code` is five digits; anything else
    is not a KBLI node and must not be written as one."""
    if not re.fullmatch(r"[0-9]{5}", code):
        raise ValueError(f"not a KBLI code: {code!r}")
    return f"kbli:{code}"
```

The contract, stated as obligations on every writer:

1. **One id form.** `kbli:<5 digits>`. A writer that cannot produce five digits does not
   write a KBLI node — it writes nothing, or it writes a node of a different
   `entity_type` that no KBLI reader will ever key on. Free text is not a KBLI code.
2. **One `entity_type`.** `kbli`. `kbli_code` is retired (§4d).
3. **Canonical-derived.** The code must be present in
   `data/source_documents/KBLI_2025_FINAL_CLEAN.json`, or the node is written with an
   explicit non-canonical status (§4c) — never silently.
4. **Idempotent from the graph.** Re-running any ingestion converges: `ON CONFLICT
(entity_id) DO UPDATE` on a canonical-derived id is a no-op the second time. The
   present writers are idempotent _per writer_ and divergent _across_ writers, which is how
   one code reaches four nodes.
5. **One writer per property namespace.** `kode`/`pma_status`/`licensing_status` are
   canonical's; an extractor may add edges and may add its own keys, and may never author
   those three.
6. **Extraction writes EDGES, not nodes.** An extractor that meets `KBLI 47721` in a legal
   document has learned an edge, not a code. If `kbli:47721` does not exist, the correct
   behaviour is to record the miss (§5), not to manufacture a node to hang the edge on.
   **Rule 6 is the one that would have prevented all 12,131.**

---

## §4 — Cure plan, in lots

**Nothing in this section is written yet.** Lot sizes are ≤ 25 codes, one transaction per
code, and every row is archived before it is touched — the house shape from
`docs/specs/2026-09-02-kbli-kg-licensing-class-cure-spec.md` §5-§7.

### (a) Repoint the edges of the 2,859 empties that have a rich twin

**Scope**: 2,859 nodes over **1,563 distinct codes**, 6,129 inbound + 16,819 outbound =
22,948 edges. 63 lots of 25 codes.

**1,563 is every rich code there is.** Not "most": the census's rich-node count (1,563) and
the count of rich codes carrying at least one empty duplicate are the same number. There is
no KBLI code in this graph that was written exactly once.

Per code, in ONE transaction:

1. `INSERT INTO kg_edges_archive SELECT * FROM kg_edges WHERE source_entity_id = ANY($dups)
OR target_entity_id = ANY($dups)` — archive row before mutation, always.
2. `UPDATE kg_edges SET target_entity_id = 'kbli:'||$code WHERE target_entity_id = ANY($dups)`
   and the same for `source_entity_id`.
3. De-duplicate: repointing merges N parallel edges into one destination, so
   `(source, target, relationship_type)` collides. **Collapse, do not error** — and record
   the collapse count, because it is the measure of how much of the graph was saying the
   same thing four times.
4. Verify in-transaction: the rich node's degree grew by exactly (repointed − collapsed);
   the duplicates' degree is 0.

**Idempotence comes from the graph, not from a ledger**: the lot's precondition is "these
duplicate ids still have edges". A second run finds zero and is a no-op.

**What this does NOT do**: it does not merge `properties`. The empties have none worth
keeping (§2.1: zero `kode`, max 3 keys, and those keys are `_deprecated`/`_superseded_by`/
`_data_note` on 3 rows). The six `kg_seed` nodes are the exception and are lot (d).

**Risk, stated**: an extractor asserted `REQUIRES` from `kbli_47721` on the strength of a
document it read. Repointing promotes that assertion onto the node the client-facing licence
list reads — 1,895 `REQUIRES` edges become visible that are not visible today. That is the
POINT of the cure and it is also its blast radius. The `kbli_requires_kind.py` classifier
already stands between a `REQUIRES` target and the word "licence"
(`kbli_notebook.py:837` — "35 distinct target entity types were measured on prod");
**lot (a) must not ship before the detector's `kg_stray_admission` check is green on the
repointed set**, or the 2026-02 "10 Billion IDR is a permit" failure returns at scale.
This is a sequencing constraint on the cure, not a reason not to do it.

### (b) Tombstone or delete the empties — priced in §6-A

After (a), the 2,859 repointed nodes hold no data and no edges. The remaining 9,272 hold no
data and, for **7,290** of them, edges that cannot be repointed because there is no
destination.

### (c) The 1,139 phantoms: a status, never data

**Never invent data.** A phantom is a five-digit code a model read somewhere and canonical
does not carry. We do not know whether it is a retired KBLI-2020 code, a typo in a
government PDF, or a hallucination — and the honest ones and the invented ones are
indistinguishable from inside the graph.

Each phantom gets a status and nothing else:
`properties = properties || jsonb_build_object('licensing_status', <STATUS>,
'phantom_provenance', <source_collection>, 'phantom_observed', '2026-09-22')`.

The status name is §6-B. `NOT_IN_KBLI_2025` already exists and is already honoured by the
detector — but it _means_ "a KBLI-2020 code that 2025 retired", and asserting that about a
hallucination is itself an invention.

Whatever the name, the phantoms keep their edges pointing at a node that says "this code has
no data and we do not know why". A traversal landing there degrades to `"Verify at OSS"`,
which is what it already does — the difference is that after this lot it does so _on the
record_, and the detector can count them (§5).

**The 45 phantoms written by `kbli_2025_final_hybrid` up to 2026-08-10 and the 49 by
`balizero_news` up to 2026-07-29 will come back** unless §3.2 rule 6 lands in those writers
first. Lot (c) without the generator is upkeep, not a cure.

### (d) The six `kg_seed` nodes — their own lot, because they are the only empties with data

They carry hand-written 2026-01 judgements in a vocabulary no reader speaks (§2.4), under an
`entity_type` no census sees. They are six rows and they need a human read, not a sweep:

1. Archive all six verbatim.
2. **Read `kbli:68110`'s `foreign_allowed: true` against canonical** before anything else.
   If canonical agrees, the node is redundant and the vocabulary dies with it. If canonical
   disagrees, we have a 2026-01 claim that contradicts the store we ship — and that is a
   finding for the owner, not a migration.
3. Retire `entity_type='kbli_code'` → `'kbli'`, or delete. Either way the type stops existing.
4. Apply lot (c)'s status: none of the six codes is in canonical KBLI-2025.

When this lot lands, `kg_node_presence`'s reverse failures go 6 → 0 and the check is
eligible for the DECLARED→ENFORCED flip (§5) — **in its own one-line PR after its own log
reads 0**, never in the same PR as the cure (W116).

### (e) The 258 jsonb-string `properties` rows

Cosmetic _today_ only because the readers defend by hand. They are swept up by (a)/(b)/(c)
whichever way §6-A goes; no separate lot. Stated so the next session does not re-discover them.

---

## §5 — Detector additions, DECLARED first

Five checks ship DECLARED in `kbli_surface_conformance.py` today and none of them can see
this problem, for one reason: **line 182, `WHERE n.entity_id ~ '^kbli:[0-9]{5}$'`**. The
snapshot the KG dimension reasons over contains 1,569 of the store's 13,694 KBLI nodes.
The 12,131 empties and the 1,139 phantoms are not failures it is missing — they are rows it
has never read.

That is not a bug in the detector. It was scoped to the canonical family deliberately. It is
a _stated limit_ that this spec turns into a measurement.

Three additions. **All three ship DECLARED — counted and rendered, never folded into
`enforced_divergences` or the exit code** (W116: each flip is its own one-line PR after that
check's own log reads 0).

| check                     | direction | fails when                                                                                         | today                   |
| ------------------------- | --------- | -------------------------------------------------------------------------------------------------- | ----------------------- |
| `kg_id_shape_conformance` | forward   | a node with `entity_type IN ('kbli','kbli_code')` has an `entity_id` that is not `kbli:<5 digits>` | **12,125**              |
| `kg_id_shape_conformance` | reverse   | a `kbli:<5 digits>` node carries no `kode`                                                         | **6**                   |
| `kg_phantom_status`       | forward   | a 5-digit token with no canonical code carries no phantom status                                   | **1,139**               |
| `kg_phantom_status`       | reverse   | a code carries a phantom status while canonical HAS it                                             | **0** (measure at flip) |
| `kg_duplicate_fanout`     | —         | any well-formed code resolves to more than 1 node; RED at ≥ 5 (the `LIMIT`)                        | max **4**, on 94 codes  |

Both directions on every check, stated up front, because a guard that judges only one
direction is scar #3 (guard-over/under-match): `kg_id_shape_conformance`'s reverse direction
is what caught the six `kg_seed` nodes, and the forward direction alone would have called
them clean.

The census script is the shared measurement organ: the detector's new checks consume
`plan_census()`'s output rather than re-deriving it, so "the spec's number" and "the
detector's number" cannot drift apart.

---

## §6 — Owner decisions. Four, each priced two ways.

### A — The 12,131 empties after repointing: tombstone or delete?

|                                        | **A1 — Tombstone** (keep the row, `_deprecated: true`, no edges)                                               | **A2 — Delete**                                                                 |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Rows after cure                        | 13,694                                                                                                         | 1,569                                                                           |
| Cost                                   | 12,131 `UPDATE`s in 486 lots                                                                                   | 12,131 `DELETE`s, same lots                                                     |
| Reversible                             | Yes, from the row itself                                                                                       | Only from the archive table                                                     |
| `kbli_notebook_chat.py:1573` `LIMIT 5` | **still matches them** (`entity_id ILIKE`) — the fan-out problem survives unless §6-D is also taken            | fan-out goes to 1, §6-D becomes optional                                        |
| Forensics                              | The provenance stays queryable in place                                                                        | Archive-only                                                                    |
| Risk                                   | The tombstones are re-adopted by the next extractor run (`ON CONFLICT DO UPDATE`), quietly un-deprecating them | A live consumer we did not find in §1 gets a hard miss instead of an empty node |

**Recommendation: A2 (delete), with the archive table as the reversal path** — conditional
on §3.2 landing first. A1's failure mode is silent (an extractor un-tombstones a row and
nothing says so); A2's is loud (a missing row throws). But A2 is only safe once rule 6 stops
the writers from recreating them, so **A2 without the generator is worse than A1**.

### B — What do we call a 5-digit code with no data?

|               | **B1 — reuse `NOT_IN_KBLI_2025`**                                                                                                                                         | **B2 — a new `PHANTOM_UNVERIFIED`**                                                                 |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Detector work | Zero — already honoured at `kbli_surface_conformance.py:437`                                                                                                              | New constant, new branch, new tests, and `kbli_documents_phantom_cure.py`'s marker must not collide |
| Truthfulness  | **Asserts a retirement we have not established.** 1,087 of 1,139 came from LLM extraction; calling a hallucination "a code 2025 retired" is an invention wearing a status | Says exactly what is known: five digits, no data, we do not know why                                |
| Downstream    | The 2020→2025 crosswalk work can key on it — and would then key on hallucinations too                                                                                     | The crosswalk lane can promote a phantom to `NOT_IN_KBLI_2025` once it has evidence                 |

**Recommendation: B2.** B1 is cheaper by a day and buys it with a false statement at 1,139
rows. The spec's own rule is "never invent data"; a status IS data.

### C — `entity_type='kbli_code'`: retype or delete?

11 rows. **Recommendation: retype the 6 `kg_seed` KBLI nodes to `'kbli'` after lot (d)'s
human read, then assert the type does not exist.** Deleting first throws away the only copy
of a 2026-01 judgement (`kbli:68110`) before anyone has compared it to canonical. Cost is
identical; the ordering is the whole decision.

### D — The `ORDER BY` fix on `kbli_notebook_chat.py:1573` — now, or with the cure?

|      | **D1 — now, its own PR**                                                   | **D2 — after lot (a)/(b)**                                              |
| ---- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Diff | One line: `ORDER BY entity_id LIKE 'kbli:%' DESC` before `LIMIT 5`         | Zero, if §6-A is A2                                                     |
| Buys | The rich node wins the 5 slots **regardless** of how many duplicates exist | Nothing until the cure lands                                            |
| Risk | Effectively nil; it is a preference, not a filter                          | The margin stays one writer wide for however long the cure takes (§2.6) |

**Recommendation: D1, today, in a PR that touches nothing else.** The 2026-08-02 refutation
is still valid (4 < 5) and this is not a bug report. It is a one-line hedge on a margin that
has already moved once, and it is correct under every outcome of A, B and C.

---

## §7 — Proof-of-armed

This PR is a spec and a read-only census. Its own proof is that the numbers are
reproducible, not that the store changed:

```bash
# §2 reproduces from PROD, read-only, exit 0
scripts/kbli_filiera/kg_root_census.py

# the fixture suite, guilt and innocence
.venv/bin/python -m pytest scripts/kbli_filiera/tests/test_kg_root_census.py -q
# -> 25 passed

# the six reverse failures §2.4 identifies
scripts/kbli_filiera/kbli_surface_conformance.py | grep -A 7 "kg_node_presence"
```

**For the cure PRs that follow**, proof-of-armed is per lot and is never the merge:

| lot                  | armed when                                                                                                                                                                           |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| (a) repoint          | `kg_root_census.py` reports `repointable_edges_in = 0` and `repointable_edges_out = 0`; the archive table holds 22,948 rows; `kg_stray_admission` still reads 0 on the repointed set |
| (b) tombstone/delete | the empty count for the chosen families reads 0 (A2) or the tombstone count equals the census count (A1)                                                                             |
| (c) phantoms         | `kg_phantom_status` forward failures go 1,139 → 0                                                                                                                                    |
| (d) `kg_seed`        | `kg_node_presence` reverse failures go 6 → 0, in a run of the detector itself                                                                                                        |
| (§3.2) generator     | the census, **re-run 14 days after the writers land**, reports 0 new nodes outside `kbli:<5 digits>`. A cure whose proof is taken the same day proves only that the DELETE ran.      |

The last row is the one that matters. Every previous pass at this problem deleted edges by
hand and measured the deletion. The disease is a writer, and only a second measurement,
later, can show a writer stopped.
