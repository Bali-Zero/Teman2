# Tier 1 Panel Brief — WhatsApp Corpus 105k

Antonello Siano is the owner of Bali Zero, an Indonesia/Bali immigration, company setup, tax, and property agency. He has a local-only archive of WhatsApp conversations assembled on 2026-05-26 on his Pro Mac at `~/Desktop/wa-chats-MASTER-2026-05-26/`.

Important privacy and sovereignty constraints:

- Symbiosis Law 2: WhatsApp data does not leave the Pro in cleartext.
- No raw WhatsApp message content may be uploaded to Anthropic/OpenAI/Google/DeepSeek or any other cloud model.
- Cloud models may reason only on this sanitized metadata brief.
- Team operational chat privacy is strict: employee/team communications must stay local.
- Personal/family/friend chat privacy is strict: absolute private ownership.
- Excluded: publishing chat content as book/podcast, selling/monetizing the corpus, commercial model training on the corpus, or any workflow requiring non-E2E cloud upload.

Verified local corpus facts from shell checks on 2026-05-26:

- Root: `~/Desktop/wa-chats-MASTER-2026-05-26/`.
- `find` sees 698 `.txt` chat files: 288 in `01_wa-mirror-db/`, 400 in `02_zip-extracted/`, 10 in `03_drive-icloud/`.
- Archive `INDEX.md` reports 699 total files because it counts `01_wa-mirror-db/INDEX.md`; actual chat `.txt` files are 698.
- Regex parser sees 105,532 message-start records total; user-provided target count is 105,530, so there is a two-record reconciliation issue.
- Source counts by parser:
  - `01_wa-mirror-db/`: 14,847 message-start records, 288 `.txt` chat files, per-contact format `YYYY-MM-DD HH:MM [SENT|RECEIVED] msg`.
  - `02_zip-extracted/`: 74,753 message-start records, 400 `.txt` chat files, WhatsApp export format `[DD/MM/YY, HH.MM.SS] Name: msg`.
  - `03_drive-icloud/`: 15,932 message-start records, 10 `.txt` chat files, WhatsApp export format.
- ZIP source breakdown by file count and parser message-start records:
  - Adit: 2 files, 227 messages.
  - Ari: 30 files, 8,553 messages.
  - GoogleDrive: 210 files, 45,136 messages.
  - Krisna: 52 files, 10,156 messages.
  - PILOT: 1 file, 46 messages.
  - Sahira: 51 files, 8,523 messages.
  - Surya: 54 files, 2,112 messages.
- Text only: media/audio/photos/stickers are not present in the `.txt` archive.
- Time range in archive documentation: 2023 to 2026, with some Dec 2022 entries in mirror stats. Treat exact date coverage as needing per-file verification.

Available local stack:

- Pro Mac M4 Pro 48GB, Mini-Pro2 M4 Pro 24GB H24 currently unreachable over SSH from this session.
- Local Python + Postgres.
- Ollama local models available: `qwen3.5:9b`, `qwen2.5vl:7b`, `bge-m3:latest`.
- Nuzantara repo has FastAPI backend, Next.js surfaces, local MCP/tooling, and existing Bali Zero CRM/knowledge graph direction.
- Preferred implementation posture: local-first, small verified pilots, no raw content in `my.balizero.com`, internal/admin-only evidence in `kita.balizero.com`.

Task:

Propose 15-20 concrete and executable use cases for this WhatsApp corpus. Prioritize by:

1. business value for Bali Zero,
2. personal/historical value,
3. technical feasibility with local stack such as Ollama, Postgres, Python, bge-m3, local Qdrant or pgvector,
4. compliance with local sovereignty and privacy constraints.

Output format:

- Markdown table with exactly four columns:
  - Use case
  - Rationale
  - LLM/tools required
  - Estimated effort
- Keep every use case executable, not abstract.
- Include both obvious and non-obvious ideas.
- Do not propose excluded uses.
- Do not assume extra corpus statistics beyond the verified facts above.
