# Nuzantara Autonomic Organism

See `docs/superpowers/specs/2026-04-22-autonomic-organism-design.md` for full design.

24/7 self-healing layer: event bus + stateless Supervisor + idempotent Actuators.

## Innervation Genoma (`organism/organs_registry.yaml`)

Single source of truth for the ~149 organi nervosi. Spec:
`docs/innervation-2026-04-29/07_innervation_protocol.md` §2.

> **Renamed 2026-05-08 (IG-3):** the file `genome.yaml` is now
> `organs_registry.yaml`. The SYSTEM CONCEPT name "Innervation Genoma"
> stays everywhere. Backward-compat:
> - filesystem symlink `organism/genome.yaml → organs_registry.yaml`
> - Python alias `organism.tools.validate_genome` re-exports
>   `validate_organs_registry` and emits `DeprecationWarning`
> - CLI `python -m organism.tools.validate_genome` still works (prints a
>   stderr deprecation note and delegates)
>
> Removal of the legacy aliases scheduled **2026-06-08** (1 month).

After editing `organs_registry.yaml`, recompute the canonical SHA256
checksum and let the validator confirm the schema:

```bash
PYTHONPATH=apps/organism python3 -m organism.tools.validate_organs_registry \
    apps/organism/organism/organs_registry.yaml --update-checksum

PYTHONPATH=apps/organism python3 -m organism.tools.validate_organs_registry \
    apps/organism/organism/organs_registry.yaml
```

The pre-commit hook `validate-organs-registry` (in repo
`.pre-commit-config.yaml`) runs the second command automatically on every
commit that touches the file and rejects commits whose recorded checksum
is missing or wrong (NB-1 ADR-7 HALT-on-mismatch). Install with
`pre-commit install` if not already active.

`yaml.safe_dump` from `--update-checksum` strips comments. Re-apply the
header preamble manually after running it; switching to `ruamel.yaml` for
comment-preserving rewrites is a future cleanup.

For surgical checksum-only edits (preserving comments), edit the
`checksum:` line in place to the value printed by the validator's
`expected=…` error.
