"""kbli_filiera — GARUDA-FILIERA Batch 0 vault-bootstrap compilers.

Deterministic, no-LLM Python compilers per the three-layer division of
labor in research/operations/2026-07-16-kbli-garuda-filiera-workflow.md §1:
an LLM never manufactures a deterministic fact — these scripts are the
ONLY sanctioned writers of the raw-evidence vault (L0,
research/operations/2026-07-16-kbli-filiera-methodology.md P4) and,
downstream, of data/kbli-filiera/** (guard-enforced:
infra/claude-hooks/data-plane-registry.json, id "kbli-filiera").

Modules:
  vault_common       — shared HTTP/hash/JSONL/logging utilities.
  vault_fetch_pp28    — PP 28/2025 lampiran corpus (peraturan.bpk.go.id).
  vault_fetch_oss     — full OSS RBA re-snapshot (gw.oss.go.id).
  vault_fetch_bps     — BPS Tabel Konversi registrar (browser-manual, Turnstile-blocked).
  vault_manifest      — deterministic sha256 manifest walker over the vault.
"""
