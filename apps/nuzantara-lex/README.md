# NUZANTARA-LEX — Phase 0 spike

> Second body of the organism. "Avvocato Totale" — the Indonesian labor-law
> pilot. Ratified by Zero 2026-07-19. This README is the founding doctrine
> for the app; treat it as load-bearing, not decoration.

## One brain, two bodies

Zantara's **brain** — the method, the reasoning engine, the RAG/agentic
machinery — is shared. It lives in this monorepo and both bodies draw on
the same craft.

The **bodies never share data**:

- **Bali Zero** — the existing body, serving expats: immigration, company
  setup, tax, property. Runs on Fly.io, OpenAI embeddings, cloud.
- **Nuzantara** — this new body, serving Indonesians. Pilot domain:
  **ketenagakerjaan** (labor law). Runs **offline-first**: local machines
  only, no Fly, no cloud inference, no shared database with Bali Zero.

Same engine, two disjoint bodies. A Bali Zero client's data must never
reach Nuzantara's corpus or vice versa — this is a hard boundary, not a
convenience default, and it applies from Phase 0 onward (there is no
"we'll separate it later" — nothing here writes to or reads from any
Bali Zero client-data surface).

## Phase-0 scope

This spike proves exactly one thing: **can we reliably fetch and verify
the source-of-truth text of a norm from an official gazette portal,
without trusting anything but the document's own content?** Everything
else (parsing, storage, retrieval, chat) is deliberately out of scope
here.

- **Domain**: ketenagakerjaan (labor law) only — 15 core norms (see
  `data_sources/ketenagakerjaan_seed.json`).
- **Offline-first**: no Fly.io, no cloud inference. The only network
  calls in this spike are the fetch step itself (public gazette PDFs).
- **Embedding model (planned, NOT wired in Phase 0)**: local **bge-m3**.
  This is explicitly **not** the Bali Zero frozen embedding
  (`text-embedding-3-small`, 1536-dim, OpenAI, 93k vectors) — that
  model is frozen for Bali Zero's own index and is irrelevant to
  Nuzantara. Phase 0 does not embed or index anything; it only fetches
  and verifies source PDFs, so this is a forward note, not a current
  dependency.

## Layer map (L0–L2 for this spike)

```
L0  sources     data_sources/ketenagakerjaan_seed.json
                the curated, human-authored list of in-scope norms
                (citation, title, tipo, nomor, anno) — starts "unverified"

L1  fetch+verify  scripts/fetch_norms.py
                for each unverified entry: search peraturan.bpk.go.id,
                resolve the Details page, resolve the Download PDF link,
                fetch the PDF with a browser-standard UA, then verify the
                regulation's IDENTITY by reading page 1 of the PDF itself
                — never by trusting the filename or URL slug

L2  manifest    the seed JSON, in place, once fetch_norms.py has run
                verified entries now carry pdf_url + sha256 + verified_at
                + verify_note — tamper-evident provenance without
                shipping a single PDF byte into git
```

**Next iteration** (explicitly NOT built here):

- **Parser** — PDF → structured pasal/ayat (article/clause) text. Needed
  before any retrieval is possible.
- **Bitemporal norm-store** — a store that tracks both *validity time*
  (when a norm was legally in force) and *system time* (when we ingested
  it), because Indonesian labor law is heavily amended by cross-reference
  (e.g. UU 6/2023 ratifies the Cipta Kerja omnibus changes that touch
  UU 13/2003 and PP 36/2021 without republishing them wholesale) — the
  same question can have a different correct answer depending on the
  date in question, and a naive single-snapshot store gets this wrong
  silently.

Neither exists yet. Phase 0 stops at a verified manifest on purpose —
building a parser or store on top of an unverified corpus would just
move the "did we get the real UU 13/2003" risk one layer downstream
where it's harder to see.

## Hard rules

1. **No corpus in git.** Downloaded PDFs live under
   `data/nuzantara-lex/raw/` (repo root, sibling to `apps/`), which is
   gitignored. The only thing committed is the manifest
   (`data_sources/ketenagakerjaan_seed.json`) with sha256 provenance —
   anyone can re-fetch and re-verify the corpus from the manifest, but
   the bytes themselves never enter version control.
2. **Content-verified only.** An entry is marked `"status": "verified"`
   only after `fetch_norms.py` has actually opened the downloaded PDF
   and confirmed the regulation number + year appear on page 1 (e.g.
   `"NOMOR 13 TAHUN 2003"`). A matching filename, URL slug, or search
   result title is never sufficient by itself — those are exactly the
   fields a portal (or a bad actor) could get wrong or mismatch without
   it being obvious. If the content check fails, the entry stays
   `"unverified"` with `verify_note` recording why, and it is never
   silently promoted.
3. **UU Advokat boundary.** NUZANTARA-LEX is a legal-**information**
   system: it surfaces sourced, verbatim regulatory text and (in later
   phases) its structure. It is never a legal-**services** provider —
   it must not draft legal opinions, represent a party, or perform any
   act reserved to a licensed advokat under UU 18/2003 tentang Advokat.
   This boundary is declared at Phase 0 so every later phase (parser,
   chat, drafting assistance) is designed against it from the start,
   not retrofitted after the fact.

## Layout

```
apps/nuzantara-lex/
  README.md                                   this file
  data_sources/ketenagakerjaan_seed.json       L0 seed list -> L2 manifest (in place)
  scripts/fetch_norms.py                       L1 fetch + content-verify

data/nuzantara-lex/raw/                        gitignored PDF cache (repo root)
```
