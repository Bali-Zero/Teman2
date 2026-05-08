# Phase 7 — Nexus OSINT (B6)

> **Prerequisiti**: Phase 0+1 mergiate. Phase 6 (Bali Macro) preferibile per cross-pollination.
>
> **Stima**: 7-10 giorni solo-dev.
>
> **Pre-azione richiesta a Antonello**: B6.a (2 NB-INTEL distinti vs 1) + B6.b (privacy line strict/aggressive/on-demand).
>
> **CRITICAL**: questo dominio ha **red lines legali** UU PDP 27/2022. Implementazione errata = 5 anni / Rp 5B sanction. Compliance stance OBBLIGATORIA prima di codice.

---

## PROMPT (drop-in)

Continuiamo il Domain Mesh. Phase 7: implementa il dominio **Nexus OSINT (B6)** — entity tracking + people-graph autorità Indonesia.

**Prima azione**: leggi compliance. NON scrivere codice prima di:

1. `docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md` §7 B6 (compliance stance 10-point)
2. `docs/superpowers/specs/2026-05-08-domain-mesh-research/r7-osint-entity-people-2026-05-08.md` (R7 SOTA — sezioni 4 e 8 obbligatorie)
3. **§8.1 R7 UU PDP 27/2022 red lines tabella**: cosa è LEGAL vs ILLEGAL

Solo dopo, leggi: 4. `apps/mata-garuda/mata_garuda/foundations/opensanctions_id.py` (Phase 0 — già implementato!) 5. `apps/mata-garuda/mata_garuda/foundations/ner_extractor.py` (Phase 0 — cahya BERT NER bahasa) 6. MATA GARUDA Indonesia Gov Data Sources NB UUID

`superpowers:brainstorming` (focus su privacy line decision B6.b!) → `writing-plans` → `subagent-driven-development`.

### Scope CRITICAL — privacy first

**Compliance stance 10-point** (R7-validated, OBBLIGATORIO commit before any code):

1. Internal-use only dossier policy
2. Source restriction: solo public/official Indonesian (KPK/KPU/DPR/BPK/MA/Setkab) + sanctioned international (OpenSanctions free)
3. **NO data breach DB use**
4. **NO address/NIK in dossier** (UU PDP Art. 67(2), 5y / Rp 5B)
5. Hunchly chain-of-custody (opzionale, $130/yr)
6. 24-month retention max
7. Privacy notice in client engagement letter
8. **NO automated mass scraping**
9. EU clients: GDPR Art. 6(1)(b) + Art. 6(1)(f) balancing test documented
10. Bellingcat-style ethics review before external output

**Output**: `apps/mata-garuda/mata_garuda/domains/nexus_osint/compliance/compliance_stance.md` — first commit.

### Architecture 3-layer (R7 Palantir-pattern, NOT prodotto)

```
domains/nexus_osint/
├── semantic/
│   └── entity_definition.yaml  # Person, Organization, Event, Sanction
├── kinetic/
│   ├── lhkpn_scraper.py
│   ├── wikidata_sparql.py
│   ├── opensanctions_id_pull.py  # already in Phase 0
│   ├── tempo_rss_ingest.py
│   ├── ner_extractor.py  # already in Phase 0
│   └── maigret_username.py
├── dynamic/
│   ├── privacy_guardrails.rego  # UU PDP enforcement (CRITICAL)
│   ├── role_change_detection.py
│   └── publication_gate.py  # auto-redact NIK/address before any external output
└── compliance/
    └── compliance_stance.md  # 10-point policy
```

### Storage backend — Wikibase self-host (R7 recommendation)

- Self-hosted Wikibase instance su Mini-Pro2 (docker)
- Same data model as Wikidata (interoperable)
- SPARQL query interface (standard)
- JSON entity export
- Federated query Wikidata + local

**Bootstrap quick-win** (R7 §6.6 Wikidata SPARQL):

```sparql
SELECT ?person ?personLabel ?roleLabel ?orgLabel ?dob WHERE {
  ?person p:P39 ?role_statement.
  ?role_statement ps:P39 ?role.
  ?role wdt:P31* wd:Q294414.  # public office Indonesia
  ?role wdt:P17 wd:Q252.      # country: Indonesia
  OPTIONAL { ?person wdt:P569 ?dob. }
  ?role pq:P108 ?org.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
LIMIT 500
```

→ 200-500 Indonesian public officials seed entries. Effort: 4-6 hours.

### Feeders (DECISIONE B6.a, default A=2 distinti)

1. **`feeders/nb_intel_authorities.py`** (formal):
   - e-LHKPN scraper (kpk.go.id) — wealth declarations
   - DPR.go.id members API
   - KPU Daftar Caleg infopemilu.kpu.go.id
   - Setkab cabinet (setkab.go.id/profil-kabinet)
   - BKN Satu Data ASN (limited public)
   - BPK audit reports
   - Mahkamah Agung Direktori Putusan
   - **OpenSanctions Indonesia datasets** (already Phase 0!): `id_dttot`, `id_regional_2018`

2. **`feeders/nb_intel_curiosities.py`** (informal/long-form):
   - Tempo "tokoh" tag RSS
   - Kompas politicians database
   - Tirto.id deep dive
   - Project Multatuli investigations
   - Watchdoc YouTube channel monitoring (RSS via youtube-rss)
   - Mata Najwa interviews (Narasi.tv)

### NER pipeline cross-domain (R7 §5)

Phase 0 `ner_extractor` con `cahya/bert-base-indonesian-NER` già pronto.

Estrai cross-domain:

- **B5 macro press**: Person, Org da Tempo/Tirto/Multatuli articles
- **B1 setup-team regulation**: Person (regulator firmatario), Org (ministero)
- **B2 tax**: Person, Org da DJP press
- **B6 nexus**: NER è il core per entity extraction

### Stack zero-cost (R7 confirmed, $130/yr only Hunchly)

| Layer                | Tool                                           | Cost         |
| -------------------- | ---------------------------------------------- | ------------ |
| Entity ontology      | Wikibase self-host + Wikidata seed             | FREE         |
| Sanctions            | OpenSanctions API (Phase 0 done)               | FREE         |
| People-graph         | Wikidata SPARQL + LittleSis API + LHKPN scrape | FREE         |
| Investigative search | OCCRP Aleph (request access journos)           | FREE/journos |
| Username pivots      | Maigret 3000+ sites                            | FREE         |
| Email pivots         | Holehe + Mosint                                | FREE         |
| NER                  | cahya BERT (Phase 0 done)                      | FREE         |
| Visualization        | Gephi + NetworkX                               | FREE         |
| Evidence custody     | Hunchly                                        | $130/yr      |
| News surveillance    | Tempo/Tirto/Multatuli/Watchdoc RSS             | FREE         |

**Skip**: Maltego ($$$$), Sayari ($$$$$), World-Check ($$$$$+), Palantir (cost + ETHICS red flags vedi memory `palantir-anthropic-hybris`).

### Sinks (R7 §7.9)

1. **`/whois <name>` CLI** — instant card from Wikibase + recent NB-INTEL mentions
2. **Strategic intel briefing monthly** — top 5 people changes + top 3 org reshuffle
3. **Editorial fodder** — Curiosities NB → marketing brief candidates (federation con B3)
4. **Cross-domain alert** — Person change → relevant domain (DG Pajak → tax, BKPM head → setup-team)
5. **Network graph viz** — Gephi + NetworkX export
6. **NEW Client Due Diligence Hunchly workflow**:
   - Trigger: nuovo cliente high-value (quote > €10k)
   - Maigret username search → social presence map
   - OpenSanctions check → no PEP/sanction match
   - Wikidata cross-ref → no public profile flags
   - Hunchly capture all evidence pages → SHA-256 hash
   - Internal dossier → `NB-WORKBENCH-Nexus-Client-{id}`
   - Engagement letter privacy notice signed
   - Cost: $130/yr Hunchly + 30min analyst time per cliente
7. **NEW OCCRP Aleph partnership exploration**:
   - Spawn workbench, contact OCCRP ID research desk
   - Use case: due diligence cliente high-value multi-jurisdiction

### Privacy guardrails (CRITICAL)

`dynamic/publication_gate.py`:

- Auto-redact NIK pattern (`\d{16}`) prima di qualsiasi output esterno
- Auto-redact home address pattern (Jl. + numero + RT/RW)
- Block emit Telegram alert se entity ha `controversy.unverified=True`
- Manual override: `force_publish=True` requires Antonello signature in code path

### R7 red flag check (legal)

Prima di ogni feature implementata, attraversa il flow di R7 §8.4 doxing line:

| Activity                                       | Legal?                                      |
| ---------------------------------------------- | ------------------------------------------- |
| Reading e-LHKPN public data                    | LEGAL                                       |
| Querying Daftar Caleg KPU                      | LEGAL                                       |
| Compiling internal dossier from public sources | LEGAL (internal)                            |
| Publishing pejabat home address                | **ILLEGAL — UU PDP Art. 67(2), 5y / Rp 5B** |
| Publishing pejabat NIK / KTP                   | **ILLEGAL — sensitive data UU PDP Art. 4**  |
| Cross-ref data breach DB                       | **ILLEGAL — UU PDP Art. 65**                |
| OSINT for KYC due diligence (internal)         | LEGAL — lawful interest, document           |

### Cron

- `infra/scripts/nexus-osint-cron.sh`
- Schedule: 10:00 WITA daily
- Kill switch: `NEXUS_OSINT_CRON_ENABLED=false`

### Regole forti

- mata-garuda CLAUDE.md hard rules invariate
- Lazy imports
- TDD: 50+ test (incluso compliance test che assert privacy_guardrails enforce)
- Cron PATH
- Branch hijack push post commit
- **Compliance stance.md committed PRIMA di qualsiasi codice**

### External review wave (mandatory per Nexus — alta sensibilità legale)

3-LLM minimum (Codex GPT-5 + DeepSeek + NotebookLM NB-1) + **security-review skill obbligatorio**. Focus su:

- Privacy guardrails enforce realmente?
- LHKPN scraping rate-limited (no UA rotation aggressiva)?
- Hunchly integration o solo theatrical?
- UU PDP red lines respect in OGNI sink?

### Pre-azione richiesta a Antonello

**PRIMA di partire**:

1. **B6.a**: 2 NB-INTEL OSINT distinti (Authorities + Curiosities) vs 1?
   - **A** (default): 2 distinti — Authorities formal, Curiosities informal
   - B: 1 unificato — mix segnale formal vs informal

2. **B6.b**: Privacy line — quanto profondo vai?
   - A: Strict open-source only (UU PDP max compliant, profile magri)
   - B: Aggressive OSINT (LinkedIn scraping, social cross-ref) — **R7 dice ILLEGAL, NO**
   - **C** (default, R7 confirmed UU PDP-compliant): Strict + manual deep-dive on demand — caso-per-caso

3. Hunchly $130/yr — confermi acquisto?
   - Pro: chain-of-custody legalmente difendibile
   - Contro: $130/yr operational cost
   - Default consigliato: Sì (cost basso, valore reputazionale alto)

4. Wikibase self-host su Mini-Pro2 — accetti docker overhead (5-8 ore/mese maintenance)?
   - Alternativa: SQLite triple store custom (R7 DeepSeek W1 alternative)
   - Default consigliato: SQLite first, Wikibase Phase 8+ se serve federation Wikidata

5. OCCRP Aleph access request — autorizzi?
   - Solo discovery, no commitment
   - Default consigliato: Sì exploratory

Procedi SOLO quando confermato. Compliance stance file commit PRIMA di codice.
