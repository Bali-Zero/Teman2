# System_Engine Agent Arsenal & Protocol

**Generated:** 2026-01-23
**Agent**: System_Engine (The Orchestrator)
**Scope**: Local OS, Multi-Cloud, AI

> **MISSION**: This document serves as the persistent "Memory Core" for all future AI Agents accessing this project. It defines the available tools (The Arsenal) and the standard operating procedures (The Workflows).

---

## 🏗️ The "Heavy Arsenal" (Capability Matrix)

| Category          | Agent (Tool)       | Capability                                                                               |
| :---------------- | :----------------- | :--------------------------------------------------------------------------------------- |
| **THE CAPTAIN**   | `claude`           | **Senior Partner (Max)**. Access to `mcp`, `browser`, `skills`. Orchestrates all others. |
| **THE CO-PILOT**  | `gemini`           | **Google AI Ultra**. High-reasoning, large context window.                               |
| **THE ARCHITECT** | `cursor agent`     | **IDE Agent**. Can write code, run terminals, and execute composer flows from CLI.       |
| **Computing**     | `runpodctl`        | **Rent GPUs** on demand. Use for heavy inference/training.                               |
| **AI (Local)**    | `ollama`           | Run Llama 3/Mistral locally (Free & Private).                                            |
| **Cloud (Major)** | `aws`              | AWS Services (S3, EC2). Infrastructure backbone.                                         |
| **Cloud (PaaS)**  | `fly`, `vercel`    | **Production Hosting**. (Backend / Frontend).                                            |
| **Cloud (Data)**  | `gdrive`, `rclone` | Sync TBs of data. Google Drive integration.                                              |
| **Infra as Code** | `terraform`        | Provision infrastructure programmatically.                                               |
| **Media**         | `ffmpeg`, `CapCut` | Process Video/Audio (The "Eyes & Ears").                                                 |
| **Networking**    | `cloudflared`      | Expose local ports safely (Tunnels).                                                     |
| **Monitoring**    | `sentry-cli`       | Error tracking.                                                                          |

### 🧠 Claude Max Capabilities (Verified)

- **MCP Servers**: `filesystem`, `docker`, `flyio`, `playwright`, `brave-search`, `github`.
- **Browser**: Native Chrome integration (requires setup).
- **Skills**: Autonomous coding, planning, execution.

---

## ⚡ Strategic Workflows (Slash Commands)

Future Agents: When the user invokes these commands, execute the following chains.

### `/deploy-universe`

**Trigger**: Ship everything to production.

1.  **Frontend**: `vercel --prod`
2.  **Backend**: `fly deploy`
3.  **Sync**: `gh release create` (Create Release Trace)

### `/gpu-burst`

**Trigger**: Need massive compute (e.g., Training, Batch Processing).

1.  **Provison**: `runpodctl create pod ...`
2.  **Job**: Send training/inference job via SSH/API.
3.  **Shutdown**: `runpodctl remove pod ...` (Save $$$)

### `/intel-check`

**Trigger**: Gather intelligence & Sync.

1.  **Run**: `python apps/bali-intel-scraper/run.py`
2.  **Backup**: `rclone copy ./data remote:backup`
3.  **Notify**: Log results to `docs/logs/`.

### `/media-factory`

**Trigger**: Process Content.

1.  **Download**: `gdrive download [folder_id]`
2.  **Process**: `ffmpeg -i input.mp4 -vf ... output.mp4`
3.  **Upload**: `aws s3 cp output.mp4 s3://...`

---

## 🔐 Credentials & Secrets

_Access to these tools is managed via:_

- `~/.aws/credentials`
- `~/.fly/config.yml`
- `.env` files (Local)
- `fly secrets` (Production)

**Usage Rule**: NEVER print raw credentials to chat. Use environment variables.
