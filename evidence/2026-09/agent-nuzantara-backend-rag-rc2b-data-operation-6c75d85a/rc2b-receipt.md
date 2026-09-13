# RC2b data-operation receipt — 2026-09-11

- **Operation:** RC2b — data half of rulings 2 and 3 (README §0), prod Qdrant via the nuzantara-rag container
- **Authority:** RC-PART1 (staff room, Fable M5); training scope S+G+F+D ruled by Zero in-window 2026-09-11 ~13:38Z
- **Executor:** RC-CLOSE Dux, Pro session nuzantara-47 (window jump 1)
- **Container:** `nuzantara-rag` machine `1781e5eda03438` release v4421, Qdrant server 1.16.3, client 1.19.0 <!-- pragma: allowlist secret -->
- **Detector:** backend.services.misc.curated_qa_government_fee_detector — row_is_refused (curated_qa answer field), text_is_refused (training chunk text)
- **PII:** none in this file: opaque point ids only, no payload text. Two email-bearing training chunks (one F deleted, one I kept) carry a staff balizero.com address, no client text; all training points are synthetic Client/Consultant dialogues.

## Measure (before any write)

| collection                    | points_count | scrolled | detector hits | candidates confirmed                                   |
| ----------------------------- | ------------ | -------- | ------------- | ------------------------------------------------------ |
| curated_qa                    | 806          | 806      | 24            | 7 ruling-2 prefixes, each exactly one point, each read |
| training_conversations_hybrid | 3638         | 3638     | 74            | all 74 read and classed                                |

Training classes: S_strict_split = 24, G_government_fee_only = 25, F_gov_fee_free_plus_our_fee = 7, D_all_in_total_disclosing_pnbp = 3, T_third_party_bpn_pnbp = 4, I_compliant = 11. Deleted: S, G, F, D (n = 59). Kept: T, I.

## Snapshot (with vectors)

Taken 2026-09-11T13:28Z (in-container read, with vectors); materialised and byte-verified 2026-09-11T13:35Z. Restore: rc2b_restore.py <snapshot.json> [comma-separated ids], run in the rag container (upsert; dense + bm25 sparse named vectors).

- `~/.nuzantara-lane-e-backups/rc2b_2026-09-11_curated_qa.json` mode 0600, 69274 B, 7 points, sha256 `81ad56ab2024c8ecbb8573483ac0cf3aaf72302aba7931505251ef07f40d4709` <!-- pragma: allowlist secret -->
- `~/.nuzantara-lane-e-backups/rc2b_2026-09-11_training_conversations_hybrid.json` mode 0600, 802597 B, 74 points, sha256 `9976fb835710fe736c5f65d760da9704d9408eb5a22294b143d7e202d214c349` <!-- pragma: allowlist secret -->

## Delete

- Script sha256 `7e99ba296fa0ed4a06f23abfc277f241505fd2ae0e2758c6bc2a3974a409137b` <!-- pragma: allowlist secret -->
- Preconditions: points_count 806/3638 AND all 66 targets found AND all 66 still refused by the detector, else exit 2 before any write.

| phase  | at (UTC)             | collection                    | result                                                                                                                                  |
| ------ | -------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| pre    | 2026-09-11T13:41:42Z | curated_qa                    | points_count 806, targets 7, found 7, still refused 7                                                                                   |
| pre    | 2026-09-11T13:41:42Z | training_conversations_hybrid | points_count 3638, targets 59, found 59, still refused 59                                                                               |
| delete | 2026-09-11T13:41:43Z | curated_qa                    | requested 7, status completed, operation_id 66                                                                                          |
| delete | 2026-09-11T13:41:43Z | training_conversations_hybrid | requested 59, status completed, operation_id 2581                                                                                       |
| post   | 2026-09-11T13:41:45Z | curated_qa                    | points_count 799 (expected 799), targets remaining 0, scrolled 799, detector hits 17, deleted ids among hits 0                          |
| post   | 2026-09-11T13:41:50Z | training_conversations_hybrid | points_count 3579 (expected 3579), targets remaining 0, scrolled 3579, detector hits 15, deleted ids among hits 0, hits == kept T+I set |

## Opaque point ids

Deleted from `curated_qa` (7):

```text
11b7e26d-ca93-5e4f-8d8b-33ff4b2f8bb4
12d804e9-2378-5ead-ae9f-f0d326052a80
1b53de60-7d0b-547f-a2ec-a98adfcfd8c2
8b520434-1e16-5b73-bd50-8dff9ca93432
8ebf681f-e34c-5030-9e03-5fdc121fce49
e407d532-7bcf-5ee5-a933-8b12fad8db6f
eacec21f-f324-5cd7-a55a-07749dfe66d2
```

Deleted from `training_conversations_hybrid`, class S (24):

```text
10440304085221173839
13197943987411976211
16654959745627765076
17200241673321796377
18274763-f7eb-4554-ab12-f8802a79394c
1e6221da-2879-464d-8241-0c5f15d8335d
2391946023793360824
2551964275609437340
26c43bf4-9554-4406-8bac-c22235aea7d2
30a56173-4830-4cf6-9d0f-257aad659a76
3c466c46-2bb4-4e1a-b869-049c384caa33
446361089904549776
4987045939842351672
4fb3883f-90ce-4dea-a75a-c5cf42171afe
6c9669f5-8d96-4ed5-9a91-d163dee9b680
7369ef31-2002-411f-bdd8-56dfe4670e8a
745c72cb-f4f7-48ea-92b6-67a5310417ef
7559006244385465166
8934986740613639145
ad852c54-a2e8-4949-8347-89b1f21b8690
c0e87fa5-fe37-478a-9e1b-82856ac99ebf
c1e0258c-ec6e-4ecb-977a-6a591ab4ab5c
ca3c8805-2f3f-4c81-a1d7-d40f424d5790
ef70ec71-e72b-4e79-8857-7c05b6f8ee92
```

Deleted from `training_conversations_hybrid`, class G (25):

```text
10090509744974947846
1067266928500260054
10695072468493934584
10962457598033285801
14884597932276728311
15202924577083940513
16781468968445179438
17385359853742107089
18309052657992869664
2607870328408538859
3497458247334538959
35b06bf7-0137-4eb5-9690-0607a4e28d6f
39830555227371673
4ac7ca9c-1d5c-4199-a90d-603f9ecb7ed3
585f024a-e147-46f6-92f6-db666ee08728
59158488-9fec-4cd6-ad95-21f9b309fffe
5c37c6f4-ccb0-44f4-8ef6-eb2e9321d0e9
7413254456390159864
8034521235828773438
8296260951369328810
88539020-6103-4e30-bd96-4f4d88b02344
98a24d2e-9a2e-48e7-9ea8-ef329c753c2d
baee0ff0-d99e-4864-8577-f1bd111c5728
bdaa32ea-b190-4f2b-b65b-9451ebdcf1bb
f0784174-a75d-4b70-888c-333e77b74c32
```

Deleted from `training_conversations_hybrid`, class F (7):

```text
13091624898423571629
14256339685969245976
149185640773935897
18318711145683984457
3744473580019590514
4127579138313440246
9120834327082471318
```

Deleted from `training_conversations_hybrid`, class D (3):

```text
3963d31d-f338-46f4-be38-c054f66b531a
9185a573-58ec-4b11-a2cc-e7f8de9c892a
c9a902e8-068b-4c58-8f66-7ee4213c4d18
```

Kept in `training_conversations_hybrid` (detector hit, not deleted), class T (4):

```text
7055737071150403730
823624986578221185
866224871413208865
ac1891a0-22fe-4130-a2ef-63c052f0ba3d
```

Kept in `training_conversations_hybrid` (detector hit, not deleted), class I (11):

```text
13851017178477279395
14462167504052134379
2d89b18b-d6e2-485e-afed-741a654ec756
3713699631719653664
4332057000664747041
67d18b81-734f-4c3f-98f3-e313dea8418c
7198794333058199861
7992677432345094881
7b4ed9f0-7847-4a97-91aa-591989b2cbf1
86667154-398b-4550-b079-4c5e3fc41941
aa62d70d-8e02-4c31-b291-dcfe42a9c8eb
```
