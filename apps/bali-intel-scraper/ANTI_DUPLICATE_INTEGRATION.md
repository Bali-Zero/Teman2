# Anti-Duplicate System - Integration Guide

## ✅ IMPLEMENTED

Il sistema anti-duplicati è **completamente implementato** in `claude_validator.py`:

- ✅ Registry file: `data/published_articles.json`
- ✅ Loading al boot: `_load_published_articles()`
- ✅ Quick check: `_quick_duplicate_check()` (60% keyword overlap)
- ✅ Claude semantic check: Riceve lista ultimi 50 articoli pubblicati
- ✅ Auto-approve override: Anche articoli con score ≥75 vengono controllati per duplicati
- ✅ Stats tracking: `duplicate_rejected` counter

## 🔧 INTEGRATION REQUIRED

### Dove integrare la registrazione

Quando un articolo viene **effettivamente pubblicato sul sito** (Sanity CMS o altro), chiamare:

```python
from claude_validator import ClaudeValidator

# Dopo successful publish
ClaudeValidator.add_published_article(
    title=article.title,
    url=published_url,  # URL finale sul sito
    category=article.final_category,
    published_at=datetime.now().isoformat()
)
```

### Punti di integrazione possibili

#### Opzione A: Backend Publish Endpoint (CONSIGLIATO)
Creare endpoint `/api/intel/staging/{item_id}/publish` che:
1. Legge articolo da staging
2. Pubblica su Sanity/website
3. Chiama `ClaudeValidator.add_published_article()`
4. Rimuove da staging

**File:** `apps/backend-rag/backend/app/routers/intel.py`

```python
@router.post("/api/intel/staging/{item_id}/publish")
async def publish_approved_article(item_id: str):
    """Publish approved article to website"""

    # 1. Load from staging
    staging_file = STAGING_DIR / f"{item_id}.json"
    with open(staging_file) as f:
        article_data = json.load(f)

    # 2. Publish to Sanity/website
    published_url = await publish_to_website(article_data)

    # 3. Register in anti-duplicate system
    ClaudeValidator.add_published_article(
        title=article_data["title"],
        url=published_url,
        category=article_data["category"],
        published_at=article_data.get("published_at")
    )

    # 4. Cleanup staging
    staging_file.unlink()

    return {"success": True, "published_url": published_url}
```

#### Opzione B: Telegram Bot dopo approvazione
Modificare `telegram_approval.py` per pubblicare automaticamente dopo voto 2/3:

```python
# In telegram.py dopo majority_vote.status == "approved"
if vote_result["status"] == "approved":
    # Publish to website
    published_url = await publish_to_website(article_data)

    # Register in anti-duplicate
    ClaudeValidator.add_published_article(
        title=article_data["title"],
        url=published_url,
        category=article_data["category"],
        published_at=datetime.now().isoformat()
    )
```

#### Opzione C: Script manuale batch publish
Per pubblicare articoli già approvati in Telegram:

```python
# scripts/publish_approved_articles.py
import asyncio
from telegram_approval import TelegramApprovalSystem
from claude_validator import ClaudeValidator

async def publish_approved():
    approval_system = TelegramApprovalSystem()
    approved = approval_system.list_approved()

    for article in approved:
        # Publish each
        url = await publish_to_website(article)

        # Register
        ClaudeValidator.add_published_article(
            title=article.title,
            url=url,
            category=article.category,
            published_at=datetime.now().isoformat()
        )

        print(f"✅ Published: {article.title}")

if __name__ == "__main__":
    asyncio.run(publish_approved())
```

## 📊 Registry File Structure

Il file `data/published_articles.json` viene auto-creato e mantenuto:

```json
{
  "last_updated": "2026-01-05T10:30:00",
  "count": 142,
  "articles": [
    {
      "title": "Indonesia Extends Digital Nomad Visa to 5 Years",
      "url": "https://balizero.com/immigration/nomad-visa-extension-2026",
      "category": "immigration",
      "published_at": "2026-01-05T09:00:00"
    }
  ]
}
```

**Rolling window**: Mantiene ultimi 500 articoli pubblicati.

## 🧪 Test del Sistema

### Test 1: Duplicate Quick Check
```python
from claude_validator import ClaudeValidator

validator = ClaudeValidator()

# Simula articolo già pubblicato
ClaudeValidator.add_published_article(
    title="Indonesia Extends Digital Nomad Visa to 5 Years",
    url="https://example.com/1",
    category="immigration"
)

# Ricarica registry
validator = ClaudeValidator()

# Testa duplicate check
result = validator._quick_duplicate_check(
    "Indonesia's Digital Nomad Visa Extended to Five Years"
)

assert result is not None, "Dovrebbe rilevare duplicato!"
print(f"✅ Quick check funziona: similar to '{result}'")
```

### Test 2: Claude Semantic Check
```python
# Articolo con leggera variazione
result = await validator.validate_article(
    title="Indonesian Government Announces 5-Year Digital Nomad Visa",
    summary="The Indonesian government has announced a new policy extending the digital nomad visa from 1 to 5 years.",
    url="https://example.com/2",
    source="Different Source",
    llama_score=85
)

assert result.is_duplicate == True
assert result.similar_to is not None
print(f"✅ Claude check funziona: identified as duplicate")
```

## 🚀 Deployment Checklist

Prima di andare in produzione:

- [ ] Creare endpoint `/api/intel/staging/{item_id}/publish` nel backend
- [ ] Testare pubblicazione + registrazione in staging
- [ ] Verificare rolling window (500 articoli max)
- [ ] Aggiungere publish button nella News Room UI
- [ ] Documentare workflow team: Approve → Publish → Auto-register

## 📝 Note Importanti

1. **La registrazione deve avvenire DOPO la pubblicazione** (usa URL finale del sito)
2. **Non registrare articoli in staging/pending** (solo quelli effettivamente pubblicati)
3. **Il sistema funziona anche senza articoli pubblicati** (lista vuota = no duplicates)
4. **Stats disponibili in** `validator.stats["duplicate_rejected"]`

## 🎯 Status Attuale

- ✅ Sistema di detection: 100% completo
- ✅ Validazione con Claude: Funzionante
- ✅ Quick check locale: Funzionante
- ⏳ Integrazione publish: **Da implementare** (vedi opzioni sopra)
- ⏳ UI publish button: **Da aggiungere** in News Room

## Contatto

Per domande sull'implementazione, vedere:
- `scripts/claude_validator.py` (linee 74-128)
- Questo documento
