---
date: 2026-06-06
domain: marketing
client_case: war-room-rebuild
sources:
  - intel_items id 44122b09 (PPh Final UMKM, liputan6.com, 2026-06-05) — brief povero reale
  - wr2-brief-interpreter agent + NB-4 (157 sources) — brief ricco reale
  - scripts/wr2_draft_generator.py (consumer del brief_json)
---

# War Room Step 2 — confronto AFFIANCATO: brief povero vs brief ricco (stesso topic reale)

> Decisione architetturale: che brief deve produrre lo Step 2? Prima di scegliere,
> ecco i DUE brief generati sullo STESSO articolo reale (PPh Final UMKM, liputan6, 5 giu).
> **Non astratto: dato reale, generato adesso.**

## Il topic

`Pemerintah Ubah Aturan PPh Final UMKM, PT dan CV Tak Lagi Dapat Fasilitas`
(il governo cambia il PPh Final 0,5% UMKM: PT e CV perdono la facilitazione). Fonte
liputan6.com, 2026-06-05. È uno dei candidati della shortlist Step 1, regolatorio-tax
(il caso peggiore per un brief povero: serve precisione normativa).

---

## LATO A — Brief POVERO (cosa ha OGGI lo Step 2)

**Materiale grezzo unico = il campo `summary`** (raw_payload = solo metadata staging,
ZERO enrichment, ZERO war_room_draft preesistente). Il summary è:

- ~2000 char di **estratti dell'articolo** separati da `[...]` **letterali** nel DB
- **troncato a metà parola** (`...fasilitas ters‹TRONCATO›`)
- testo **indonesiano grezzo**, zero struttura, zero analisi
- contiene il numero norma (PP 20/2026, Pasal 57) ma **annegato** nel testo

Esempio verbatim (così com'è nel DB):

> Pemerintah resmi menerbitkan PP Nomor 20 Tahun 2026 tentang Perubahan atas PP Nomor
> 55 Tahun 2022... [...] ...kini penerimanya dibatasi hanya untuk wajib pajak orang
> pribadi, perseroan perorangan... [...] ...CV, firma, PT, dan BUMDes... masih dapat
> menggunakannya hingga masa transisi berakhir. [...] ...Sebelumnya, fasilitas ters‹TRONCATO›

**Cosa NON ha**: nessun the_facts, nessun 30-second-brief, nessun bali_zero_take,
nessun next_steps, nessun FAQ, nessuna citazione normativa isolata, nessun glossario,
nessun taboo-check, nessun angolo per il pubblico PT PMA. Il draft_generator a valle
dovrebbe estrarre TUTTO da questo blocco grezzo, da solo.

---

## LATO B — Brief RICCO (brief-interpreter + NB-4 ground-truth)

Generato adesso dall'agente `wr2-brief-interpreter` con query a NotebookLM NB-4 (157 source tax). Estratto:

**15 key_facts** con provenienza normativa, es.:

- "PP 55/2022 ha sostituito PP 23/2018... implementando UU HPP 7/2021 Art. 4, 17, 32C — NB-4 source 848862af (testo verbatim)"
- "Durata: 7 anni orang pribadi / 4 anni CV-firma-koperasi-BUMDes / 3 anni PT — NB-4 848862af"
- "PT PMA strutturalmente esclusi anche oggi: capitale minimo Rp 10 mld incompatibile con soglia omzet Rp 4,8 mld — NB-4 9e49136b"
- "CoreTax (PMK 81/2024) bloccherà automaticamente e-Billing 0,5% per PT/CV post-revisione, triggerando SP2DK — NB-4 c9203fa0"

**11 key_numbers**: 0,5% / Rp 4,8 mld / Rp 500 mln esente / 7-4-3 anni / 22% / 11% Pasal 31E / 2029 / 24 mesi bunga / Rp 10 mld PT PMA.

**7 citazioni regolatorie verbatim**: PP 23/2018, PP 55/2022, UU HPP 7/2021 (Pasal 4(2)e, 17(2e), 32C), UU KUP Pasal 28+13, Pasal 17(1)b, Pasal 31E, PMK 81/2024 Pasal 448.

**Quote dirette autorità** (verbatim, citabili senza parafrasi):

- Airlangga Hartarto: "...PPh finalnya 0,5% dilanjutkan sampai 2029. Jadi, tidak diperpanjang setahun-setahun, tetapi diberikan kepastian sampai 2029" (DDTCNews)
- Bimo Wijayanto (DJP): rimozione facility corporate mira al "firm splitting / revenue bunching"

**23 termini lexicon bilingue** (PPh Final, omzet, peredaran bruto, pembukuan, SKPKB, SP2DK… con assist EN; PT PMA/CV/NPWP/Coretax always-untranslated).

**7 taboo-check TOPIC-SPECIFICI** (oltre alla ban-list standard):

- "save money on taxes" / "loophole" / "avoid taxes" (la riforma CHIUDE un loophole — usarlo fa sembrare BZ complice del firm-splitting)
- "PT PMA can use UMKM regime" = MISINFORMAZIONE al pubblico-target BZ
- framing "signed/effective" — (vedi sotto: qui il brief ricco è meno aggiornato del povero!)

**hook_angle**, **archetype** (regulatory-explainer), **tone_register** (analitico/militante).

---

## LATO C — La cosa che NESSUNO dei due ha da solo (importante per la decisione)

⚠️ **Discrepanza fattuale reale tra i due brief**:

- Il **povero** (articolo Liputan6, 5 giu) dice: norma **GIÀ emanata = PP 20/2026, Pasal 57**, con masa transisi.
- Il **ricco** (NB-4) dice: revisione **"in attesa di firma di Prabowo, nessun numero PP"** — perché le source NB-4 sono di nov 2025/set 2025, **precedenti** all'emanazione.

→ **Il brief povero (news fresca) aveva il numero norma definitivo (PP 20/2026) che il brief ricco (NB curato) non aveva ancora.** Il ricco ha la profondità normativa (PP 55/2022 verbatim, UU HPP, sanzioni); il povero ha l'aggiornamento (PP 20/2026 emanata). **Il brief ideale fonde i due: freschezza-news + ground-truth-NB.**

---

## Verdetto secco (per la decisione)

| Dimensione                               | Povero (summary)                       | Ricco (NB-4)                                  |
| ---------------------------------------- | -------------------------------------- | --------------------------------------------- |
| Profondità normativa                     | quasi zero (numero annegato nel testo) | altissima (7 citazioni verbatim, UU+PP+PMK)   |
| Numeri precisi                           | sparsi nel testo                       | 11 isolati e verificati                       |
| Quote autorità citabili                  | no                                     | sì (verbatim)                                 |
| Taboo/rischio-legale                     | nessun controllo                       | 7 taboo topic-specifici (anti-misinfo PT PMA) |
| Lexicon bilingue                         | no                                     | 23 termini                                    |
| **Freschezza (numero norma definitivo)** | **sì (PP 20/2026)**                    | **no (source pre-emanazione)**                |
| Costo                                    | $0 (già nel DB)                        | 1 invocazione agente + query NB (~$0, MAX)    |
| Pronto per il carosello?                 | il draft_generator deve estrarre tutto | quasi pronto allo storyboard                  |

**Implicazione per lo Step 2**: il brief ricco è **incomparabilmente superiore** per un carosello
regolatorio (è la differenza tra "ecco il testo grezzo, arrangiati" e "ecco i fatti citati,
i numeri, le quote, cosa NON dire"). MA da solo rischia di essere **stale** sui fatti
freschissimi. La fusione (news fresca → grounding NB verbatim) è il brief vero.

> **3 opzioni per lo Step 2** (la decisione è di Antonello):
>
> - **(B-ponte)** Step 2 invoca brief-interpreter + PERSISTE lo schema ricco in brief_json. Estende wr2_draft_generator a leggere i campi nuovi. Brief fortissimo, più lavoro.
> - **(B-enrichment)** Step 2 popola la forma a 12 chiavi esistente (enrichment via LLM). Zero modifiche a valle, carosello subito, ma meno ricco.
> - **(B-fusione)** Step 2 = news-item (fresco) + brief-interpreter (grounding NB) fusi in un brief_json esteso. Il migliore in assoluto; il più ambizioso. Risolve anche la discrepanza PP 20/2026 vs pre-emanazione.
