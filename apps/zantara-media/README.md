# zantara-media — Curator Agent for Bali Zero

Mata Garuda Layer 4.5 — Asset indexer + multi-channel curator.

## Components

- **`indexer/`** — Daily incremental crawler of `GARUDA/` Drive folder
- **`security/dlp.py`** — PII guard (NIK, KITAS, NPWP detection)
- **`curators/`** — Per-channel composers (IG carousel, IG video, TG, newsletter, blog)
- **`selection/`** — Asset pool builder + scoring + selection
- **`voiceover/`** — Google TTS OAuth wrapper
- **`maintenance/gc.py`** — Weekly tombstone collector

## Install

```bash
cd apps/zantara-media
pip install -e ".[dev]"
```

## Bootstrap (one-time)

```bash
# 1. Run migration 109
PYTHONPATH=. python -m backend.db.migration_manager up

# 2. Create Qdrant collection
garuda-bootstrap

# 3. Initialize Drive cursor (first run is no-op, just bookmarks)
garuda-indexer
```

## Daily run (cron OpenClaw)

```bash
garuda-indexer  # 04:30 WITA
```

## Cost

- $0.20 one-shot OpenAI embeddings for first 7000 files
- $0.05/month operational
- All other tools: local Ollama, Whisper, Tesseract, ffmpeg, GDrive OAuth

## Specs

- Design v2: `docs/superpowers/specs/2026-04-14-curator-agent-garuda-design-v2.md`

## GARUDA Drive Folder IDs

| Path                   | Folder ID                           |
| ---------------------- | ----------------------------------- |
| `GARUDA/`              | `1xjkBpgic3tZl3_K1u7vy-qJpw7XzpIYN` |
| `GARUDA/photos/`       | `1c9QnRb22XdcrFH8ukxgJeWW41soZhzVq` |
| `GARUDA/videos/`       | `1QZ6hnEqUAxIwhz6yhWeXh6m3QsgFnJ6G` |
| `GARUDA/audio/`        | `1CX2K-MtRQVMqDwlbcT9gLTGf4mGmGVh3` |
| `GARUDA/intelligence/` | `1n3VjN-YZGGH-6-yByxIi0rLGxi4iTDu1` |
| `GARUDA/drafts/`       | `1b7ERuRssLPAxKYHtAhv2Kx-G81ot0Ulb` |
| `GARUDA/research/`     | `18E-rHjO94JFqao1xMCoA2mmy4oK9Waw7` |
| `GARUDA/published/`    | `1dX87C514aOZO82NTxl8meHiiO3dhIJNl` |
