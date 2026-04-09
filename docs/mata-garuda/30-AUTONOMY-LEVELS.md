# Mata Garuda — Livelli di Autonomia

> Data: 2026-04-08 | Sessione: brainstorming iniziale

## Filosofia

Mata Garuda non e' un tool che esegue. E' un **organismo** che pensa, decide, si espande.
Ma le decisioni critiche restano a Zero.

## 4 Livelli

### L1: Operativo — Autonomo Completo
Il sistema fa senza chiedere. Zero riceve solo il risultato.

| Azione | Esempio |
|--------|---------|
| Scraping | Raccoglie da 609+ fonti ogni giorno |
| Classification | Classifica articoli per topic/priority |
| Scoring | Applica quality gate a tutti gli articoli |
| NER | Estrae entita da ogni articolo |
| Embedding | Vettorizza e indicizza in Qdrant |
| Daily Briefing | Genera e invia briefing alle 07:00 |
| Regulation Alert | Detecta cambio e invia alert immediato |
| KB Update | Aggiorna Qdrant/KG con nuovi fatti verificati (T1) |
| Blog publish | Pubblica articoli con score > 0.7 da fonte T1 |

### L2: Tattico — Autonomo con Report
Il sistema decide e agisce, poi informa Zero nel report settimanale.

| Azione | Esempio |
|--------|---------|
| Source management | Disattiva fonte morta (404 per 7gg), trova sostituto via Exa |
| NLM expansion | Crea nuovo notebook domain quando topic supera soglia volume |
| Deep Research | Lancia NLM research su tema emergente |
| Source discovery | Aggiunge nuova fonte trovata automaticamente |
| War Room topics | Seleziona topic per carousel dalla briefing |
| TG Channel posts | Pubblica su TG channel BZ se score > 0.8 |
| X thread draft | Prepara thread, pubblica se regulation alert |

### L3: Strategico — Proposta + Attesa Approvazione
Il sistema analizza, propone, ma NON agisce finche Zero non approva.

| Azione | Esempio |
|--------|---------|
| Nuovo canale | "Propongo di attivare LinkedIn posting settimanale" |
| Content pivot | "Il topic digital-nomad ha 3x il volume di property, suggerisco riallocazione" |
| KB gap | "Ho identificato 15 domande frequenti senza risposta nel KB" |
| WhatsApp broadcast | Ogni broadcast a clienti richiede approvazione |
| Newsletter first month | Primi 4 invii richiedono review |
| Budget change | "Serve Tavily paid tier per coverage" |

### L4: Critico — MAI Autonomo
Il sistema non tocca queste aree senza ordine diretto di Zero.

| Azione | Perche mai autonomo |
|--------|---------------------|
| Architettura | Cambiamenti strutturali al sistema |
| Costi | Nuovi abbonamenti o API a pagamento |
| OSINT decisions | Nuovi target, nuove tecniche collection |
| Client-facing changes | Modifiche a cosa vedono i clienti |
| Deploy | Push to production su Fly.io/Vercel |
| Data deletion | Rimozione fonti, articoli, entita |
| Security | Cambiamenti a firewall, accessi, chiavi |

## Meccanismo di Escalation

```python
class MataGarudaBrain:
    async def make_decision(self, decision: Decision):
        if decision.level == "L1":
            await self.execute(decision)
            await self.log_to_mos(decision)
        
        elif decision.level == "L2":
            await self.execute(decision)
            await self.log_to_mos(decision)
            self.weekly_report.append(decision)
        
        elif decision.level == "L3":
            proposal = await self.draft_proposal(decision)
            await self.send_to_zero(proposal)  # TG privato
            # Attende risposta. NON esegue.
        
        elif decision.level == "L4":
            # MAI arriva qui automaticamente.
            # Solo Zero puo iniziare azioni L4.
            pass
```

## Decision Log

Ogni decisione (L1-L3) viene salvata in MOS:

```bash
mem save decision "Mata Garuda L2: disattivata fonte bali-expat-blog.com (404 da 7gg)" 7
mem save decision "Mata Garuda L2: creato NB-INTEL-DigitalNomad (volume > soglia)" 8
mem save decision "Mata Garuda L3: proposto LinkedIn posting - attesa approvazione" 6
```

## Weekly Autonomy Report (Domenica)

```markdown
# Mata Garuda — Autonomy Report W15 2026

## Decisioni L1 (automatiche)
- 847 articoli processati, 312 pubblicati
- 23 KB updates
- 7 regulation alerts inviati
- 5 briefing giornalieri generati

## Decisioni L2 (autonome, reportate)
- Disattivata fonte: indonesiaexpat.id/old-rss (404 da 10gg)
- Aggiunta fonte: regulasiindonesia.com (trovata via Exa, T2)
- Deep Research lanciato: "Indonesia golden visa 2026 requirements update"
- NB-INTEL-Immigration: aggiunte 34 fonti, rimosse 12 obsolete

## Proposte L3 (in attesa approvazione)
- [ ] LinkedIn posting settimanale (analisi costi: $0, solo tempo)
- [ ] Upgrade Tavily a paid tier ($30/mo) per +9000 ricerche

## Metriche
- Source health: 97.2% (598/615 fonti attive)
- Briefing quality: rating medio 4.2/5 (feedback Zero)
- Alert precision: 89% (8/9 alert confermati rilevanti)
```

## [OPEN] Da approfondire

- Feedback loop: come Zero valuta la qualita dei briefing? Thumbs up/down su TG?
- Learning: come il sistema impara dalle decisioni L3 approvate/rifiutate?
- Guardrails: cosa succede se il sistema fa un errore L2? Rollback automatico?
- Multi-agent: ogni livello ha un agent separato o e' un unico brain?
