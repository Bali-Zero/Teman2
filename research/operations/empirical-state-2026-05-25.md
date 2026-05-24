# Bali Zero WA Corpus — Empirical System State 2026-05-25

> Generated for tri-LLM panel context enrichment.
> All numbers verified via direct postgres query (nuzantara_readonly role).

## Tables: rows + freshness

| Table | Rows | Oldest | Newest |
|---|---:|---|---|
| ERROR:  relation "kg_entities" does not exist |  |  |  |
| RIGA 10: ... SELECT 'kg_entities | ' |  | COUNT(*) |
|                                                               ^ |  |  |  |

## Identity resolution: current state

 total_msgs | client_id_set | pct_matched | uniq_phones | crm_name_set | lid_pending 
------------+---------------+-------------+-------------+--------------+-------------
      16655 |           331 |         2.0 |          61 |          419 |         549
(1 riga)


## Language distribution (heuristic by first 200 chars)

       lang       | msgs  
------------------+-------
 unknown_other    | 24795
 russian_cyrillic |    13
(2 righe)


## Senders ranking — chi parla quanto

  sender_display_name  | msgs 
-----------------------+------
 Sahira BZ             | 6574
 ~ Amanda Bali Zero    | 5023
 Ari Bali Zero         | 4572
 Antonello ~ Bali Zero | 3078
 Aditya Morpheus       | 2638
 Krisna - BZ           | 1127
 Suryadi BZ            | 1021
 Asya BZ               |  923
 Surya Baru BZ         |  778
 ~ Adi Bayusantero     |  561
 mba din               |  163
 ~ amandaa             |   78
 Damar Bali Zero       |   70
 ~ Ari Firda           |   43
 Sahira Cahyani        |   30
 ~ Marta               |   27
 Catia Sabatini D12    |   23
 Makar                 |   10
 ~ Surya               |    8
 ~ Ruslana             |    8
(20 righe)


## KG state — quanto sono popolati entities/relations


## Practices vs WhatsApp coverage gap

 practices_total | practices_with_wa_msgs | pct_practices_linked 
-----------------+------------------------+----------------------
             425 |                      3 |                  0.7
(1 riga)


## KG state (postgres kg_nodes/kg_edges + sqlite Mata Garuda)

### Postgres kg_nodes

### Postgres kg_edges

### Postgres crm_kg (CRM-specific subgraph)
     tbl      | count 
--------------+-------
 crm_kg_nodes |   852
 crm_kg_edges |   711
(2 righe)


### SQLite Mata Garuda knowledge.db
genome                 genome_fts_docsize     knowledge_fts_config 
genome_fts             genome_fts_idx         knowledge_fts_data   
genome_fts_config      knowledge              knowledge_fts_docsize
genome_fts_data        knowledge_fts          knowledge_fts_idx    
---
knowledge
knowledge_fts
knowledge_fts_data
knowledge_fts_idx
knowledge_fts_docsize
knowledge_fts_config
knowledge_ai
knowledge_ad

### Postgres kg_nodes — entity_type distribution
     entity_type      | count 
----------------------+-------
 dokumen              | 42245
 kbli                 | 13418
 pasal                | 10162
 izin_usaha           |  9462
 biaya                |  9180
 undang_undang        |  3698
 jangka_waktu         |  3653
 peraturan_pemerintah |  2843
 perizinan            |  2789
 permen               |  1930
 sanksi               |  1508
 pt_pma               |  1421
 perda                |  1323
 pt_pmdn              |  1269
 perpres              |   673
 proses               |   589
 lembaga              |   575
 vitas                |   413
 kitas                |   403
 ppn                  |   274
(20 righe)


### Postgres kg_edges — relationship_type distribution
 relationship_type | count 
-------------------+-------
 REQUIRES          | 66022
 APPLIES_TO        | 39653
 REFERENCES        | 32297
 PART_OF           | 31671
 HAS_DURATION      | 10186
 PENALTY_FOR       |  8465
 REQUIRED_FOR      |  8008
 ISSUED_BY         |  6749
 RELATED_TO        |  6423
 ENABLES           |  5898
 BELONGS_TO        |  4894
 AUTHORIZES        |  4500
 DURATION_OF       |  4486
 HAS_FEE           |  4005
 SIMILAR_TO        |  3000
(15 righe)


### Postgres crm_kg specific (downstream of CRM)
 entity_type  | count 
--------------+-------
 crm_document |   418
 crm_client   |   325
 crm_person   |   109
(3 righe)

 relationship_type | count 
-------------------+-------
 BELONGS_TO        |   418
 CONTEMPORANEOUS   |   176
 DESCRIBES         |   117
(3 righe)


### kg_entity_mentions (entity ↔ source location)
mention_id, entity_id, collection_name, point_id, mention_text, confidence, match_type, created_at

