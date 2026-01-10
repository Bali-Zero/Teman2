# Database PostgreSQL Export

**Ultimo aggiornamento:** 2026-01-10 14:20:13

## File Excel

| File | Contenuto |
|------|-----------|
| 01_CRM.xlsx | Clienti, Pratiche, Interazioni |
| 02_TEAM.xlsx | Team members, Timesheet, Accessi |
| 03_MEMORY.xlsx | Memory facts, Conversazioni, Episodi |
| 04_KNOWLEDGE.xlsx | Documenti, Knowledge Graph, Analytics |
| 05_USERS.xlsx | Profili utente, Facts, Stats |
| 06_CONTENT.xlsx | News, Visa types, Categorie |
| 07_SYSTEM.xlsx | Activity log, Migrazioni |

## Aggiornamento

Per aggiornare i dati, esegui:

```bash
cd POSTGRESQL
python3 update_excel.py
```

## Note

- Tabelle grandi (embeddings, kg_nodes) sono limitate a 1000 righe
- Colonne pesanti (full_text, embedding) sono escluse
- Timestamp in formato ISO 8601
