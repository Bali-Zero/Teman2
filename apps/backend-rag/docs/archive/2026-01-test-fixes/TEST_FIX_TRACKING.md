# Test Fix Tracking

**Data Inizio:** 2026-01-16  
**Obiettivo:** < 5% test falliti

---

## 📊 STATO ATTUALE

- **Test Totali:** ~6,350
- **Test Falliti:** 300 (~4.7%)
- **Obiettivo:** < 318 test falliti (< 5%)

---

## ✅ TEST FIXATI

### FASE 1: Pulizia

#### Test Obsoleti Identificati

- [ ] `tests/unit/core/plugins/test_init_exports.py` - Verificare se modulo esiste ancora
- [ ] `tests/unit/llm/test_zantara_ai_client_coverage.py` - Verificare se modulo esiste ancora
- [ ] Altri da identificare...

#### Test con API Cambiate

- [ ] Da identificare...

#### Test con Bug Evidenti

- [ ] Da identificare...

---

## 🔄 IN PROGRESS

- [ ] Analisi test obsoleti
- [ ] Identificazione test con API cambiate
- [ ] Fix test critici

---

## 📝 NOTE

- Usare `@pytest.mark.skip(reason="...")` invece di rimuovere test
- Documentare ogni fix con data e motivo
- Creare issue/ticket per bug reali identificati

---

## 🎯 PROSSIMI PASSI

1. Verificare quali test sono realmente obsoleti
2. Iniziare fix test critici (LLM Gateway, CRM Router)
3. Aggiornare test con API cambiate
