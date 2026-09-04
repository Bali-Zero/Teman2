# Spec — the KG tells clients "PENDING_REGULATION" on codes whose government licensing rows exist, and no script can cure it

**Date:** 2026-09-02 · **Revised:** 2026-09-03 (r4) · **Status:** **REOPENED.** The six open round-3
findings are folded below, each against a measurement re-taken on 2026-09-03 from a fresh PROD dump — and
re-taking them surfaced a **seventh** client-facing defect the refuter could not see, because it lives on
codes its census had filtered out: **nine codes serve `KITAS` — a personal residence permit — as the
licence of a business**, `55111` "Hotel Bintang Lima" among them (§2.3, proven live this session). §5–§7 are rewritten where the findings
hit them. Still nothing implemented; `--placeholders-only` (§5.4) is the first build PR. The 2026-09-02
suspension stands as history — that draft was not buildable, and this is a different design, not a fourth
round on the same one. · **Surface:** `kg_nodes` /
`kg_edges` (PROD Postgres), `apps/backend-rag/backend/app/routers/kbli_notebook.py` (`inspect_kbli`),
`apps/backend-rag/backend/services/kbli_requires_kind.py`,
`apps/backend-rag/backend/scripts/kg_kbli_license_fix.py`, `scripts/kbli_filiera/kbli_surface_conformance.py`

This document exists because PR #5513 (`--licensing-only`, merged 2026-09-01) cured the
`kbli_documents` table for 25 codes and, while grounding its consumer map, proved that **the table
is not what a client hears** — the KG is, and 22 of those 25 codes still answer
`licensing_status: PENDING_REGULATION, licenses: []` there. The PENDING-ARMS row opened that day
("The client-facing licensing defect of those 25 codes lives in the KG") demanded a spec before
any script, for three reasons it named: (a) the original derivation of a `REQUIRES` edge from a
PP 28/2025 row is undocumented, (b) the cross-store verdict convention is unstated, (c) nothing
detects the class. Agent PR Contract §8: an under-specified surface gets a spec, not a third
script. **Nothing here is implemented.**

Every number below was measured read-only against PROD — 2026-09-01 16:1x–16:5xZ for the first
census, and **re-measured 2026-09-02 01:1xZ with the router's exact admission predicate** (`scripts/pg.sh`
from Pro; dump `kg_r3_probe.psv` = every `kbli:<5 digits>` node status + every `REQUIRES` edge to a
permit-typed target, 1,568 + 5,318 rows; recompute script kept with the dump under
`~/logs/kbli-conformance/`) — and against the canonical `data/source_documents/KBLI_2025_FINAL_CLEAN.json`
at `origin/main` (`32a6dbab6f`; dataset last touched by `f6dfda994d`, #4215). Where a fact was read
from code, the `path:line` is given; a claim without one is a design choice, not a measurement. Two
refuter rounds (last section) each falsified part of the previous draft; the numbers below are the
third measurement, and the predicate that produced them is the router's own function, not a
paraphrase of it.

---

## 1. What the client actually hears (the consumer map, grounded)

- **`inspect_kbli` checks the Redis cache first (`kbli_notebook.py:609-614`); on a miss the KG read is
  mandatory.** `:626-635`: `SELECT * FROM kg_nodes WHERE entity_id = $1` (`kbli:<code>`), **404 if
  absent**. Licences come from `:653-659`: `SELECT n.*, n.entity_type AS target_entity_type,
e.properties AS edge_props FROM kg_nodes n JOIN kg_edges e ON n.entity_id = e.target_entity_id WHERE
e.source_entity_id = $1 AND e.relationship_type = 'REQUIRES'`. Qdrant is consulted last (`:745`) only
  to enrich `pma_status` / `kategori_risiko`, and `:758-762` back-fills a licence's `risk_level` from
  Qdrant only when it is `"Unknown"`.
- **The tier data is read from the TARGET NODE, not from the edge.** `edge_props` is selected and
  never used: `lic_props` is built from `lic["properties"]` — the target node's column
  (`:664-668`) — and each surviving row becomes `KBLILicense(type=lic["name"],
scale=lic_props.get("skala_usaha", ["All"]), risk_level=lic_props.get("kategori_risiko",
"Unknown"), sla=lic_props.get("jangka_waktu", "N/A"), requirements=lic_props.get("kewajiban",
[]))` (`:691-699`). `KBLILicense` has exactly those five fields (`:79-84`) — no issuer, no
  verification field — and both mouth renderers print exactly those five
  (`apps/mouth/src/app/kbli-explorer/components/KBLIInspector.tsx:275-309`,
  `kbli-explorer/page.tsx:879-897`). PROD confirms the legacy shape: `perizinan:14962b2d34ae`
  carries `{"kewajiban": [...], "skala_usaha": ["Mikro","Kecil"], "jangka_waktu": "Otomatis",
"kategori_risiko": "Menengah Rendah"}` on the **node**. **Any cure must write the tier data on the
  target node** (§5.3).
- **The admission predicate — the ONE predicate this spec, the cure, the census and the detector
  use.** A `REQUIRES` target reaches `licenses[]` iff (`kbli_notebook.py:674-689`):
  `classify_requires_target(target.entity_type) == "license"` (`kbli_requires_kind.py:58-66,118` —
  `entity_type ∈ PERMIT_TYPES = {perizinan, izin_usaha, license, nib, permit_type, penetapan}`)
  **and then** `permit_name_verdict(target.entity_id, target.name) == "permit"`
  (`kbli_requires_kind.py:242-272`). The verdict demotes: an empty name (`:251-253`); an id
  containing one of `_UNKNOWN_ID_MARKERS = ("tidak_diketahui", "unknown", "placeholder")` (`:178,
:255-256`); an id carrying the token `kewajiban` (`:260-261`); a name that is an enumerated
  category label (`:202-215`); a name opening with one of 23 obligation verbs (`:266-270`). A
  demoted target is not dropped — it is bucketed into `related_requirements[<verdict>]`
  (`:686-688`). **`pending` is not a marker** — see §2.1. Re-measured on PROD **2026-09-03** over **every** `REQUIRES`
  edge out of a `kbli:<5 digits>` node — 13,344 of them, no intersection filter (dump
  `kbli_nodes_0903.psv` + `kbli_edges_0903.csv`, recompute `kg_r4_recompute.py`, all three under
  `~/logs/kbli-conformance/`): 5,318 permit-typed, **4,722 admitted**, **355** demoted
  `unspecified_permits`, **241** demoted `obligations` — and `4,722 + 355 + 241 = 5,318`, which is
  the arithmetic the 2026-09-02 draft did not close: it reported `4,699 / 352 / 241` **= 5,292**
  against that same 5,318 denominator, because its census intersected the KG with the canonical and
  therefore scored no edge belonging to the 10 KG-only codes (round 3 #1; the refuter estimated the
  gap at 9 edges — the dump says **26**). 17 of the 4,722 point at the three placeholders: the hole. The spec calls this
  function `client_admitted_permit(entity_type, entity_id, name)`; §7 makes it a named export of
  `kbli_requires_kind.py` that the router itself calls, so there is exactly one spelling.
- **The verdict**: `licensing_status = props.get("licensing_status", "REGULATED")` (`:785`) — a node
  with no key is served as REGULATED. **The status never suppresses `licenses[]`**: the list is
  assembled at `:661-699` and returned at `:788` regardless of the status resolved at `:785`.
- **The mouth renders the enum raw**: `KBLIInspector.tsx:201` and `kbli-explorer/page.tsx:807` print
  `data.licensing_status` untranslated. The only friendly copy is for an empty list
  (`apps/mouth/src/lib/kbli-licence-summary.ts:45-65`): `"None (outside OSS licensing)"` **only**
  when the list is empty _and_ the status is `NOT_APPLICABLE_OSS`, otherwise `"Not listed in our
data"`.
- **Who does NOT read this**: `search_kbli` (Qdrant only, `kbli_notebook.py:530-578`) and `chat_kbli`
  (its `kg_nodes` fallback at `kbli_notebook_chat.py:1123-1144` builds a `KBLISearchResult`, a schema
  with no licensing field). `services/rag/kg_subgraph_company.py` reads `REQUIRES` only toward
  `company:pt_pma` (`:235-242`) and fills its `licensing_requirements` list with PMA/capital results
  (`:377-384,460-465`) — it would not consume the permit edges written here.
- **Cache**: Redis key `kbli_inspect_v6_{code}` (`kbli_notebook.py:606`), TTL 12h / 7d / 30d by prefix
  (`:484-493`); bust = `kbli_inspect_cache_bust.py --only <codes> --apply` (mandatory `--only`,
  re-reads after delete, `SystemExit(3)` if Redis is configured but unreachable). The key version is
  bumped (`v6` → `v7`) only if the router's field semantics change (§8 F2), per the comment at
  `:596-602`; a data-only cure busts per code.

Live proof (this session, MCP `inspect_kbli`): `85510` → `PENDING_REGULATION, risk_profile: Tinggi,
licenses: []`. `03231` → `REGULATED`, three licences (`Sertifikat Standar` / `NIB dan Sertifikat
Standar` ×2, scales `[Mikro,Kecil]` and `[Menengah,Besar]`, sla `Otomatis` / `3 Hari`, requirements
= the row `kewajiban`). **`65121` → `PENDING_REGULATION` and `licenses: [{"type":
"PENDING_REGULATION", "scale": ["All"], "risk_level": "Tinggi", "sla": "N/A", "requirements": []}]`
— a client is shown a licence whose name is a status word.**

## 2. The measured state of the KG against the canonical

Canonical: 1,559 records; `per_skala` rows > 0 on **1,342**, `== []` on **217** (`{'3-10': 1137,
'11+': 162, '0': 217, '1-2': 43}`); 9,095 v10 rows in total. **The canonical carries NO
`licensing_status` field at all** (`grep -c '"licensing_status"'` → 0); the verdict exists only
downstream — on `kg_nodes.properties` and, since 2026-09-01, on `kbli_documents.metadata`, where
`kbli_documents_cure.py:441-445` writes `PENDING_REGULATION` when `per_skala == []` and, when rows
exist, **preserves the old status and defaults to `N/A` only when there was none** (inherited, §8 F1).

KG: 1,568 `kbli:<5 digits>` nodes; 1,558 exist in both stores. **10 KG codes are absent from the
canonical**, and **1 canonical code — `01122` "Pertanian Padi Inbrida", 8 v10 rows — has NO KG node**:
`inspect_kbli 01122` answers HTTP 404 (measured live 2026-09-03), and neither
`kg_kbli_resync.py:229-238` nor the 2026-09-02 §5 could create one (round 3 #2 — folded in §2.3 and
§5.9). `licensing_status`: `REGULATED 1266 · PENDING_REGULATION 217 · NOT_APPLICABLE_OSS 75 · <null> 6
· NOT_IN_KBLI_2025 4`. `REQUIRES` edges from KBLI nodes: 13,344, to 35 target types — `dokumen 7369 ·
perizinan 2097 · izin_usaha 1935 · license 1167 · kewajiban 174 …`; only the admitted subset (§1)
renders as a licence.

**The classes are DISJOINT STATES of a code — and there are TWO tables, because the placeholder lot
moves 16 codes between them.** Over the 1,341 codes present in both stores with rows > 0, by
(admitted permits, status), under the router's own predicate (§1):

**Table A — LIVE right now.** The three placeholders ARE admitted, so a placeholder edge counts as a
rendered licence. This is the state a client is in today, and the state `--census` prints first:

| state  | definition                                                         | codes  | non-OSS (§3) |
| ------ | ------------------------------------------------------------------ | ------ | ------------ |
| **S1** | admitted = 0, `PENDING_REGULATION`                                 | **54** | 22           |
| **S2** | admitted = 0, `REGULATED` (rendered as "Not listed in our data")   | **99** | 34           |
| **S3** | admitted ≥ 1, `PENDING_REGULATION` (16 of them a placeholder ONLY) | **22** | 5            |
| —      | admitted ≥ 1, `REGULATED` (legacy-served, Phase 2)                 | 1,166  | —            |
| —      | admitted = 0, other status                                         | 0      | —            |

**Table B — after the `--placeholders-only` lot (§5.4) and its cache bust**, which is a HARD
PREDECESSOR of every state-driven action in this spec:

| state  | definition                         | codes                                            | non-OSS | Phase-1 action (§5.2)      |
| ------ | ---------------------------------- | ------------------------------------------------ | ------- | -------------------------- |
| **S1** | admitted = 0, `PENDING_REGULATION` | **70**                                           | 26      | build licences + relabel   |
| **S2** | admitted = 0, `REGULATED`          | **99**                                           | 34      | build licences             |
| **S3** | admitted ≥ 1, `PENDING_REGULATION` | **6** — 25920, 52322, 55400, 65303, 85694, 90200 | 1       | **nothing written** (§5.2) |
| —      | admitted ≥ 1, `REGULATED`          | 1,166                                            | —       | none (Phase 2)             |

**The union is the same 175 codes in both tables** — the lot moves codes between S3 and S1, it adds
and removes none; non-OSS-issued **61**; **Phase 1a = 114**, **Phase 1b = 61**. **Both tables are
over the 1,341 codes that exist in BOTH stores, so neither contains `01122`** — it has no KG node to
have a state. The moment Lot 0(c) creates that node it becomes an S2 code (8 rows ⇒ `REGULATED` by
§3, zero admitted permits) and it is OSS-issued, so the post-Lot-0 figures are **union 176 / Phase 1a
115 (110 built) / Phase 1b 61**. Every count here is stated for the state it belongs to; a number
that moves is written twice rather than averaged. Outside the rows > 0
set: rows == 0 & `PENDING_REGULATION` 141; rows == 0 & `NOT_APPLICABLE_OSS` 75 (all of that status,
§3); rows == 0 & `REGULATED` **1** — `91300` (the shape `kg_kbli_license_fix.py` already cures).

**Ordering is a RULE, not a caveat (round 3 #1, folded).** Table B is not reachable by relabelling;
it is reachable only by deleting the 17 placeholder edges. The ordering is therefore enforced by the
script and not by the runbook: **a build- or relabel-mode `--only` run refuses (`SystemExit(2)`) any
code that still carries a placeholder edge**, and `--census` always prints Table A first and Table B
second. The 2026-09-02 draft printed only Table B and called it "the" state, because the census that
produced 70/99/6 labelled the placeholders separately (`kg_r3_recompute.py:65-73`) — which the router
does not do, and the router is what a client hears.

How the earlier drafts got it wrong, so the next reader does not repeat it: the round-1 draft counted
one id prefix (`perizinan:`) and found 125; the round-2 draft counted permit-typed targets minus the
three placeholders and found "148 build + 76 relabel", presented as if disjoint (they overlapped on
69 codes — the union was 155, and the "78 non-OSS" summed two overlapping counts). Under the router's
real predicate **21 more codes** join the build set: 20 `REGULATED` codes whose only permit-typed
targets are demoted `unspecified_permits` (07229, 07294, 07296, 08105, 08107, 08991, 32906, 35120,
52233, 66115, 66117, 66121, 66127, 66133, 66152, 66191, 66223, 68291, 85594, 85599 — a client sees
"Not listed in our data" on each) and 87910 (`PENDING_REGULATION`, same shape). "Permit-typed" is
not "rendered"; only the router's function is.

The 25 detector codes inside this: 03231/03232/03233 are legacy-served (`REGULATED`, 3/3/4 admitted
permits — Phase 2); **20 are S1** and **2 are S3** (85694 renders `Izin Usaha Sertifikasi Profesi`,
90200 `Izin Usaha Pertunjukan Kesenian`); of those 22, five are non-OSS-issued (65111, 65121, 85102,
85510, 85520) → **17 detector codes are in Phase 1a**. Two things the ledger row got wrong: **"edge
count == row count" is not a metric** (722 codes have more edges than rows; documents and
obligations are edges too; a licence is a (permit name × risk tier) pair, a row is a (scope × scale)
tuple — 03231's 20 rows are 3 licences), and **the defect is a class of 175, not "22 of 25"**. Node
`skala_usaha` is `<null>` on the 22 and `["Menengah","Besar"]` on 03231 whose rows cover all four
scales; catalog-wide it disagrees with the canonical union on **881 of 1,341** codes.

### 2.1 Three placeholder nodes are served to clients as licences today

`status_perizinan_pending` (name `PENDING_REGULATION`), `izin_usaha_pending` (`Status Perizinan:
PENDING_REGULATION`) and `izin_usaha_status_pending_regulation`, all `entity_type = izin_usaha`,
created 2026-02-05/06 by `kbli_2025_final`, are `REQUIRES` targets of **17** KBLI nodes, all
`PENDING_REGULATION`, none with any other admitted permit: 03300, 12005, 41020, 60390, 65121, 65301,
82400, 85542, 85573, 85586, 85610, 88907, 90310, 91410, 95400, 96220, 96300. They pass
`classify_requires_target` (permit-typed) **and** `permit_name_verdict` — `pending` is not in
`_UNKNOWN_ID_MARKERS`, the id carries no `kewajiban` token, the name is not a category label and
opens with no verb — so they land in `licenses[]` (live proof on 65121 above). Their canonical
shape is not uniform: **85586 has zero v10 rows** (a `[]` code — nothing to build), **65121, 65301,
85542, 88907 are non-OSS-issued** (Phase 1b), the other 12 are S1 / Phase 1a. Removing a
placeholder edge is therefore its own phase-independent gesture (§5.4 `--placeholders-only`) — a
licence named after a status is false on every code regardless of what else that code gets — and
§8 F5 closes the classifier hole for any future one.

### 2.2 Where today's edges came from — and why the class exists

No script on `origin/main` writes `source_collection = 'kbli_2025_import'` (`git grep` → 0 files),
nor the KG values `REGULATED` / `NOT_APPLICABLE_OSS` (0 non-test writers — `REGULATED` exists only
as the router's read-time default; `NOT_IN_KBLI_2025` is written to `kbli_documents` by
`kbli_documents_phantom_cure.py:134`, never to `kg_nodes`); on the KG, `PENDING_REGULATION` is
written only by `kg_kbli_license_fix.py:243`, and `kg_kbli_resync.py` declares `licensing_status`,
`skala_usaha`, `kategori_risiko`, `sektor_id` "left untouched" (`:24-25`) and holds no `kg_edges`
DML at all. No shared enum governs the value set across the two stores. **The builder that
populated the graph in February 2026 is out-of-tree.** What it consumed is visible in the data: the
2,063 `kbli_2025_import` edges target 2,785 `perizinan:<12-hex>` nodes that carry the tier data as
node properties and whose names are the **legacy** permit strings (`NIB dan Sertifikat Standar`
×1500 nodes, `NIB` ×734, `NIB dan Izin` ×411 …); the canonical still holds that shape as
`per_skala_legacy` (1,256 codes, 2,702 rows; two key sets, one adding `dati_inferiti` on 114 rows;
`perizinan` present). The v10 `per_skala` rows (the PP 28/2025 layer, `_l2_source =
OSS_RBA_resiko_2025` on 1,338 codes) come in **four** key sets (`skala_usaha, kategori_risiko,
jangka_waktu, scope_index, scope_uraian, perizinan, persyaratan, kewajiban, kewenangan,
fiktif_positif` ± `jangka_waktu_source` ± `pb_umku`/`parameter`/`sanksi_*` ± `dati_inferiti`) and
**`perizinan` is empty on 1,336 of the 1,342 codes that have rows**; on five codes (93111, 93112,
93114, 93119, 93191) `perizinan` and `kewenangan` are a **string**, not a list, and **the same five
rows are the only ones in the 9,095 that carry neither `scope_index` nor `scope_uraian`** (§4.3
treats both as optional). **All 25 detector codes — 86 codes in total — have v10 rows and an empty
`per_skala_legacy`**: they entered the canonical after the import ran. The 12-hex suffix of the
legacy node ids is not reproducible from the name alone (six name/code/scale hash candidates: no
match); the cure does not join those nodes.

### 2.3 The eleven codes that live in one store only — and the nine that answer `KITAS`

Round 3 #2 asked for `01122`. Re-measuring it over the whole dump (no intersection filter) turned
the single missing node into a symmetric pair of states, and the second half of the pair is a
client-facing defect nobody had named.

**One canonical code has no KG node.** `01122` "Pertanian Padi Inbrida" carries 8 v10 rows
(`Menengah Rendah` 3, `Menengah Tinggi` 3, `Rendah` 2) and an empty `per_skala_legacy`; there is no
`kbli:01122` row, `kg_edges.source_entity_id` is a FK onto `kg_nodes.entity_id`
(`migration_028_knowledge_graph_schema.py:34`) so it can carry no edges either, and
`inspect_kbli 01122` returns **HTTP 404** (`{"detail":"KBLI code 01122 not found"}`, measured live
2026-09-03). A 404 on a real KBLI-2025 code is not an honest gap — it is the navigator denying the
code exists. §5.9 gives the creation path; the counts and manifests in this spec are computed over
all **1,559** canonical codes, so `01122` is inside them.

**Ten KG codes are not in the canonical, and six of them lie.** Four carry
`licensing_status = NOT_IN_KBLI_2025` and are honest (26120, 60111, 82920, 85598). The other six —
**55111, 62011, 62021, 68110, 73110, 74100** — carry a **`<null>`** status, which `kbli_notebook.py:785`
resolves to the read-time default **`REGULATED`**, and each has exactly one admitted `REQUIRES`
target: `permit:kitas`, `entity_type = permit_type`, name **`KITAS`**. Live, this session:

```
inspect_kbli 55111 → {"code":"55111","title":"KBLI 55111",
  "description":"ID: Hotel Bintang Lima | EN: Five Star Hotel",
  "licensing_status":"REGULATED","risk_profile":"Unknown",
  "licenses":[{"type":"KITAS","scale":["All"],"risk_level":"Unknown","sla":"N/A","requirements":[]}],
  "related_requirements":{"entity_forms":["PT PMA"],"unspecified_permits":["Izin"]}}
```

A KITAS is a **residence permit for a person**. It is not a business licence, it is not issued to
the company, and `55111` is a KBLI-**2020** code that KBLI 2025 does not contain — so the navigator
affirms a code that no longer exists, calls it `REGULATED`, and names the permit a foreigner needs
to live in Indonesia as the licence a five-star hotel must obtain. This is §2.1's disease on a
different class of node: the classifier judges the TYPE (`permit_type` ∈ `PERMIT_TYPES`,
`kbli_requires_kind.py:58-66`) and then the NAME (`KITAS` is no category label and opens with no
obligation verb, `:242-272`), and a personal immigration permit passes both.

**The blast radius is nine codes, not six.** `permit:kitas` is the target of **9** `REQUIRES` edges
from KBLI nodes and is the only `permit_type` node any KBLI code points at. Six are the `<null>` codes
above, where `KITAS` is the code's ONLY licence. The other three are canonical, `REGULATED`,
legacy-served codes where it sits **beside** real licences and is therefore easy to miss:
`55300` Bumi Perkemahan (`Sertifikat Standar`, `NIB dan Sertifikat Standar`, **`KITAS`**),
`68210` Jasa Intermediasi Real Estat (`NIB dan Sertifikat Standar`, **`KITAS`**),
`70201` Konsultansi Manajemen (`NIB`, `Sertifikat Standar`, **`KITAS`**) — three of the codes a
Bali expat client is most likely to look up.

**And the TYPE is worse than the node.** `permit_type` — the entity type that admits `KITAS` — has
exactly **four** nodes on PROD (measured 2026-09-03): `permit:kitas` KITAS, `permit:kitap` KITAP,
`permit:itas` ITAS, `permit:itap` ITAP. **All four are immigration permits for a person; none is a
business licence.** `PERMIT_TYPES` carries `permit_type` on the strength of a comment reading
"permit taxonomy nodes" (`kbli_requires_kind.py:56`) — the one member of that frozenset whose live
population contradicts its label. Only `permit:kitas` has KBLI edges today; the other three are one
edge away from the same defect.

**The KITAS cure is a CLASSIFIER change, not a deletion — and this revision's own first draft got
that wrong.** The obvious move is to delete the nine edges the way §5.4 deletes the placeholder
ones. That would be the second defect wearing the shape of a fix that `kbli_requires_kind.py`'s own
design note warns about (_"A cure that quietly deletes 7,369 `dokumen` edges would be a second
defect wearing the shape of a fix"_, module docstring). The two cases are not the same shape:

- a **placeholder** node is named after a **status**. It duplicates the code's own
  `licensing_status` and carries zero information, so deleting its edge loses nothing — §5.4 stands.
- `kbli:55111 REQUIRES permit:kitas` is a **true relational fact in the wrong bucket**. It is the
  same kind of context as `company:pt_pma`, which the router already renders correctly on those very
  codes under `related_requirements.entity_forms`. Deleting it destroys information; re-bucketing it
  renders it honestly.

So the cure is **§8 F5**, promoted from a follow-up to Lot 0's first gesture: move `permit_type` out
of `PERMIT_TYPES` and into `_BUCKETS` as `immigration_permits`. `classify_requires_target` has
exactly one runtime consumer (`kbli_notebook.py:36,674` — every other reference is its own test
module), so the change is contained, and it covers KITAP / ITAS / ITAP before any of them acquires a
KBLI edge. After it, `55111` reports `licenses: []` with `related_requirements:
{"immigration_permits": ["KITAS"], "entity_forms": ["PT PMA"], "unspecified_permits": ["Izin"]}`,
and `55300` / `68210` / `70201` keep every real licence and gain one bucket entry. **No edge is
deleted, and Table B does not move** — those three stay legacy-served, and the six `<null>` codes
fall to zero admitted licences, which is exactly the state F8 then labels honestly. The missing node
is created by **`--create-missing-node`** (§5.9). None of this writes a licence, so none of it waits
on Phase 1a/1b or on Zero's §9 decision.

### 2.4 A third admitted-but-not-a-licence class exists, and this spec does not cure it

The §2.1 and §2.3 defects share a mechanism — a target passes both stages of the admission predicate
without being a permit — so the honest question is how many more there are. Measured 2026-09-03 over
the same dump: of the **2,447 distinct admitted targets**, **172** carry no licence-shaped token in
their name (no `NIB`, `Izin`, `Sertifikat`, `Persetujuan`, `Surat`, `Tanda`, `Akreditasi`,
`Penetapan`, `Rekomendasi`, `Lisensi`, `Registrasi`, `STTD`, `SIUP`, `Permit`, `License`), reaching
**221 codes** over **356** edges.

**That 172 is a SEARCH SPACE, not a defect count**, and saying otherwise would be the same
over-claim the round-1 draft made. Many are real permits known by acronym — `IPP-IRT`, `SPP-IRT`,
`STP Distributor/Agen`, `PMR`, `Uji Klinik`. But some are provably not, and they are served to
clients today exactly as `KITAS` is:

| target id                     | name                                                | codes                                      |
| ----------------------------- | --------------------------------------------------- | ------------------------------------------ |
| `parameter_lokasi_provinsi`   | "Lokasi industri berada pada Provinsi bersangkutan" | 10296, 10421, 10434, 13911, 14111, 14200 … |
| `parameter_lokasi_hamparan`   | "Lokasi Industri dalam Satu Hamparan"               | 10296, 10421, 10434, 14111, 14200, 28160 … |
| `layanan_keluhan_pelanggan`   | "Layanan keluhan pelanggan"                         | 20232, 20233, 21011, 21012 …               |
| `kerja_sama_operasi_kso`      | "Kerja Sama Operasi (KSO)"                          | 41016, 41017, 41019, 42991, 43215 …        |
| `produk_senjata_kimia`        | "Tidak menghasilkan produk senjata kimia"           | 20121                                      |
| `wajib_lapor_ketenagakerjaan` | "Wajib Lapor Ketenagakerjaan Perusahaan"            | 33121                                      |
| `license:npwp`                | "NPWP" — a tax identification number                | 33121                                      |

A location parameter, a complaint desk, a contracting form, a negative undertaking and a labour
report are not things a business obtains. They escape `permit_name_verdict` because it demotes on 23
opening verbs and a category-label list, and none of these opens with one (`Tidak` and `Lokasi` are
not verbs; `Layanan` and `Kerja` are nouns) — the same shape as `pending` escaping
`_UNKNOWN_ID_MARKERS` in §2.1.

**This spec does not cure it, and does not pretend to.** Its cure is per-target adjudication of 172
names against what a business actually obtains — a different kind of work from deriving licences
from `per_skala`, and one that must not be bolted onto a cure PR whose scope is the 175-code class.
It is **F9** (§8), it is sized here so the next session does not have to re-measure it, and §7's
`kg_stray_admission` check is deliberately phrased over admission so that whatever F9 demotes reads
as clean without the check changing.

## 3. The verdict convention (cross-store, stated once)

`licensing_status` is a function of the canonical record plus one frozen, declared exception:

| canonical                                                       | KG `licensing_status`                              | `licenses[]`                                         | mouth copy                            |
| --------------------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------- | ------------------------------------- |
| `per_skala` rows > 0                                            | `REGULATED`                                        | ≥ 1 admitted licence (§1 predicate; §4 derivation)   | licence names                         |
| `per_skala == []`, code on the frozen `NOT_APPLICABLE_OSS` list | `NOT_APPLICABLE_OSS` — **preserved, not asserted** | 0 admitted (measured true on all 75, §7 keeps it so) | "None (outside OSS licensing)"        |
| `per_skala == []`, otherwise                                    | `PENDING_REGULATION`                               | 0 admitted                                           | "Not listed in our data" (honest gap) |
| code not in canonical                                           | `NOT_IN_KBLI_2025` (out of scope)                  | —                                                    | —                                     |

- **No new enum value, but the non-OSS-issued codes are a product decision (§9).** 91 codes carry
  rows whose `persyaratan` say _"Lembaga OSS hanya menerbitkan NIB. Permohonan Perizinan Berusaha
  diajukan … ke Kementerian …"_ (472 rows; the phrase lives in `per_skala[].persyaratan` only — the
  one field that carries it); **61 unique** codes of the 175 (S1 26, S2 34, S3 1 — 85510 among
  them). They are regulated — the licence exists, the issuer is a ministry/dinas outside the OSS
  issuance path of PP 28/2025 Arts. 131(3)/132(2)/133(2). But `KBLILicense` has no issuer field and
  `requirements` is the row `kewajiban` (which for 85510 does name the ministry, while the
  `persyaratan` procedure stays invisible). Relabelling them `REGULATED` with a generic `NIB dan
Izin` before the issuer is rendered trades an honest-looking gap for a licence that hides who
  grants it. This spec therefore splits Phase 1 into **1a (OSS-issued: 114 codes)**, licensed now,
  and **1b (non-OSS-issued: 61 codes)**, gated on §8 F2 unless Zero rules otherwise. Inventing a
  `REGULATED_NON_OSS` status is not the alternative: the mouth translates exactly one status and
  would print the new one raw.
- **`NOT_APPLICABLE_OSS` is a freeze of the status quo, not a truth.** The canonical has no marker
  for it and its origin is out-of-tree. The 75 codes are recorded as data **in this PR**:
  `scripts/kbli_filiera/kg_oss_not_applicable_codes.json` (provenance block: measured on PROD
  2026-09-01, origin unknown, NOT adjudicated). Re-measured **2026-09-03** with the admission
  predicate over the whole dump: all 75 carry `licensing_status` exactly `NOT_APPLICABLE_OSS`, rows
  == 0 and **0 admitted permits** — all three properties, which is what §7's check now asserts — 56 carry `REQUIRES` edges (52 to
  `oss`-typed targets, 5 to `izin_usaha`-typed ones), and every one of those is demoted by
  `permit_name_verdict`, so the table's "none" is what a client sees today. That is an observation,
  not a guarantee: §7's `kg_allowlist_contradiction` check keeps it measured. The cure never touches
  a code on the list; adjudication per code against sector law is §8 F6.
- **`kbli_documents.metadata.licensing_status`** follows the same function once its inherited `N/A`
  is retired (§8 F1); until then it is read by no runtime consumer (PR #5513 grounding).

## 4. The derivation rule — from a v10 `per_skala` row to a licence

### 4.1 Legal basis — PP 28/2025, primary text, read this session

Source: _Peraturan Pemerintah Nomor 28 Tahun 2025 tentang Penyelenggaraan Perizinan Berusaha
Berbasis Risiko_, enacted 5 June 2025, batang tubuh 310 pp. + penjelasan 73 pp., downloaded from
`https://peraturan.bpk.go.id/Download/381375/PP%20Nomor%2028%20Tahun%202025.pdf` (page
`peraturan.bpk.go.id/Details/319773`), **sha256
`8808de485eab2499cf3d8369921c097beaea68ae55aa767c61095d47a5a118fb`**, text extracted with
`pdftotext -layout`; the articles below sit on printed pages 77–80. Quoted with the scanner's
artefacts removed (`(21` → `(2)`):

- **Pasal 128 (1)–(2)** — tiers: _"tingkat Risiko … ditetapkan menjadi: a. … tingkat Risiko rendah;
  b. … tingkat Risiko menengah; dan c. … tingkat Risiko tinggi. (2) Kegiatan usaha dengan tingkat
  Risiko menengah … terbagi atas: a. tingkat Risiko menengah rendah; dan b. tingkat Risiko menengah
  tinggi."_
- **Pasal 130** — _"PB untuk kegiatan usaha dengan tingkat Risiko rendah … berupa NIB yang merupakan
  identitas Pelaku Usaha sekaligus legalitas pelaksanaan kegiatan usaha."_
- **Pasal 131 (1)–(2)** — _"PB untuk kegiatan usaha dengan tingkat Risiko menengah rendah … berupa:
  a. NIB; dan b. Sertifikat Standar. (2) Sertifikat Standar … merupakan legalitas … dalam bentuk
  pernyataan Pelaku Usaha untuk memenuhi standar usaha"_ — **self-declared**.
- **Pasal 132 (1)–(2), (4), (6)** — _"PB untuk kegiatan usaha dengan tingkat Risiko menengah tinggi
  … berupa: a. NIB; dan b. Sertifikat Standar. (2) Sertifikat Standar … diterbitkan … berdasarkan
  hasil verifikasi pemenuhan standar pelaksanaan kegiatan usaha"_; (4) the OSS first issues a
  _"Sertifikat Standar yang belum terverifikasi"_ (preparation only, (5)); (6) NIB + the **verified**
  Sertifikat Standar is the PB for operation/commercial activity.
- **Pasal 133 (1)–(2)** — _"PB untuk kegiatan usaha dengan tingkat Risiko tinggi … berupa: a. NIB;
  dan b. Izin. (2) Izin … merupakan persetujuan Pemerintah Pusat, Pemerintah Daerah, Administrator
  KEK, dan/atau Badan Pengusahaan KPBPB … yang wajib dipenuhi oleh Pelaku Usaha sebelum
  melaksanakan kegiatan usahanya melalui Sistem OSS."_
- **Pasal 134** — verification under 132 is done by those authorities, optionally through
  accredited bodies.

The build PR pins this block as a module constant `LEGAL_BASIS = {"instrument": "PP 28/2025",
"pdf_sha256": "8808de48…18fb", "tiers": "Pasal 128", "Rendah": "Pasal 130", "Menengah Rendah":
"Pasal 131", "Menengah Tinggi": "Pasal 132", "Tinggi": "Pasal 133"}` and a unit test that asserts
`TIER` (below) against it — `--apply` refuses (`SystemExit(2)`) if the constant is absent or the
test module is missing, so the legal basis is a mechanical pre-apply gate, not a note.

### 4.2 The rule

Normalise first: `perizinan`, `kewenangan`, `kewajiban`, `persyaratan`, `skala_usaha` are read
through one helper that returns `[]` for `None`, `[s]` for a non-empty string, the list for a list,
and raises `shape_defect` for anything else — never iterate a string as characters.

1. `name(r)` = the normalised `r.perizinan` when non-empty (12 list-shaped entries in v10, all
   Menengah Tinggi → `NIB dan Sertifikat Standar`, consistent with the rule; plus the five string
   cases); otherwise `TIER[r.kategori_risiko]` with `TIER = {Rendah: "NIB" (Pasal 130), Menengah
Rendah: "NIB dan Sertifikat Standar" (131), Menengah Tinggi: "NIB dan Sertifikat Standar" (132),
Tinggi: "NIB dan Izin" (133)}`. Every v10 row has one of these four classes (unseen: 0).
   **Empirical fit on the 2,702 government legacy rows** (the import's own strings, dominant mapping
   with counter-examples stated): Rendah → `NIB` 704/707 (3 × `NIB dan Sertifikat Standar`); Menengah
   Rendah → `NIB dan Sertifikat Standar` 674/738 (+27 spelling/truncation variants, 25 blank, **3 ×
   `NIB`**); Menengah Tinggi → `NIB dan Sertifikat Standar` 760/842 (+~50 variants, 29 blank); Tinggi
   → `NIB dan Izin` 378/415 (+13 `NIB dan Izin (…)` sub-types, 7 truncated, **1 × `Sertifikat
Standar`**). The rule follows the statute; a v10 row that carries an explicit `perizinan` always
   wins over it.
2. **Menengah Rendah and Menengah Tinggi share a licence name but not a legal effect** (131(2) vs
   132(2),(6)). The node keeps the government string as `type` and carries the distinction as data:
   `kategori_risiko` (already rendered as `risk_level`) and `sertifikat_standar_verification ∈
{"self-declared", "verified", null}`. **Honesty about reach: no client sees this field until §8
   F2 renders it.** `KBLILicense` has no slot for it and the mouth prints none; Phase 1a therefore
   serves MR and MT under the same licence name with different `risk_level` — exactly what the
   legacy import already serves today on 1,166 codes, so 1a introduces no regression on this axis
   and F2 is where the distinction becomes visible (its gate is behavioural, §8).
3. Group the rows by `(name, kategori_risiko)` → one licence per group (03231: 20 rows → 2 groups,
   plus the legacy `Sertifikat Standar` node it carries today). Per group, **aggregation pinned**:
   `skala_usaha` = ordered union in `(Mikro, Kecil, Menengah, Besar)`; `jangka_waktu` = distinct
   non-blank values in first-seen row order joined by `/`; `kewajiban`, `persyaratan`,
   `kewenangan`, `scope_uraian` = ordered dedup, first-seen order; `fiktif_positif` = any();
   `pp28_row_indexes` = the rows' `scope_index` values **with `null` for a row that has none** —
   `scope_index` and `scope_uraian` are OPTIONAL (the five string-shaped rows lack both). A row whose
   `kategori_risiko` is missing/unknown, or whose `skala_usaha` is not a non-empty subset of the four
   scales, makes the **whole code refuse** — the posture of `plan_licensing_only` in
   `kbli_documents_cure.py`. **93111 is a mandatory fixture** (string `perizinan`, no scope fields).
4. Over the 169 S1 ∪ S2 codes this yields 1 licence on 145, 2 on 11, 3 on 2, 4 on 11; the 109 built
   Phase-1a codes need **155 target nodes**. `01122` joins them after Lot 0(c) with 3 groups (`NIB`
   [Rendah], `NIB dan Sertifikat Standar` [MR], the same [MT]; all four scales), so the post-Lot-0
   build is **110 codes / 158 target nodes** (`--census` prints the exact histogram).

## 5. The cure script — `kg_kbli_licensing_from_canonical.py` (new, `apps/backend-rag/backend/scripts/`)

Same scope discipline as `kg_kbli_license_fix.py` (`--only` mandatory, dry-run default, archive
before delete) — **not** its transaction shape: that script issues its DELETE and UPDATE without
`conn.transaction()` (`grep transaction` → 0 hits), and this one must not. Per `--only` code:

1. **Refuse** (build mode) unless canonical `per_skala` is a non-empty list of well-shaped rows (§4);
   a `[]` record is `kg_kbli_license_fix.py`'s job (except its placeholder edges — item 4); a code
   on the `NOT_APPLICABLE_OSS` list is refused; a non-OSS-issued code (§3) is refused unless `--phase
1b`, and `--phase 1b` is enabled by a module constant `PHASE_1B_ENABLED = False` that **only the
   §8 F2 PR flips**, in the same diff that adds the issuer field and its HTTP contract test — never a
   runtime grep, never a CLI flag alone. A missing `LEGAL_BASIS` (§4.1) refuses `--apply` outright.
2. **State, then eligibility.** Classify the code with the §1 predicate over its live edges:
   - **S1 / S2** (admitted = 0): build the §4 licences (items 3–4), set the status (item 5).
   - **S3** (admitted ≥ 1, `PENDING_REGULATION`): **nothing is written at all — no edges AND no
     status** (round 3 #3, folded; the 2026-09-02 draft relabelled these to `REGULATED`). The run
     compares the admitted names with the §4 derived names, logs both, and stops; the logged pair is
     the first entry of the Phase-2 diff (§6). Re-measured 2026-09-03 on the six Table-B S3 codes,
     the two sets differ on **6/6** and the derived set is strictly LARGER on five of them:

     | code  | rendered today (legacy)             | §4-derived from the canonical rows                                                       |
     | ----- | ----------------------------------- | ---------------------------------------------------------------------------------------- |
     | 25920 | `Nomor Induk Berusaha`              | `NIB dan Sertifikat Standar` [MR], `NIB dan Sertifikat Standar` [MT], `NIB dan Izin` [T] |
     | 52322 | `Izin Terbang`                      | `NIB` [R], `NIB dan Sertifikat Standar` [MR], [MT], `NIB dan Izin` [T]                   |
     | 55400 | `Izin Usaha Intermediasi Akomodasi` | `NIB` [R], `NIB dan Sertifikat Standar` [MR], [MT], `NIB dan Izin` [T]                   |
     | 65303 | `Izin Usaha Dana Pensiun`           | `NIB dan Izin` [T]                                                                       |
     | 85694 | `Izin Usaha Sertifikasi Profesi`    | `NIB dan Sertifikat Standar` [MT]                                                        |
     | 90200 | `Izin Usaha Pertunjukan Kesenian`   | `NIB` [R]                                                                                |

     Relabelling to `REGULATED` would make the answer **more affirmative** about a licence set this
     spec has not adjudicated — the statute says four tiers apply to `52322`, the graph renders one
     `Izin Terbang`, and neither the spec nor the cure knows which is right. That is the opposite of
     §6's non-regression claim. `REGULATED` is therefore reachable for an S3 code by exactly one
     route: **the rendered set and the derived set match exactly** — today, **zero codes** — in which
     case the relabel carries no new claim. The predicate belongs to the code, not to the runbook,
     and these six codes are its innocence corpus.

   - **legacy-served** (admitted ≥ 1, `REGULATED`): skipped with a logged reason; `--replace-legacy`
     is inert until §6 Phase 2 is measured (hard `SystemExit(2)` with the reason).
   - **CURED / DRIFTED** (item 7) are decided before any of the above.
3. **Target nodes carry the tier data (the router's contract, §1), one node per (code, group),
   code-scoped id:** `entity_id = f"perizinan:pp28v10:{code}:" + sha256(canonical_json(node_properties))[:12]`
   where **`node_properties` is the one and only object this spec knows** — the §4 group _plus_
   `source: "kbli_2025_v10_pp28"`, `sertifikat_standar_verification` and the `LEGAL_BASIS`
   instrument string — **built once, hashed as built, stored unchanged** (round 3 #6, folded: the
   2026-09-02 draft hashed a `payload` and stored `payload` + two more keys, so the id never covered
   the content it identified), with `canonical_json = json.dumps(node_properties, sort_keys=True,
ensure_ascii=False, separators=(",", ":"))`. Measured on the full canonical: a
   shared (cross-code) id hashed on five fields — the round-2 design — produced 974 ids for 2,088
   groups, **196 ids colliding with different full payloads** (1,275 group instances; the worst id
   had 175 instances and 18 distinct payloads), i.e. validate-on-conflict would have refused most of
   the catalog; the code-scoped id gives **0 collisions**. Consequence accepted: nodes are not shared
   across codes (the legacy import shared them; sharing bought nothing the router reads). `entity_type
= "perizinan"`, `name = <licence name>`, `properties = node_properties` exactly,
   `source_collection = "kbli_2025_v10_pp28"`. Insert; on an existing `entity_id` (same code, same
   content by construction) **validate** `entity_type` and `name` as strings and `properties`
   **by DECODED VALUE** — `loaded(row["properties"]) == node_properties`, where `loaded` is
   `json.loads` when the driver hands back a `str` and the value itself when it hands back a `dict`
   (the router does exactly this at `kbli_notebook.py:637-641,664-668`, because asyncpg returns
   `jsonb` either way depending on the codec). **Never "byte-equal"** (round 3 #6): the column is
   `JSONB` (`migration_028_knowledge_graph_schema.py:19`), which normalises whitespace, drops
   duplicate keys and reorders them on write — comparing bytes against a serialisation is a check
   that fails on a correct node. A colliding node whose decoded value differs is a finding: refuse
   the code, never overwrite.
4. **Edges:** `relationship_id = f"kbli:{code}|REQUIRES|{target}"`, `relationship_type = 'REQUIRES'`,
   `properties` = a copy of the group (for a future edge-reading router), `confidence = 1.0`,
   `source_collection = "kbli_2025_v10_pp28"`. Before insert, look for a **natural duplicate**
   `(source_entity_id, target_entity_id, relationship_type)` under any id — the schema has no unique
   constraint on it (`migration_028_knowledge_graph_schema.py:14-15,32-33`: PKs on `entity_id` /
   `relationship_id` only, non-unique indexes on source/target/type) — and treat one as
   already-present. **Placeholder edges — the three §2.1 ids, and ONLY those.** The §2.3
   `permit:kitas` edges are re-bucketed by F5 and never deleted (§2.3 says why). A placeholder edge
   is removed for every code the run touches, archived first into the KBLI node's
   `properties._replaced_requires_pp28v10` as `(target, at)` — append, never overwrite.
   **`--placeholders-only`** performs _only_ this deletion+archive, on any code carrying one of the
   three edges — 17 codes, regardless of rows, OSS status or phase, `85586` (`[]`) and the four
   non-OSS codes included — and writes nothing else: no status change, no licences, no node property
   beyond the archive key. The gesture is phase-independent by construction (a licence named after a
   status is false on every code whatever else that code gets) and may not be combined with a build
   or relabel mode in one invocation, so a lot's log says exactly what it did. **The test for
   deleting rather than re-bucketing is informational content**: a placeholder's name duplicates the
   code's own status and carries none; anything that carries some is re-bucketed instead.
5. **Node update** (build/relabel modes): `properties.licensing_status = "REGULATED"`,
   `properties.skala_usaha` = union over all rows, `properties.pp28_sources` = canonical
   `pp28_sources`, `properties._licensing_cure = {"run", "rows", "licences", "digest", "at"}`
   **written once on the run that cures; a no-op run never touches it**, `updated_at = now()`.
   Nothing else on the node moves.
6. **One transaction per code, all of it:** `SELECT … FOR UPDATE` on the `kbli:<code>` row, target
   inserts, archive, placeholder deletes, edge inserts, node update — commit or nothing. A failure
   after partial writes must leave the graph as it was (failure-injection test, item 10). Code-scoped
   targets mean two codes never contend on a shared node; two runs on the same code serialise on the
   row lock.
7. **Idempotence — three explicit states, decided from the graph, not from the marker.** Compute the
   derived id set `D` and its digest `d = sha256(sorted(D))`. **UNCURED**: no edge from the code to a
   `perizinan:pp28v10:{code}:*` node. **CURED**: the set of such targets equals `D`, every target's
   `properties` decode equal to `node_properties` (§5.3 — by value, never by bytes), the status is
   `REGULATED`, and
   `_licensing_cure.digest == d` → skip, write nothing (`0 of N cured | N skipped`, asyncpg command
   tags `INSERT 0 0` / `UPDATE 0`). **DRIFTED**: pp28v10 targets exist but ≠ `D`, or a payload
   differs, or the digest differs → **report, exit 4, write nothing**; drift handling (re-derivation
   after a canonical change) is Phase-2 scope and gets its own spec — there is no `--refresh-props`.
8. **Flags:** `--only <codes>` mandatory (no sweep, ever); `--census` (read-only: **both** §2 state
   tables — A live, B post-lot — under the shared predicate, the 1a/1b split, the licence histogram,
   the §2.3 one-store codes; exits 0/4); `--apply` (dry-run default, printing the exact licences per
   code); `--phase {1a,1b}` (default `1a`; `1b` refuses while `PHASE_1B_ENABLED` is `False`);
   `--placeholders-only`; `--create-missing-node` (item 9); `--cure-run
<label>`; `--dataset <path|url>`; `--replace-legacy` (`SystemExit(2)` until §6 Phase 2 lands).
   A build- or relabel-mode run refuses (`SystemExit(2)`) any code that still carries a placeholder
   edge — the §2 ordering rule, enforced in code and not in the runbook. After apply,
   same runbook step: `kbli_inspect_cache_bust.py --only <codes> --apply`, then `inspect_kbli` on ≥ 3
   codes of the lot with a **fresh** read (the pre-cure probes of 85510 / 03231 / 65121 made this
   session are poisoned for up to 30 days).
9. **Missing-node creation — `--create-missing-node` (round 3 #2, folded).** A canonical code with
   no `kbli:<code>` row cannot be cured, cannot carry an edge (`kg_edges.source_entity_id` is a FK
   onto `kg_nodes.entity_id`, `migration_028_knowledge_graph_schema.py:34`) and is answered with a
   404 — the navigator denying that a real KBLI-2025 code exists. Today that is exactly one code,
   `01122`. The flag takes `--only` like every other mode and refuses any code that already has a
   node or that is absent from the canonical. Inside the same single transaction as any other
   gesture: `INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties,
source_collection)` with `entity_type = "kbli"`, `name` = the canonical `judul`, `description` =
   the canonical `uraian`, and `properties` = **only what the canonical proves** — `kode`, `uraian`,
   `sektor_id`, `kategori_risiko` and `skala_usaha` derived from the rows, `pp28_sources`,
   `licensing_status` per the §3 function, and `_created_by = {"run", "at", "reason": "canonical
code had no KG node"}`. `source_collection = "kbli_2025_v10_pp28"` — **never** `kbli_2025_import`,
   which would claim a provenance this run does not have.
   **What the created node deliberately LACKS**, stated so no future reader takes the absence for a
   bug: the 1,568 imported `kbli:` nodes carry 14 property keys, five of them editorial prose
   (`whatChanged`, `whatItMeans`, `whatYouNeed`, `zantaraOpener`, `baliContext`) written by the
   out-of-tree February import, which this cure cannot synthesise. `inspect_kbli` reads **none** of
   the five — `kbli_notebook.py:781-796` builds `KBLIDetail` from `name`, `uraian`/`description`,
   `licensing_status`, `sektor_id`, the risk profile, `pp28_sources` and the PMA tuple — so the
   created node answers this router completely and honestly. The `/kbli/01122` mouth page, fed by
   the Qdrant gold content (`index_kbli_gold_content.py`), is NOT fixed by this insert; that is F7
   (§8). A real code with a real licence set and no editorial prose beats a 404.

10. **Tests (guilt AND innocence, superscar #3):** normaliser on `None`/str/list/other; `TIER` against
    `LEGAL_BASIS`; tier rule on all four classes + explicit-list precedence; 93111 fixture (string
    `perizinan`, absent scope fields → `null` index, no refusal); grouping (03231 → 2 groups, scale
    order, `jangka` join order); `sertifikat_standar_verification` per tier; code-scoped id — two
    codes with identical groups get distinct ids, one code re-derived gets the same id; refusal on
    `[]`, malformed rows, unknown risk class, allowlisted code, non-OSS code in `--phase 1a`, `--phase
1b` with the constant `False`, legacy-served code without `--replace-legacy`, colliding target
    node with different content; S3 code → status changes, `INSERT 0 0` on edges, comparison logged;
    natural-duplicate edge detected under a foreign id; `--placeholders-only` on a `[]` code removes
    and archives the edge and changes nothing else; CURED second run writes 0 rows and leaves
    `_licensing_cure` byte-identical; DRIFTED exits 4 with 0 writes; **rollback**: an injected failure
    between edge insert and node update leaves zero new rows; **concurrency**: two runs on the same
    code serialise on the row lock. Idempotence assertions read the asyncpg command tag, never
    `updated_at` (`CURRENT_TIMESTAMP` is frozen inside the test transaction).
    Added by this revision: **`--create-missing-node`** inserts a node whose `properties` hold only canonical-derived keys
    plus `_created_by`, refuses a code that already has a node and a code absent from the canonical;
    **S3 writes nothing** — a code with an admitted legacy licence and `PENDING_REGULATION` leaves
    the transaction with `INSERT 0 0`, `UPDATE 0` and an unchanged status, and the one synthetic case
    where rendered == derived DOES relabel (guilt for the exact-match route); **ordering** — a build
    or relabel run on a code still carrying a placeholder edge exits 2 and writes nothing; **decoded-value validation** — a stored `properties` that differs from `node_properties`
    only by key order and whitespace VALIDATES (innocence: the `JSONB` round-trip must not be read as
    a collision), one that differs by a value REFUSES.

Merging `apps/backend-rag/**` is the deploy (`fly-deploy.yml`); the apply runs from Pro after the
deploy, in lots of ≤ 25 codes, `dry-run → apply → bust → probe`, each lot's `--census` output and
apply log kept under `~/logs/kbli-conformance/`.

## 6. Scope and phases

- **Lot 0 — the three phase-independent gestures, before any licence is built:** **(a)** the F5
  classifier change (§8 — `permit_type` → `immigration_permits`, cache bump), which cures all 9
  §2.3 `KITAS` codes router-side without touching one edge; **(b)** `--placeholders-only` on all 17
  §2.1 codes (`85586` and the four non-OSS ones included); **(c)** `--create-missing-node --only
01122`. None writes a licence, none depends on Zero's §9 decision, and (b) is a hard predecessor of
  everything below (§2 ordering rule). Each is its own PR, its own lot, its own prove-live.
- **Phase 1a (this spec's first licence build), 110 codes acted on of 115 — `01122` included, and
  included precisely because Lot 0(c) only creates its node:** S1-OSS 44 (build + relabel), S2-OSS
  65 + `01122` (build), S3-OSS 5 (**nothing written** — the legacy/derived comparison is
  logged and becomes the first rows of the Phase-2 diff, §5.2); `kg_kbli_license_fix.py --only 91300`
  for the one `REGULATED` node over a canonical `[]`. Additive on the graph — nothing a client hears
  gets _less_, and nothing non-OSS-issued is relabelled.
- **Phase 1b, 61 codes:** S1 26 + S2 34 + S3 1, after §8 F2 renders the issuer (the F2 PR flips
  `PHASE_1B_ENABLED`) — or earlier only on Zero's ruling (§9). Until then those codes keep today's
  values (minus their placeholder edges).
- **Phase 2 (not licensed by this spec):** the 1,166 legacy-served codes — replacing import-era
  permit nodes with v10-derived ones, the `skala_usaha` node prop on the remaining ~730 codes, and
  DRIFTED handling. Precondition: a read-only diff of legacy-derived vs v10-derived licence sets per
  code (the six S3 pairs are its first rows), published and adjudicated per pattern; the legacy edges
  are government rows too, and replacing them without a measured diff is the cross-vintage fill the
  corner's north star forbids.
- **Not touched:** `dokumen` / `kewajiban` / `permen` edges (`related_requirements` lane —
  `kg_kbli_contradicted_obligations.py`); demoted permit-typed targets (352 + 241 edges — they stay
  where the router already puts them); the 11,039 nodes whose id starts with `kbli_` (underscore —
  the shadow-id family, `kg_fix_68112_node.py:198`; empty duplicates, separate hygiene lane); Qdrant
  point text for PP 28 (still unmeasured).

## 7. The detector — KG dimension in `kbli_surface_conformance.py`

Same organ, same wrapper (`kbli-surface-conformance-run.sh`), same `scripts/pg.sh` read path, same
exit codes (`0/1/4`, empty snapshot = 4 never 0). One more snapshot query over `kg_nodes` +
`kg_edges` — per `kbli:<code>`: status, and for every `REQUIRES` target its `(entity_id,
entity_type, name)` — evaluated in Python with **`client_admitted_permit` imported from
`kbli_requires_kind.py`**, the function the router calls (the build PR extracts it from
`kbli_notebook.py:674-689` and makes the router call it — one spelling, three consumers: router,
census, detector). Four checks, each with a **manifest** (the set of codes it is allowed to judge)
so that a check can be ENFORCED on what has been cured while the rest is still DECLARED:

**Every check runs in BOTH directions** (round 3 #5, folded). The 2026-09-02 draft asserted only
`rows > 0 ⇒ …`, so a code with zero canonical rows could acquire any status and any licence without
tripping anything — and the reverse direction is not hypothetical: measured 2026-09-03, **`91300`
has zero rows, status `REGULATED` and two admitted legacy licences**, and `85586` has zero rows and
a placeholder licence. A one-directional detector calls both of those clean.

- **`kg_status_function`** — rows > 0 ⇒ `REGULATED`, **and** rows == 0 ⇒ `PENDING_REGULATION`;
  `NOT_APPLICABLE_OSS` codes excluded and counted separately. Manifest = all **1,559** canonical
  codes **minus the 61 Phase-1b codes** (until 1b applies) **and minus the 6 Table-B S3 codes**
  (until Phase 2 adjudicates their legacy licence set). The S3 exclusion is not a convenience: §5.2
  deliberately leaves those six at `PENDING_REGULATION` over non-empty rows, so a manifest that
  contained them could never read 0 and the check could never be ENFORCED — the exclusion and the
  §5.2 fold are one decision seen from two sides, and the same Phase-2 PR lifts both. Manifest today
  = 1,559 − 61 − 6 − 75 = **1,417**. ENFORCED only after the 1a apply log reads 0. Measured today:
  76 codes fail the forward direction (70 S1 + 6 S3, of which only the 70 are in the manifest), 1
  fails the reverse (`91300`).
- **`kg_licence_presence`** — rows > 0 ⇒ ≥ 1 **admitted** permit, **and** rows == 0 ⇒ **0** admitted
  permits. Same manifest rule. **Not** a count equality — §2 shows why. Measured today, after Lot 0
  the reverse direction fails on exactly one code, `91300`.
- **`kg_stray_admission`** (was `kg_placeholder_edge`) — any code with an **admitted** edge to one
  of the three §2.1 placeholder ids or to a node of type `permit_type`. Phrased over ADMISSION, not
  over edge existence, because the two cures differ: after F5 a `permit:kitas` edge still exists and
  is no longer admitted, and that must read as clean. DECLARED until Lot 0 lands, then **ENFORCED
  catalog-wide** — no phase manifest, the gestures are phase-independent.
- **`kg_allowlist_contradiction`** — an allowlisted code that fails ANY of: zero canonical rows,
  zero admitted permits, `licensing_status` exactly `NOT_APPLICABLE_OSS`. The status itself is now
  asserted, not assumed (round 3 #5). Measured 2026-09-03: **75/75 pass all three**. DECLARED in the
  PR that lands the check, ENFORCED after its first log reads 0. The JSON's own note already says
  this correctly — _"Never enforced as TRUTH; a detector may enforce the freeze itself (zero rows,
  zero admitted permits, exact status `NOT_APPLICABLE_OSS`)"_ — so no edit to
  `kg_oss_not_applicable_codes.json` is needed; the contradiction the refuter reported was between
  that note and §7's older text, and it is §7 that moves.
- **`kg_node_presence`** (new, round 3 #2) — every canonical code has a `kbli:<code>` node, **and**
  every `kbli:<5 digits>` node is either canonical or carries `NOT_IN_KBLI_2025`. Measured today:
  1 failure forward (`01122`), 6 reverse (the §2.3 `<null>` codes). Catalog-wide, no manifest.
  ENFORCED after `--create-missing-node` and a status write on the six (§8 F8).

The DECLARED → ENFORCED flip of each check is its own one-line PR after the log shows the check at
0 on its manifest — never in the same PR as the cure (W116: arm the alarm against a state that was
observed, not promised).

## 8. Follow-ups this spec creates (declared, not scheduled here)

- **F1** — `kbli_documents.metadata.licensing_status`: retire the inherited `N/A`; make
  `licensing_metadata_from_canonical` in `kbli_documents_cure.py` emit the §3 function. Rides the
  next backend PR on that script (the stale `build_cured_metadata` docstring is already ledgered).
- **F2 (gates Phase 1b)** — router increment: additive `issuer` (from `kewenangan`), **`procedure`
  (from `persyaratan`)** and `verification` (§4.2) fields on `KBLILicense`, read from the target
  node; cache key `v6` → `v7`; both mouth renderers print the issuer, **the procedure sentence** and
  the self-declared/verified qualifier on the licence line. **`procedure` is the load-bearing half,
  and this is measured, not assumed** (2026-09-03, over the 61 non-OSS codes): `kewenangan` carries
  **three generic role labels and nothing else** — `Menteri/Kepala Badan` 608 rows,
  `Bupati/Walikota` 72, `Gubernur` 16 — and names a specific institution on **zero** rows, whereas
  the `persyaratan` phrase names the actual body on **61/61** codes (12 distinct texts, e.g. `64122`
  → _"…diajukan oleh Pelaku Usaha ke, diterbitkan oleh … Otoritas Jasa Keuangan (OJK)…"_). An F2
  that shipped `issuer` alone would render "issued by Menteri/Kepala Badan" and answer nothing.
  **Two PRs, not one (round 3 #4, folded):**
  1. the **F2 PR** adds the three fields, the `v7` key, an HTTP contract test on `inspect_kbli`
     asserting all three (guilt + innocence) and a mouth render test that asserts the **procedure**
     line as well as the issuer line — and leaves `PHASE_1B_ENABLED = False`;
  2. a **separate one-line PR** flips the constant, opened only after the F2 increment is proven
     live on **both** production surfaces — `inspect_kbli` on Fly returning the three fields on a
     cured code, and the rendered `/kbli/<code>` page on Vercel showing the procedure line. The
     2026-09-02 draft flipped the constant in the source PR, i.e. before either deploy existed:
     merged is not live.
- **F3** — the corner's PMA entry ("`inspect_kbli` reads Qdrant first") is true of the PMA tuple
  only; for licensing the KG is primary and mandatory (after the cache). Corrected in the corner in
  this PR.
- **F4** — node `skala_usaha` disagrees with the canonical union on 881/1,341 codes; Phase 1 fixes
  its share, Phase 2 the rest.
- **F5 — promoted to Lot 0(a); it IS the KITAS cure, not a follow-up.** `kbli_requires_kind.py`,
  two changes, one router-side PR, cache bump:
  1. **Move `permit_type` out of `PERMIT_TYPES` and into `_BUCKETS` as `immigration_permits`.** All
     four live nodes of that type are personal immigration permits (KITAS / KITAP / ITAS / ITAP,
     measured on PROD 2026-09-03). Guilt corpus: those four, none admitted. **Innocence corpus: the
     4,722 admitted ids measured 2026-09-03 minus the 9 `permit:kitas` edges — all 4,713 must stay
     admitted**, which is what makes this the demotion of one type and not a widening.
  2. Add the three §2.1 placeholder ids and the id tokens `pending` / `pending_regulation` to the
     non-admission markers, so a future placeholder cannot reach `licenses[]` even before its edges
     are removed (guilt: the three nodes; innocence: the same 4,713).
- **F6** — adjudicate the 75 `NOT_APPLICABLE_OSS` codes per code against sector law; until then the
  list is a freeze, never enforced as truth.
- **F7** (opened by §5.9) — a node created by `--create-missing-node` answers `inspect_kbli`
  completely but has no Qdrant gold content, so `/kbli/01122` on the mouth is still unfed.
  `index_kbli_gold_content.py` is the organ; own lane, own PR, after the node exists.
- **F9** (opened by §2.4) — adjudicate the 172 admitted targets whose names carry no licence-shaped
  token (221 codes, 356 edges) one by one: real permits known by acronym stay admitted, parameters /
  obligations / contracting forms / negative undertakings get demoted into the bucket that already
  describes them. Router-side, own lane, cache bump; guilt corpus the six tabled in §2.4, innocence
  corpus the acronym permits (`IPP-IRT`, `SPP-IRT`, `STP Distributor/Agen`, `PMR`, `Uji Klinik`) plus
  the 4,713 of F5. Not part of this spec's build.
- **F8** (opened by §2.3) — the six KG-only codes with a `<null>` status (55111, 62011, 62021,
  68110, 73110, 74100) are served as `REGULATED` by the router's read-time default. Write
  `NOT_IN_KBLI_2025` on them, as the other four KG-only codes already carry, so the graph says what
  it knows. Own PR; it is the precondition for ENFORCING the reverse direction of
  `kg_node_presence` (§7).

## 9. Owner decisions

One, and it gates Phase 1b only: **the 61 non-OSS-issued codes** (Table B: S1 26, S2 34, S3 1 —
85510 among them). Nothing else in this spec waits on it: Lot 0 (§6), Phase 1a's 109 built codes,
the detector and F1/F5/F7/F8 all proceed either way. Both options priced on 2026-09-03
(`ZERO-DECISIONS.md` item 2 carries the same two rows):

|                           | **Option A — gate on F2** (recommendation)                                                                                                                                                                                                                         | **Option B — relabel now**                                                                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| what a client sees        | nothing changes until F2 ships; then `REGULATED` + the statute licence + **the procedure sentence naming OJK / the ministry**                                                                                                                                      | `REGULATED` + `NIB` / `NIB dan Sertifikat Standar` / `NIB dan Izin`, with no indication that OSS will not issue it                                                   |
| diff to write first       | F2 router increment (3 fields on `KBLILicense`, cache `v6`→`v7`, 2 mouth renderers, 2 test files) + a 1-line flip PR + 3 cure lots                                                                                                                                 | 3 cure lots only; **zero** new router or mouth lines                                                                                                                 |
| codes / target nodes      | 61 codes, **63** target nodes (59 codes → 1 licence, 2 → 2)                                                                                                                                                                                                        | identical                                                                                                                                                            |
| measured risk             | delay only. The data is ready: `persyaratan` names the issuing body on **61/61** codes (12 distinct texts)                                                                                                                                                         | a client is told to obtain `NIB dan Izin` through OSS when OSS issues only the NIB — the wrong door, on codes like `85510` (yoga/retreat) and `64122` (OJK-licensed) |
| what neither option fixes | `kewenangan` — the field an `issuer` line would read — is **three generic role labels** (`Menteri/Kepala Badan` 608 rows, `Bupati/Walikota` 72, `Gubernur` 16) and names **zero** institutions. `issuer` alone answers nothing; `procedure` is the half that does. | same                                                                                                                                                                 |

Recommendation stands with A, and the measurement strengthens it: the procedure text exists for
every one of the 61, so the gap A waits on is engineering time, not missing data. Phase 1a needs no
decision. The 1,505-code PMA `NOT_VERIFIED`-by-design question from 2026-09-01 is unrelated and
stays open.

## 10. Proof-of-armed (replaces the ledger row's original proof)

Lot 0 first — each of its three gestures proves itself before any licence is built:

1. `inspect_kbli` on **all 17** §2.1 codes, post-bust, no longer lists a licence named
   `PENDING_REGULATION` (today `65121` does — re-proven live 2026-09-03).
2. `inspect_kbli` on **all 9** §2.3 codes, after the F5 deploy and cache bump, no longer lists
   `KITAS` under `licenses[]` and DOES list it under `related_requirements.immigration_permits` —
   nothing deleted; `55300` / `68210` / `70201` still list every real licence they list today
   (innocence). Read from the deployed Fly app, never from the merged diff.
3. `inspect_kbli 01122` returns HTTP **200** with `title` = the canonical `judul`, `sector` and
   `risk_profile` from the created node, `licensing_status: REGULATED` and **`licenses: []`** —
   because Lot 0(c) creates a node and writes no licence. That is the honest S2 shape ("Not listed
   in our data"), which is what the other 99 S2 codes show today and is strictly better than a 404
   denying the code exists. **Its three licences arrive at step 7**, where `01122` is the 110th
   built Phase-1a code. Claiming the licence set here would be claiming a build from a gesture that
   performs none.
4. `--census` re-run: Table A now equals Table B, and both read S1 70 / S2 99 / S3 6.

Then Phase 1a:

5. `--census` lists 0 Phase-1a codes remaining in S1 and S2 (44 / 66 after Lot 0(c) — 65 on
   2026-09-03 plus `01122`; S3's 5 are logged, never cured).
6. For each of the **17 detector codes in 1a** (the 20 S1 + 2 S3 minus 65111, 65121, 85102, 85510,
   85520), a **post-bust** `inspect_kbli` returns, for the 15 S1 codes, `licensing_status:
REGULATED` and a non-empty `licenses[]` whose `type` set equals the §4 rule applied to the canonical
   rows with `scale` = the rows' scale union; for `85694` / `90200` — S3 — **both the legacy licence
   and `PENDING_REGULATION` are unchanged**, which is the §5.2 fold and is verified as innocence,
   not as a cure. (03231/03232/03233 keep their legacy entries until Phase 2; the five 1b codes are
   judged after 1b.)
7. `inspect_kbli 01122` now returns its 3 licences (`NIB` Rendah, `NIB dan Sertifikat Standar` MR
   and MT), `scale` covering all four scales — the second half of the `01122` proof, and the half
   that needs a licence build.
8. The detector's **five** KG checks read 0 in **both directions** on their manifests in
   `~/logs/kbli-conformance/`, and each ENFORCE flip PR is merged separately after its log shows 0
   (W116). `kg_licence_presence`'s reverse direction is allowed exactly one known exception,
   `91300`, until `kg_kbli_license_fix.py --only 91300` has run.
9. A second `--apply` on any lot writes 0 rows (asyncpg tags `INSERT 0 0` / `UPDATE 0`) and leaves
   `_licensing_cure` byte-identical.

## Adversarial review

Seat: Codex GPT-5.6 `sol`, refute stance, read-only on the worktree (Kimi K3 unavailable — weekly
quota exhausted, 403 measured). Fold status is stated per finding: **closed** (verified and the spec
now matches), **partial** (folded, with a named remainder), **open** (carried, not folded).

**Round 1: BLOCKED** — 3 blockers, 5 majors, 1 minor.

| #   | finding                                                                                                    | verified                                                                                                    | status after round 2                                                                                                                   |
| --- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | router reads tier data from the target node, not `edge_props`                                              | yes — `kbli_notebook.py:664-668,691-698`; legacy node props read on PROD                                    | closed — §1, §5.3                                                                                                                      |
| 2   | the three placeholders are NOT demoted; `pending` is no marker; the denominator used a different predicate | yes — `kbli_requires_kind.py:178,255`; live `inspect_kbli 65121`                                            | closed in round 3 — the round-2 recount ("148/76") still used a paraphrase of the predicate; §1/§2 now use the router's function (175) |
| 3   | global detector checks could never reach 0 with Phase 2 deferred                                           | yes (logic)                                                                                                 | closed — §7 manifests; placeholder check phase-independent (round 3)                                                                   |
| 4   | non-OSS codes relabelled with a generic licence would hide the issuer — a product decision                 | yes — `KBLILicense` has no issuer field                                                                     | closed — §3, §6, §9, F2 behavioural gate (round 3)                                                                                     |
| 5   | MR vs MT collapse a legal distinction; article numbers deferred                                            | round 2: accepted as an assertion; **round 3: primary text read** (PP 28/2025 Pasal 128–134, sha256 pinned) | closed — §4.1, §4.2, `LEGAL_BASIS` gate; reach limited to F2 stated honestly                                                           |
| 6   | `NOT_APPLICABLE_OSS` allowlist is not a canonical truth                                                    | yes                                                                                                         | closed — §3 freeze, file created, measured 0 admitted, §7 contradiction check                                                          |
| 7   | no transaction; no natural uniqueness on edges; `ON CONFLICT DO NOTHING` hides a bad node                  | yes — `grep transaction` → 0; PK-only schema `:14-15,32-33`                                                 | closed — §5.3–5.7 (round 2's node identity was itself broken; round 3 fixed it)                                                        |
| 8   | canonical shape claims imprecise (5 string codes, 4 key sets, legacy counter-examples)                     | yes — recomputed                                                                                            | closed — §2.2, §4.2 (five scope-less rows added in round 3)                                                                            |
| 9   | `kg_subgraph_company.py` does not consume permit edges                                                     | yes                                                                                                         | closed — §1                                                                                                                            |

**Round 2: BLOCKED** — 5 blockers, 5 majors, 1 minor. Every finding was re-derived by two independent
readers (a Sonnet 5 code reader on the cited lines; a Sonnet 5 data reader on the canonical and the
census dumps) and, where PROD was needed, re-measured this session with the router's own predicate:

| #   | finding                                                                                                                    | verified                                                                                                     | status                                                                                                                                                                             |
| --- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | build/relabel classes overlap (69 shared; union 155 not 224; "78 non-OSS" double-counted; 22-vs-17 detector codes)         | yes — recomputed from the dumps: ∩ = 69, ∪ = 155, unique non-OSS 52 under that predicate                     | closed — §2 disjoint states S1/S2/S3 (175 / 61 / 114 under the real predicate), §5.2 per-state actions, §10 says 17                                                                |
| 2   | the shared target-node id hashes 5 fields but the node carries the full payload → collisions refused as conflicts          | yes — 2,088 groups, 974 ids, 196 colliding (1,275 instances; worst 175 × 18); code-scoped id → 0             | closed — §5.3 code-scoped id over the full payload, canonical encoding pinned                                                                                                      |
| 3   | "permit-typed minus placeholders" is not the router predicate (`permit_name_verdict` demotes permit-typed targets too)     | yes — `kbli_notebook.py:674-689`; PROD: 5,318 permit-typed, 4,699 admitted; 21 codes move into the build set | closed — §1 predicate, all denominators recomputed, §7 single export                                                                                                               |
| 4   | the legal premise of `TIER` was unverified (folded as an assertion)                                                        | yes — round 2 had not opened the gazette                                                                     | closed — §4.1 primary text read this session, Pasal 128/130–134 quoted, PDF sha256, `LEGAL_BASIS` pre-apply gate                                                                   |
| 5   | the plan could not remove all 17 placeholder edges (85586 has 0 rows; 4 codes are non-OSS/1b)                              | yes — 85586 rows = 0; 65121/65301/85542/88907 carry the non-OSS phrase                                       | closed — §5.4 `--placeholders-only` phase-independent, §7 check catalog-wide, §10.3 all 17                                                                                         |
| 6   | MR/MT distinction written but not rendered; F2 gate was a grep                                                             | yes — `KBLILicense:79-84`, both mouth renderers, no `verification` slot                                      | partial — §4.2 states the reach honestly (1a serves MR/MT as the legacy import does); F2 gate is now the F2 PR's own contract tests + constant flip; the rendering itself stays F2 |
| 7   | idempotence underspecified (eligibility skips the validation; `--refresh-props` contradicts itself; marker not write-once) | yes (logic)                                                                                                  | closed — §5.7 UNCURED/CURED/DRIFTED with digest, marker write-once, `--refresh-props` removed                                                                                      |
| 8   | `NOT_APPLICABLE_OSS` "none" was not enforced; 5 permit-typed targets unmeasured                                            | yes — measured: all 5 demoted, 0 admitted on all 75                                                          | closed — §3 measured statement, §7 `kg_allowlist_contradiction`                                                                                                                    |
| 9   | five rows lack `scope_index`/`scope_uraian`; grouping required both                                                        | yes — exactly the five string-shaped rows                                                                    | closed — §4.2.3 optional scopes, 93111 fixture                                                                                                                                     |
| 10  | the round-1 table's blanket "all folded" was false                                                                         | yes — see the per-row status above                                                                           | closed — per-finding status, both tables                                                                                                                                           |
| 11  | two citations overstated ("KG first"; `kbli_documents_cure.py:443` "N/A otherwise")                                        | yes — cache first `:609-614`; `:441-445` preserves the old status on rows, defaults to `N/A`                 | closed — §1, §2                                                                                                                                                                    |

**Round 3: BLOCKED** — 4 blockers, 2 majors, read against the PROD dump, the recompute script, the
gazette text and the code. Agent PR Contract §8 forbade a fourth round on that draft, so the lane
suspended with the six findings tabled. **All six are folded in this r4 revision**, each against a
measurement re-taken on 2026-09-03 from a fresh dump rather than re-derived from the old one:

| #   | finding                                                                                                                                     | folded where                                                                                                                                                                                    |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | placeholders are admitted, so live state is S1 54 / S2 99 / S3 22; the ordering was unstated; the intersection filter dropped KG-only edges | **closed** — §2 Tables A and B, both printed by `--census`; the ordering is a `SystemExit(2)` in §5.8, not a runbook step; §1 recomputed over all 13,344 edges (4,722 / 355 / 241, sum = 5,318) |
| 2   | canonical `01122` has 8 rows and no KG node; no creation path; KG-only codes are 10                                                         | **closed** — §2.3 states both one-store classes, §5.9 is the transactional creation path, §7 adds `kg_node_presence`, every manifest is over all 1,559                                          |
| 3   | relabelling S3 to `REGULATED` asserts a legacy licence set that differs from the derived one on 6/6                                         | **closed** — §5.2: an S3 code gets **no write at all**; `REGULATED` is reachable only on an exact rendered/derived match (today zero codes); the 6/6 comparison is tabled                       |
| 4   | `PHASE_1B_ENABLED` flips before prove-live; F2 never tests `procedure`                                                                      | **closed** — §8 F2 is two PRs: the increment (constant stays `False`, `procedure` rendered and tested) and a separate flip PR after Fly **and** Vercel are proven                               |
| 5   | detectors are one-directional; the allowlist's own status is not asserted; the JSON note contradicts §7                                     | **closed** — §7 runs every check both ways (the reverse direction is not hypothetical: `91300` fails it today), the allowlist check asserts all three properties, and §7 — not the JSON — moved |
| 6   | the hashed `payload` and the stored `properties` are two objects; "byte-equal" is not how JSONB compares                                    | **closed** — §5.3: one `node_properties` object, hashed as built, stored unchanged, compared by **decoded value** (`JSONB`, `migration_028_knowledge_graph_schema.py:19`)                       |

### Round 4 (2026-09-03) — what re-measuring found that no refuter had

Re-taking the six measurements over the **whole** dump instead of the intersection surfaced four
things the three refuter rounds could not have seen, because every previous census had filtered out
the codes they live on:

1. **Nine codes serve `KITAS` as a business licence** (§2.3), `55111` "Hotel Bintang Lima" among
   them, and three of them — `55300`, `68210`, `70201` — are canonical, `REGULATED` and hide it
   beside real licences. Proven live this session. This is a bigger client-facing surface than the
   17 placeholder codes and it was in no draft. Its cure is a classifier demotion, not a deletion:
   `permit_type` holds four nodes and all four are personal immigration permits.
2. **The 2026-09-02 admission triple did not close arithmetically**: `4,699 + 352 + 241 = 5,292`
   against its own 5,318 denominator. The whole-dump numbers are `4,722 + 355 + 241 = 5,318`. The
   refuter estimated the dropped edges at 9; the dump says 26.
3. **`kewenangan` cannot answer "who grants it"** — three generic role labels over the 61 non-OSS
   codes, zero named institutions — while `persyaratan` names the body on 61/61. F2's `issuer` half
   is decorative and its `procedure` half is the whole point (§8 F2, §9).
4. **The reverse direction of the row/licence invariant fails today on a real code**: `91300` has
   zero canonical rows, status `REGULATED` and two admitted legacy licences. Round 3 #5 argued this
   from logic; it is now measured.
5. **The admission hole is wider than either named class** (§2.4): 172 of the 2,447 distinct
   admitted targets carry no licence-shaped token, over 221 codes — a search space, not a defect
   count, but it provably contains location parameters, a complaint desk and "Tidak menghasilkan
   produk senjata kimia" being served as permits. Declared as F9 and deliberately left outside this
   spec's build.

**Verified live in this session** (the round-3 refuter could not, its sandbox had no route to Pro or
to the API): `inspect_kbli` on `65121` (placeholder licence still served), `55111` (`KITAS`) and
`01122` (HTTP 404). **Re-measured from the 2026-09-03 dump**: every count in §1, §2, §2.3, §3, §5.2,
§7, §9 and §10 above. **Still unverified and declared**: the 13,344-edge type distribution and the
881 `skala_usaha` figure are carried from 2026-09-02 unchanged (not recomputed here), and the "two
independent readers" claim for round 2 remains procedural with no artefact.

### The r4 adversarial round — PARTIAL, and reported as partial

Seat: Codex GPT-5.6 `sol`, `xhigh`, refute stance, read-only, fresh context, with the dump and the
recompute scripts handed to it (generator ≠ grader — none of the r4 text is its own). **It exhausted
its turn budget before writing the findings table**, so this round is a partial gate, not a clean
one. What it did produce is not nothing and is folded above; what it did not produce is not counted
as a pass. Two findings it named explicitly, both re-verified here before folding:

| #   | finding (its words, translated)                                        | verified                                                                                                    | fold                                                                                                                                                                                                  |
| --- | ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| a   | "the path for `01122` cannot produce the licences the proof requires"  | yes — Lot 0(c) creates a node and writes no edge; §10.3 as drafted demanded a licence set from that gesture | §10.3 now proves the S2 shape (`licenses: []`, 200 not 404) and the licences move to §10.7; `01122` is measured OSS-issued with 3 groups and joins Phase 1a → union 176 / 115 / 110 built / 158 nodes |
| b   | "the five S3-OSS codes left untouched stop the detector reaching zero" | yes — §5.2 leaves the 6 S3 codes `PENDING` over non-empty rows, which `kg_status_function` forward-fails    | §7's manifest now excludes the 6 S3 codes as it excludes the 61 Phase-1b ones; manifest = 1,559 − 61 − 6 − 75 = 1,417, and one Phase-2 PR lifts both exclusions                                       |

Its last probe before running out was aimed at the §2.4 class (`license:npwp`,
`pemutakhiran_data_perizinan`); `NPWP` — a tax number — is indeed admitted as a licence on `33121`
and is now in §2.4's table. **Still ungraded by any refuter**: §4's derivation rule, §5's transaction
and idempotence design, and §2.4/F9 itself. A build PR out of this spec must carry its own
adversarial gate; passing this section off as a completed round would be exactly the "green ≠
working" the superscar file's family #2 is made of.

**Status of the suspension.** The 2026-09-02 suspension was correct and stands as history: that
draft was not buildable. This r4 revision is a different design on the same measured surface — the
six findings are folded, not re-argued — so it is not a fourth round on the suspended draft.

The measured facts of §1–§2 and the legal basis of §4.1 stand; §5–§7 are the design as revised.
