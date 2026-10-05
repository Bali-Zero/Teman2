---
adversarial_review: exempt-machine-report # nb-curator daily health snapshot (generated artifact, not a research deliverable)
---

# NB Arsenal Health Report — 2026-10-05

## Health Overview (Mode B)
- Total Notebooks: 65 | Healthy: 62 | Empty/Broken: 3 | Near Cap (>=490): 0
- Empty notebooks (0 sources):
  - `bafceb4f-cd61-4922-8fc1-932852d1c054`: Labor Law Research May 2025
  - `761c79e8-2ed2-491a-bd8f-da68f2d1f270`: NB-INTEL Other
  - `530dff78-ce26-4e0a-b40c-1aacfbcc9a5a`: NB-INTEL Other
- High-volume monitors: `NB-PROBE-SANDBOX-2026-05` (475/500), `NB-INTEL-AIResearch-2` (457/500), `NB-LAB-AGENT-ENGINEERING-2026` (395/500), `NB-INTEL-AIResearch` (389/500).

## NB-INTEL Snapshot & Dedup Proposals (Mode C Full Pass)
- Inventory: AIResearch (389), Press (271), Tax (224), Regulation (113), Immigration (11)
- Proposed Dedup / Curation Clusters:
  1. **NB-INTEL-Tax**: Merge syndication duplicate: "DJP Punya Jurus Baru Kejar Pajak Digital, Setoran Bisa Naik 2x Lipat!" and "... - Ditjen Pajak | Pajak Berita".
  2. **NB-INTEL-Tax**: Merge near-dup: "PER-8/PJ/2026 Terbit, DJP Sempurnakan Mekanisme Pembayaran Pajak di Coretax" and "PER-8/PJ/2026 Berlaku, DJP Perbarui Ketentuan Pembayaran...".
  3. **NB-INTEL-Immigration**: Remove dead link "Not Found (#404) – Direktorat Jenderal Imigrasi".
- Proposed Summarization (Press):
  - Topic cluster on marketplace tax postponement to Nov 2026 (PMK 37/2025) has >=10 recurring articles. Propose offline Ollama synthesis into master brief.
- Stale Sources (>90d): 0 active stale feeds; empty containers above flagged for cleanup.

## Recommended Operator Actions
- [ ] Approve 2 near-dup merges in NB-INTEL-Tax and 1 removal in NB-INTEL-Immigration.
- [ ] Review marketplace tax cluster synthesis for NB-INTEL-Press.
- [ ] Archive/delete 3 empty legacy notebooks (`bafceb4f`, `761c79e8`, `530dff78`).
