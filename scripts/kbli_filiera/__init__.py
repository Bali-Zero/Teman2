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
  vault_fetch_perpres — Perpres 10/2021 + 49/2021, the Daftar Positif Investasi
                        (peraturan.bpk.go.id). Added 2026-08-02: until then the
                        instrument every `pma_status` cites was in NO vault, so
                        both annex transcriptions were unreproducible claims.
  vault_manifest      — deterministic sha256 manifest walker over the vault.

Annex readers (join the vaulted instrument against the catalogue, report only):
  parse_perpres_lampiran2          — compiles the Koperasi/UMKM reservation table.
  perpres_umkm_reservation_relation — reports where that table and the catalogue differ.
  perpres_foreign_cap_relation      — the same for Lampiran III (percentage caps).
  perpres_body_default_relation     — the NEGATIVE locator: what the BODY says about
                                      the ~1,288 codes no annex names (Pasal 3(1)(d)
                                      residual default, Pasal 7(1) Usaha Besar floor).
"""
