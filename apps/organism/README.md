# Nuzantara Autonomic Organism

See `docs/superpowers/specs/2026-04-22-autonomic-organism-design.md` for full design.

24/7 self-healing layer: event bus + stateless Supervisor + idempotent Actuators.

## Genoma (`organism/genome.yaml`)

Single source of truth for the 149 organi nervosi. Spec:
`docs/innervation-2026-04-29/07_innervation_protocol.md` §2.

After editing `genome.yaml`, recompute the canonical SHA256 checksum and let
the validator confirm the schema:

```bash
PYTHONPATH=apps/organism python3 -m organism.tools.validate_genome \
    apps/organism/organism/genome.yaml --update-checksum

PYTHONPATH=apps/organism python3 -m organism.tools.validate_genome \
    apps/organism/organism/genome.yaml
```

The pre-commit hook `validate-genome` (in repo `.pre-commit-config.yaml`)
runs the second command automatically on every commit that touches the file
and rejects commits whose recorded checksum is missing or wrong (NB-1 ADR-7
HALT-on-mismatch). Install with `pre-commit install` if not already active.

`yaml.safe_dump` from `--update-checksum` strips comments. Re-apply the
header preamble manually after running it; switching to `ruamel.yaml` for
comment-preserving rewrites is a future cleanup.
