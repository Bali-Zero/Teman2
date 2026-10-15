# research(udb-wave8): B05 operation contracts — validator, 23-contract ledger, relation-bound catalog join

Branch: `agent/mini-pro2/db/udb-b05-contracts` · Campaign `universal-db-wave8-20261015`, block B05.
Research-only: every file lives under `research/operations/udb-wave8/B05/`. No runtime code, no
migration, no configuration and no client data change.

## What this adds

- `b05_contracts_validator.py` (stdlib): `--generate` rebuilds `operation-contracts.json` / `.csv`
  from the pinned inputs, and `--validate` checks them. It covers the AST counterexamples, the
  relation-bound catalog join and the denominator accounting computed from data.
- `test_b05_operation_contracts.py`: 7 tests over the on-disk artifacts. No DB and no network.
- `operation-contracts.json` / `.csv`: 23 operation contracts. 19 are PARTIAL, 3 CONFLICT,
  1 BLOCKED and 0 complete.
- `PRINCIPAL-ROLE-BINDING-PROPOSAL.md`: a proposal only. It grants nothing and runs nothing.
- `DEFINITIVE-SYNTHESIS.md`: opens with a Dux correction that supersedes the earlier
  "16/16 join", the "45 + 3,477 + 2,508" split and the `--self-test` claims.

## Observed (Mini, base `8061c88e0c`)

| Check | Result |
|---|---|
| `pytest -q research/operations/udb-wave8/B05/test_b05_operation_contracts.py` | 7 passed, exit 0 |
| `b05_contracts_validator.py --generate` | exit 0 |
| `b05_contracts_validator.py --validate` | exit 0 |

| Fact | Value |
|---|---|
| Relation join | 8 of 8 matched via `md5(database‖chr(31)‖schema‖chr(31)‖relation)`, 0 unmatched |
| Role join | 3 of 5 configured roles matched. `nuzantara` and `nuzantara_app` are unmatched |
| Denominator | 6,029 consumer-matrix rows + 1 lead delta = 6,030 leads, in 33 buckets computed from data |
| `conversation_repository.save_messages` | Runs in a transaction, but takes no advisory lock and no `FOR UPDATE` row lock |
| `migration_manager.apply_all_pending` lock-busy | Returns empty lists, and `cmd_apply` / `main` exit 0. Counterexample proven |

## Still open (`block_closed: false`)

- The runtime principal-to-role binding is unobserved: `POOL-FACTORY-SOURCE.json` has
  `target_role=UNOBSERVED`.
- The active-consumer denominator is `UNKNOWN`, and 4,276 non-retained leads stay uninstantiated.
- Live `pg_indexes` / `pg_constraint` data and runtime GUC traces were not read. They need an
  admitted native read, and none is authorized in this campaign.

Bites: the consumer is the B05 validator together with its pytest suite, which ships in this PR.
Observed on the committed sources: `pytest` 7 passed (exit 0) and `--validate` exit 0. The ledger
joins 8 of 8 relations through the chr(31) database/schema/relation derivation, and it records the
lock-busy exit-0 counterexample.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
