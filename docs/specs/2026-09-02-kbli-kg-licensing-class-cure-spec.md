# Spec — the KG tells clients "PENDING_REGULATION" on codes whose government licensing rows exist, and no script can cure it

**Date:** 2026-09-02 · **Status:** **SUSPENDED 2026-09-02 — Agent PR Contract §8: three refuter rounds
BLOCKED, no fourth round. NOT BUILDABLE AS WRITTEN: the six open round-3 findings (last section) must be
folded and re-refuted before any script exists. Kept on `main` as the measured record so the next session
reopens from those six findings, not from a fresh derivation.** Nothing implemented. · **Surface:** `kg_nodes` /
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
  (`:686-688`). **`pending` is not a marker** — see §2.1. Measured on PROD 2026-09-02 over the
  5,318 permit-typed edges from `kbli:` nodes: **4,699 admitted**, 352 demoted `unspecified_permits`,
  241 demoted `obligations`, 17 to the three placeholders (admitted — the hole). The spec calls this
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

KG: 1,568 `kbli:<5 digits>` nodes; 1,558 exist in both stores (**10** KG codes absent from canonical;
**1 canonical code, `01122`, with 8 rows and NO KG node** — the router 404s on it and neither
`kg_kbli_resync.py:229-238` nor §5 as written creates a node: open, round 3 #2). `licensing_status`: `REGULATED 1266 · PENDING_REGULATION 217 ·
NOT_APPLICABLE_OSS 75 · <null> 6 · NOT_IN_KBLI_2025 4`. `REQUIRES` edges from KBLI nodes: 13,344,
to 35 target types — `dokumen 7369 · perizinan 2097 · izin_usaha 1935 · license 1167 · kewajiban 174
…`; only the admitted subset (§1) renders as a licence.

**The classes are DISJOINT STATES of a code, not two overlapping lists.** Over the 1,341 codes present
in both stores with rows > 0, by (admitted permits, status):

| state  | definition                                                       | codes                                            | non-OSS-issued (§3) | Phase-1 action (§5.2)                   |
| ------ | ---------------------------------------------------------------- | ------------------------------------------------ | ------------------- | --------------------------------------- |
| **S1** | admitted = 0, `PENDING_REGULATION`                               | **70**                                           | 26                  | build licences + relabel                |
| **S2** | admitted = 0, `REGULATED` (rendered as "Not listed in our data") | **99**                                           | 34                  | build licences                          |
| **S3** | admitted ≥ 1, `PENDING_REGULATION`                               | **6** — 25920, 52322, 55400, 65303, 85694, 90200 | 1 (65303)           | relabel only, after the §5.2 comparison |
| —      | admitted ≥ 1, `REGULATED` (legacy-served, Phase 2)               | 1,166                                            | —                   | none                                    |
| —      | admitted = 0, other status                                       | 0                                                | —                   | —                                       |

**Ordering caveat (round 3 #1):** the table is the state _after_ the placeholder edges are gone. Today
the router ADMITS the three placeholders, so the 16 rows > 0 placeholder codes are live S3, not S1 —
**live S1 54 / S2 99 / S3 22**; the census script that produced 70/99/6 labelled placeholders
separately (`kg_r3_recompute.py:65-73`), which the router does not. The `--placeholders-only` lot is a
hard predecessor of every state-driven action, and `--census` must print both states.
**Union S1 ∪ S2 ∪ S3 = 175 codes**; non-OSS-issued 61; **Phase 1a = 114** (S1 44 + S2 65 + S3 5),
**Phase 1b = 61** (S1 26 + S2 34 + S3 1). Outside the rows > 0 set: rows == 0 & `PENDING_REGULATION`
141 (consistent); rows == 0 & `NOT_APPLICABLE_OSS` 75 (all of that status, §3); rows == 0 &
`REGULATED` **1** — `91300` (the shape `kg_kbli_license_fix.py` already cures).

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
  2026-09-01, origin unknown, NOT adjudicated). Re-measured 2026-09-02 with the admission
  predicate: all 75 have rows == 0 and **0 admitted permits** — 56 carry `REQUIRES` edges (52 to
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
4. Over the 169 S1 ∪ S2 codes this yields 1 licence on 145, 2 on 11, 3 on 2, 4 on 11; Phase 1a
   (109 of them) needs **155 target nodes** (`--census` prints the exact histogram).

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
   - **S3** (admitted ≥ 1, `PENDING_REGULATION`): **no edge writes.** Compare the set of admitted
     names with the §4 derived names and log both; set the status to `REGULATED` (rows exist and a
     licence is already rendered — the current pair "PENDING + a licence" is self-contradictory);
     the logged pair is the first entry of the Phase-2 diff (§6). Measured today: the sets differ on
     6/6 (each S3 code renders one specific legacy permit — `Izin Terbang` on 52322, `Izin Usaha Dana
Pensiun` on 65303 … — where the statute-derived name is generic), which is exactly why no v10
     edge is added next to a government-specific one without the Phase-2 adjudication.
   - **legacy-served** (admitted ≥ 1, `REGULATED`): skipped with a logged reason; `--replace-legacy`
     is inert until §6 Phase 2 is measured (hard `SystemExit(2)` with the reason).
   - **CURED / DRIFTED** (item 7) are decided before any of the above.
3. **Target nodes carry the tier data (the router's contract, §1), one node per (code, group),
   code-scoped id:** `entity_id = f"perizinan:pp28v10:{code}:" + sha256(canonical_json(payload))[:12]`
   where `payload` is the **whole** §4 group (every property that will be written on the node, the
   `LEGAL_BASIS` instrument string included) and `canonical_json = json.dumps(payload,
sort_keys=True, ensure_ascii=False, separators=(",", ":"))`. Measured on the full canonical: a
   shared (cross-code) id hashed on five fields — the round-2 design — produced 974 ids for 2,088
   groups, **196 ids colliding with different full payloads** (1,275 group instances; the worst id
   had 175 instances and 18 distinct payloads), i.e. validate-on-conflict would have refused most of
   the catalog; the code-scoped id gives **0 collisions**. Consequence accepted: nodes are not shared
   across codes (the legacy import shared them; sharing bought nothing the router reads). `entity_type
= "perizinan"`, `name = <licence name>`, `properties` = `payload` (+ `source:
"kbli_2025_v10_pp28"`, `sertifikat_standar_verification`), `source_collection =
"kbli_2025_v10_pp28"`. Insert; on an existing `entity_id` (same code, same content by
   construction) **validate** `entity_type`, `name`, `properties` byte-equal, else refuse the code — a
   colliding node with different content is a finding, never overwritten.
4. **Edges:** `relationship_id = f"kbli:{code}|REQUIRES|{target}"`, `relationship_type = 'REQUIRES'`,
   `properties` = a copy of the group (for a future edge-reading router), `confidence = 1.0`,
   `source_collection = "kbli_2025_v10_pp28"`. Before insert, look for a **natural duplicate**
   `(source_entity_id, target_entity_id, relationship_type)` under any id — the schema has no unique
   constraint on it (`migration_028_knowledge_graph_schema.py:14-15,32-33`: PKs on `entity_id` /
   `relationship_id` only, non-unique indexes on source/target/type) — and treat one as
   already-present. **Placeholder edges** (the three §2.1 ids): deleted for every code the run
   touches, archived first into the KBLI node's `properties._replaced_requires_pp28v10` as `(target,
at)` — append, never overwrite. **`--placeholders-only`** performs _only_ this deletion+archive on
   any code carrying such an edge, regardless of rows, OSS status or phase — 85586 (`[]`) and the four
   non-OSS codes included — and writes nothing else (no status change, no licences).
5. **Node update** (build/relabel modes): `properties.licensing_status = "REGULATED"`,
   `properties.skala_usaha` = union over all rows, `properties.pp28_sources` = canonical
   `pp28_sources`, `properties._licensing_cure = {"run", "rows", "licences", "digest", "at"}`
   **written once on the run that cures; a no-op run never touches it**, `updated_at = now()`.
   Nothing else on the node moves.
6. **One transaction per code, all of it:** `SELECT … FOR UPDATE` on the `kbli:<code>` row, target
   inserts, archive, placeholder deletes, edge inserts, node update — commit or nothing. A failure
   after partial writes must leave the graph as it was (failure-injection test, item 9). Code-scoped
   targets mean two codes never contend on a shared node; two runs on the same code serialise on the
   row lock.
7. **Idempotence — three explicit states, decided from the graph, not from the marker.** Compute the
   derived id set `D` and its digest `d = sha256(sorted(D))`. **UNCURED**: no edge from the code to a
   `perizinan:pp28v10:{code}:*` node. **CURED**: the set of such targets equals `D`, every target's
   `properties` are byte-equal to the derived payload, the status is `REGULATED`, and
   `_licensing_cure.digest == d` → skip, write nothing (`0 of N cured | N skipped`, asyncpg command
   tags `INSERT 0 0` / `UPDATE 0`). **DRIFTED**: pp28v10 targets exist but ≠ `D`, or a payload
   differs, or the digest differs → **report, exit 4, write nothing**; drift handling (re-derivation
   after a canonical change) is Phase-2 scope and gets its own spec — there is no `--refresh-props`.
8. **Flags:** `--only <codes>` mandatory (no sweep, ever); `--census` (read-only: the §2 state table
   under the shared predicate, the 1a/1b split, the licence histogram; exits 0/4); `--apply` (dry-run
   default, printing the exact licences per code); `--phase {1a,1b}` (default `1a`;
   `1b` refuses while `PHASE_1B_ENABLED` is `False`); `--placeholders-only`; `--cure-run <label>`;
   `--dataset <path|url>`; `--replace-legacy` (`SystemExit(2)` until §6 Phase 2 lands). After apply,
   same runbook step: `kbli_inspect_cache_bust.py --only <codes> --apply`, then `inspect_kbli` on ≥ 3
   codes of the lot with a **fresh** read (the pre-cure probes of 85510 / 03231 / 65121 made this
   session are poisoned for up to 30 days).
9. **Tests (guilt AND innocence, superscar #3):** normaliser on `None`/str/list/other; `TIER` against
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

Merging `apps/backend-rag/**` is the deploy (`fly-deploy.yml`); the apply runs from Pro after the
deploy, in lots of ≤ 25 codes, `dry-run → apply → bust → probe`, each lot's `--census` output and
apply log kept under `~/logs/kbli-conformance/`.

## 6. Scope and phases

- **Phase 1a (this spec's first build), 114 codes + 17:** S1-OSS 44 (build + relabel), S2-OSS 65
  (build), S3-OSS 5 (relabel only, comparison logged); **`--placeholders-only` on all 17 §2.1 codes**
  in the first lot (phase-independent — 85586 and the four non-OSS codes included); `kg_kbli_license_fix.py
--only 91300` for the one `REGULATED` node over a canonical `[]`. Additive on the graph — nothing a
  client hears gets _less_ except the false `PENDING_REGULATION` licence, and nothing non-OSS-issued
  is relabelled.
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

- **`kg_status_function`**: rows > 0 ⇒ `REGULATED`; rows == 0 ⇒ `PENDING_REGULATION`;
  `NOT_APPLICABLE_OSS` codes excluded and counted. Manifest = all canonical codes minus the Phase 1b
  set until 1b applies; ENFORCED on the manifest only after the 1a apply log shows 0.
- **`kg_licence_presence`**: rows > 0 ⇒ ≥ 1 **admitted** permit. Same manifest rule. **Not** a count
  equality — §2 shows why.
- **`kg_placeholder_edge`**: any code with an edge to a §2.1 placeholder. DECLARED until the
  `--placeholders-only` lot is applied to the 17, then **ENFORCED catalog-wide** (no phase manifest —
  the gesture is phase-independent).
- **`kg_allowlist_contradiction`**: an allowlisted code with rows > 0 or ≥ 1 admitted permit. 0 today
  by measurement; DECLARED in the PR that lands the check, ENFORCED after its first log shows 0.

The DECLARED → ENFORCED flip of each check is its own one-line PR after the log shows the check at
0 on its manifest — never in the same PR as the cure (W116: arm the alarm against a state that was
observed, not promised).

## 8. Follow-ups this spec creates (declared, not scheduled here)

- **F1** — `kbli_documents.metadata.licensing_status`: retire the inherited `N/A`; make
  `licensing_metadata_from_canonical` in `kbli_documents_cure.py` emit the §3 function. Rides the
  next backend PR on that script (the stale `build_cured_metadata` docstring is already ledgered).
- **F2 (gates Phase 1b — behaviourally)** — router increment: additive `issuer` (from `kewenangan`),
  `procedure` (from `persyaratan`) and `verification` (§4.2) fields on `KBLILicense`, read from the
  target node; bump the cache key `v6` → `v7`; mouth renders "issued by <issuer>" and the
  self-declared/verified qualifier on the licence line. **The gate is the F2 PR itself**: it flips
  `PHASE_1B_ENABLED` in the same diff that adds (i) an HTTP contract test on `inspect_kbli` asserting
  the three fields (guilt + innocence), (ii) the `v7` key, (iii) a mouth render test for the issuer
  line. No grep, no flag.
- **F3** — the corner's PMA entry ("`inspect_kbli` reads Qdrant first") is true of the PMA tuple
  only; for licensing the KG is primary and mandatory (after the cache). Corrected in the corner in
  this PR.
- **F4** — node `skala_usaha` disagrees with the canonical union on 881/1,341 codes; Phase 1 fixes
  its share, Phase 2 the rest.
- **F5** — `kbli_requires_kind.py`: add the three §2.1 ids explicitly and the id tokens
  `pending` / `pending_regulation` to the admission markers, with guilt (the three nodes) and
  innocence (every admitted permit id on PROD, 4,699 measured) corpora — so a future placeholder
  cannot reach `licenses[]` even before its edges are removed. Router-side, own PR, cache bump.
- **F6** — adjudicate the 75 `NOT_APPLICABLE_OSS` codes per code against sector law; until then the
  list is a freeze, never enforced as truth.

## 9. Owner decisions

One, and it gates Phase 1b only: **the 61 non-OSS-issued codes** (S1 26, S2 34, S3 1 — 85510 among
them). Recommendation: keep today's values until F2 renders the issuer and procedure, then cure them
exactly like 1a — a licence a client cannot act on because it does not say who grants it is not
better than a declared gap. Alternative Zero may rule: relabel now with the generic licence name and
the `kewajiban` text (which names the ministry on some codes, not all). Phase 1a needs no decision.
The 1,505-code PMA `NOT_VERIFIED`-by-design question from 2026-09-01 is unrelated and stays open.

## 10. Proof-of-armed (replaces the ledger row's original proof)

1. `--census` on PROD lists 0 Phase-1a codes in S1, S2 and S3 (44 / 65 / 5 on 2026-09-02).
2. For each of the **17 detector codes in 1a** (the 20 S1 + 2 S3 minus 65111, 65121, 85102, 85510,
   85520), a **post-bust** `inspect_kbli` returns `licensing_status: REGULATED`; for the 15 S1 codes
   a non-empty `licenses[]` whose `type` set equals the §4 rule applied to the canonical rows, with
   `scale` = the rows' scale union; for 85694 / 90200 the legacy licence unchanged
   (03231/03232/03233 keep their legacy entries until Phase 2; the five 1b codes are judged after 1b).
3. `inspect_kbli` on **all 17** §2.1 codes — 85586 and the four non-OSS codes included — no longer
   lists a licence named `PENDING_REGULATION` (proof of the `--placeholders-only` lot).
4. The detector's four KG checks read 0 on their manifests in `~/logs/kbli-conformance/` and each
   ENFORCE flip PR is merged; a second `--apply` on any lot writes 0 rows and leaves
   `_licensing_cure` untouched.

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
gazette text and the code. **Not folded** — Agent PR Contract §8 forbids a fourth round; every item
below is OPEN and is the entry point for the session that reopens this spec. The refuter's minimal fix
is quoted so nothing has to be re-derived:

| #   | finding                                                                                                                                                                                                                                                                                | verified this session                                                                 | status                                                                                                                                                                                                                     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | the census labelled placeholders as non-admitted; the router admits them → live S1 54 / S2 99 / S3 22, and 70/99/6 holds only after the placeholder lot (unstated ordering); the intersection filter dropped 9 edges of KG-only codes (admitted 4,722 / 355 / 241 over the whole dump) | yes — arithmetic on the same dump (16 placeholder codes with rows > 0, all `PENDING`) | **open** — fix: represent placeholders as an explicit current state; make the placeholder lot + bust + fresh manifests a hard predecessor of every state-driven action; `--census` prints both states (noted inline in §2) |
| 2   | canonical `01122` (8 rows) has no KG node; the router 404s; §5.6's locked update and `kg_kbli_resync.py:229-238` have no creation path; KG-only codes are 10, not 9                                                                                                                    | yes — 1,559 − 1,558 = 1; 1,568 − 1,558 = 10                                           | **open** — fix: missing-node detector + transactional node creation path; regenerate counts/manifests from all 1,559                                                                                                       |
| 3   | S3 relabel to `REGULATED` makes the answer MORE affirmative while the rendered legacy licence ≠ the statute-derived set on 6/6 — contradicts §6's non-regression claim                                                                                                                 | yes — §5.2's own comparison table                                                     | **open** — fix: S3 stays `PENDING` until Phase 2 adjudicates; relabel-only solely on an exact legacy/derived match (today: zero codes)                                                                                     |
| 4   | `PHASE_1B_ENABLED` is weaker than §3's gate: F2 tests the issuer line but never `procedure`; the constant flips in the source PR before Fly AND Vercel are proven live                                                                                                                 | yes — F2 text                                                                         | **open** — fix: F2 renders + tests `procedure`; the constant stays `False` in the F2 PR and flips in a separate PR after prove-live on both production surfaces (or `--apply` preflights both)                             |
| 5   | detectors are one-directional (`rows == 0 ⇒ admitted == 0` unenforced — 85586, 91300 would pass a status change); allowlist status itself not asserted; the JSON's "never enforced" note contradicts §7                                                                                | yes                                                                                   | **open** — fix: both directions of the row/licence invariant; allowlist = zero rows ∧ zero admitted ∧ exact status; JSON note corrected in this PR                                                                         |
| 6   | the hashed `payload` and the stored `properties` are two objects (`+ source, verification`); "byte-equal" is not how JSONB compares                                                                                                                                                    | yes                                                                                   | **open** — fix: one exact `node_properties` object, hashed by its canonical JSON, stored unchanged, compared by decoded value or the same serialisation                                                                    |

Unverified by the refuter (declared): the cached `inspect_kbli` outputs of §1 (Pro unreachable from
its sandbox), the 13,344-edge type distribution and the 881 `skala_usaha` figure (not in the dump), and
the "two independent readers" claim for round 2 (procedural, no artefact in the files it was given —
the readers' reports live in this session's transcript only).

**Suspension (rule 8).** Same surface, three BLOCKED verdicts: the lane suspends with this record on
`main` and a PENDING-ARMS line naming the cause. The measured facts of §1–§2 and the legal basis of
§4.1 stand (each was verified independently of the design); §5–§7 are the design that must be reopened
from the six rows above.
