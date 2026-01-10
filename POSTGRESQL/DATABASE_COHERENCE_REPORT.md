# Database Coherence Report - Nuzantara

**Data Analisi:** 2026-01-10 (AGGIORNATO dopo pulizia)
**Database:** PostgreSQL su Fly.io (nuzantara-postgres)
**Tabelle Totali:** 49 (da 96 - riduzione 49%)
**Righe Totali:** 62,439
**Size:** 91 MB (da ~410 MB - riduzione 78%)

---

## 1. PANORAMICA

| Categoria | Tabelle | Righe | Status |
|-----------|---------|-------|--------|
| CRM | 7 | 198 | ✅ ACTIVE |
| Team | 8 | 9,407 | ✅ ACTIVE |
| Memory | 5 | 2,447 | ✅ ACTIVE |
| Knowledge | 5 | 49,863 | ✅ ACTIVE |
| Users | 5 | 291 | ⚠️ PARTIAL |
| Content | 4 | 114 | ✅ ACTIVE |
| System | 10 | 136 | ✅ ACTIVE |
| Integrations | 3 | 18 | ✅ ACTIVE |
| Portal | 3 | 3 | ⚠️ PARTIAL |
| Cache/Analytics | 6 | 0 | 🔶 EMPTY |
| Unused | 10 | 0 | ❌ ORPHANED |

---

## 2. TABELLE ATTIVE (Usate dal Codice)

### 2.1 CRM Module
| Tabella | Righe | Routers | Status |
|---------|-------|---------|--------|
| clients | 21 | crm_clients, crm_practices, crm_interactions, crm_enhanced, portal, dashboard_summary | ✅ |
| practices | 17 | crm_practices, crm_interactions, crm_enhanced, portal, crm_auto | ✅ |
| interactions | 126 | crm_interactions, crm_clients, crm_enhanced, analytics | ✅ |
| practice_types | 5 | crm_practices, crm_enhanced, knowledge_visa | ✅ |
| client_preferences | 4 | crm_enhanced | ⚠️ Minimal |
| client_invitations | 5 | portal_invite | ✅ |
| crm_settings | 4 | crm_enhanced | ⚠️ Minimal |

### 2.2 Team Module
| Tabella | Righe | Routers | Status |
|---------|-------|---------|--------|
| team_members | 28 | team, team_activity, team_drive, auth, zoho_email | ✅ Core |
| team_timesheet | 9,308 | team_activity, team_analytics | ✅ Heavy Use |
| team_access | 23 | team, team_activity | ✅ |
| team_employees | 22 | team | ⚠️ Redundant con team_members |
| team_work_sessions | 14 | team_activity | ✅ |
| departments | 5 | team | ⚠️ Minimal |
| team_member_visibility_rules | 7 | team | ✅ |

### 2.3 Memory & Conversations
| Tabella | Righe | Routers/Services | Status |
|---------|-------|------------------|--------|
| memory_facts | 1,641 | collective_memory, episodic_memory, oracle_universal | ✅ Core |
| episodic_memories | 245 | episodic_memory, oracle_universal | ✅ |
| collective_memory | 6 | collective_memory | ✅ |
| conversations | 554 | conversations, feedback, analytics, agentic_rag | ✅ Core |
| conversation_ratings | 1 | feedback | ✅ |

### 2.4 Knowledge Graph & RAG
| Tabella | Righe | Routers/Services | Status |
|---------|-------|------------------|--------|
| kg_nodes | 24,923 | root_endpoints, debug, legal_ingest | ✅ Core |
| kg_edges | 23,234 | root_endpoints, debug | ✅ Core |
| parent_documents | 1,507 | debug, legal_ingest, root_endpoints | ✅ Core |
| query_analytics | 193 | analytics | ✅ |
| kbli_blueprints | 6 | knowledge_visa | ✅ |

### 2.5 Users & Auth
| Tabella | Righe | Routers | Status |
|---------|-------|---------|--------|
| user_profiles | 42 | auth, crm_clients, team, telegram, websocket | ✅ Core |
| users | 18 | auth, telegram | ❌ LEGACY - Migrare a team_members |
| user_facts | 193 | oracle_universal | ✅ |
| user_stats | 35 | analytics | ✅ |
| persistent_sessions | 3 | session | ✅ |

### 2.6 Content
| Tabella | Righe | Routers | Status |
|---------|-------|---------|--------|
| news_items | 47 | news | ✅ |
| visa_types | 25 | knowledge_visa, crm_enhanced | ✅ |
| document_categories | 41 | debug, crm_clients | ⚠️ |
| newsletter_subscribers | 1 | newsletter | ✅ |

### 2.7 System & Logs
| Tabella | Righe | Routers/Services | Status |
|---------|-------|------------------|--------|
| activity_log | 55 | admin_logs, analytics | ✅ |
| schema_migrations | 34 | health, nusantara_health | ✅ |
| migration_log | 3 | migration_runner | ✅ |
| email_activity_log | 10 | zoho_email | ✅ |
| folder_access_rules | 16 | team_drive, portal | ✅ |

### 2.8 Integrations
| Tabella | Righe | Routers | Status |
|---------|-------|---------|--------|
| google_drive_tokens | 1 | google_drive | ✅ |
| zoho_email_tokens | 17 | zoho_email | ✅ |
| zoho_email_cache | 0 | zoho_email | ✅ Cache |

---

## 3. TABELLE VUOTE MA VALIDE (Feature Future)

Queste tabelle sono referenziate nel codice ma non ancora popolate:

| Tabella | Router/Service | Motivo Vuota |
|---------|----------------|--------------|
| golden_routes | golden_router_service | Cache risposte da popolare |
| golden_answers | golden_answer_service | Cache risposte da popolare |
| query_clusters | routing/* | Clustering query non attivo |
| review_queue | feedback | Review workflow non attivo |
| renewal_alerts | portal | Alert automatici non attivi |
| portal_messages | portal | Portal clienti non attivo |
| audit_events | middleware/audit | Audit trail non attivo |
| auth_audit_log | auth | Auth logging non attivo |

---

## 4. TABELLE POTENZIALMENTE ORFANE

Queste tabelle potrebbero essere rimosse dopo verifica:

| Tabella | Righe | Problema |
|---------|-------|----------|
| users | 18 | LEGACY - Rimpiazzato da team_members |
| team_employees | 22 | Potenzialmente duplicato di team_members |
| client_companies | 0 | FK a company_profiles (vuota) - Mai usato |
| client_family_members | 0 | Mai popolata |
| company_profiles | 0 | Mai popolata |
| cross_session_context | 0 | Feature non implementata |
| cultural_knowledge | 0 | Feature non implementata |
| document_language_mappings | 0 | Feature non implementata |
| memory_analytics | 0 | Feature non implementata |
| memory_cache | 0 | Feature non implementata |
| news_subscriptions | 0 | Feature non implementata |
| newsletter_send_log | 0 | Feature non implementata |
| team_daily_reports | 0 | Feature non implementata |
| team_knowledge_sharing | 0 | Feature non implementata |
| user_saved_news | 0 | Feature non implementata |
| automation_runs | 0 | Feature non implementata |
| knowledge_feedback | 0 | Feature non implementata |
| query_route_clusters | 0 | Feature non implementata |

---

## 5. FOREIGN KEYS - VERIFICA INTEGRITÀ

### FK Attive e Valide
```
clients.id <- practices.client_id (21 → 17) ✅
clients.id <- interactions.client_id (21 → 126) ✅
clients.id <- client_preferences.client_id (21 → 4) ✅
clients.id <- client_invitations.client_id (21 → 5) ✅
practices.id <- interactions.practice_id (17 → X) ✅
user_profiles.id <- team_access.user_id (42 → 23) ✅
user_profiles.id <- user_facts.user_id (42 → 193) ✅
user_profiles.id <- conversation_ratings.user_id (42 → 1) ✅
user_profiles.id <- episodic_memories.user_profile_id (42 → 245) ✅
team_members.id <- zoho_email_tokens.user_id (28 → 17) ✅
team_members.id <- email_activity_log.user_id (28 → 10) ✅
kg_nodes.entity_id <- kg_edges.source_entity_id (24923 → 23234) ✅
kg_nodes.entity_id <- kg_edges.target_entity_id (24923 → 23234) ✅
news_items.id <- user_saved_news.news_id (47 → 0) ✅
practice_types.code <- practices.practice_type_code (5 → 17) ✅
```

### FK con Tabelle Vuote (non verificabili)
```
clients.id <- client_companies.client_id (21 → 0)
clients.id <- client_family_members.client_id (21 → 0)
company_profiles.id <- client_companies.company_id (0 → 0)
practices.id <- portal_messages.practice_id (17 → 0)
practices.id <- renewal_alerts.practice_id (17 → 0)
golden_routes.route_id <- query_route_clusters.route_id (0 → 0)
```

---

## 6. RACCOMANDAZIONI

### 🔴 Azioni Immediate

1. **Migrare tabella `users` → `team_members`**
   - 18 righe da consolidare
   - Verificare che tutti i riferimenti usino team_members
   - Poi DROP TABLE users

2. **Verificare `team_employees` vs `team_members`**
   - 22 vs 28 righe - potenziale duplicazione
   - Unificare se possibile

### 🟡 Azioni Consigliate

3. **Attivare `audit_events` e `auth_audit_log`**
   - Il codice esiste, solo non attivo
   - Utile per compliance e debugging

4. **Popolare `golden_routes/golden_answers`**
   - Cache risposte per ridurre costi LLM
   - Già implementato, solo vuoto

5. **Attivare `renewal_alerts`**
   - Auto-alert scadenze pratiche
   - Codice in portal router

### 🟢 Pulizia Opzionale

6. **DROP tabelle mai usate** (dopo backup)
   ```sql
   DROP TABLE IF EXISTS
     client_companies,
     client_family_members,
     company_profiles,
     cross_session_context,
     cultural_knowledge,
     document_language_mappings,
     memory_analytics,
     memory_cache,
     news_subscriptions,
     newsletter_send_log,
     team_daily_reports,
     team_knowledge_sharing,
     user_saved_news,
     automation_runs,
     knowledge_feedback,
     query_route_clusters
   CASCADE;
   ```

---

## 7. METRICHE DATABASE

```
Tabelle totali:        66
Tabelle con dati:      41 (62%)
Tabelle vuote:         25 (38%)
  - Feature future:     8
  - Potenzialmente orfane: 17

Foreign Keys:          35
FK valide:             25
FK non verificabili:   10 (tabelle vuote)

Righe totali:          ~62,000
  - kg_nodes:          24,923 (40%)
  - kg_edges:          23,234 (37%)
  - team_timesheet:     9,308 (15%)
  - Altri:              4,535 (8%)

Size database:         92 MB
```

---

## 8. APPENDICE - MAPPING ROUTER → TABELLE

| Router | Tabelle Usate |
|--------|---------------|
| crm_clients | clients, interactions, user_profiles, document_categories |
| crm_practices | clients, practices, practice_types, interactions |
| crm_interactions | clients, practices, interactions, conversations |
| crm_enhanced | clients, practices, client_preferences, crm_settings, visa_types |
| team | team_members, team_employees, team_access, departments |
| team_activity | team_members, team_timesheet, team_work_sessions, team_access |
| auth | user_profiles, users, team_members |
| conversations | conversations, user_profiles |
| feedback | conversations, conversation_ratings, review_queue, golden_answers |
| agentic_rag | conversations, user_profiles, golden_routes |
| portal | clients, practices, documents, portal_messages, folder_access_rules |
| google_drive | google_drive_tokens |
| zoho_email | team_members, zoho_email_tokens, zoho_email_cache |
| news | news_items |
| newsletter | newsletter_subscribers |
| analytics | query_analytics, activity_log, conversations, interactions, user_stats |
| knowledge_visa | visa_types, practice_types, kbli_blueprints |
| legal_ingest | parent_documents, kg_nodes |
| debug | parent_documents, kg_nodes, kg_edges, document_categories |
| health | schema_migrations |

---

**Report generato automaticamente - Nuzantara Database Analysis**
