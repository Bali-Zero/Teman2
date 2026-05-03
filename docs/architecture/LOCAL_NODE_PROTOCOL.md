# LOCAL NODE PROTOCOL: The "Hand of God" Architecture

> **Status:** DRAFT (2026-01-27)
> **Goal:** Establish a secure, high-bandwidth bridge between Nuzantara (Cloud Brain) and MoltBot (Local Hand).

## 1. The Philosophy: "Maximum Power"

To achieve "Maximum Power", the separation between Cloud and Local must dissolve. Nuzantara becomes the **Strategic Commander**, and MoltBot becomes the **Tactical Field Operator**.

| Component     | Location         | Role             | Superpower                                                               |
| ------------- | ---------------- | ---------------- | ------------------------------------------------------------------------ |
| **NUZANTARA** | Fly.io (Cloud)   | **The Brain** 🧠 | Massive Memory (53k docs), Strategy, 24/7 Uptime, API Orchestration      |
| **MOLTBOT**   | Mac Mini (Local) | **The Hand** 🖐️  | Filesystem Access, Terminal (Sudo), Browser Automation, Hardware Control |

## 2. The "Axon" Bridge (Communication Layer)

We need a secure channel for the Brain to issue commands to the Hand.

### Phase 1: The Telegram Bridge (Immediate)

Since both systems integrate with Telegram, we use it as the "Bus".

- **Channel:** Dedicated Secret Group ("Nuzantara Ops").
- **Protocol:**
  - **Brain:** Sends `/cmd deploy backend --force`
  - **Hand (MoltBot):** Reads msg -> Executes specific script -> Replies with Logs.

### Phase 2: Direct Neural Link (Future)

- **Technology:** Ngrok / Cloudflare Tunnel / Tailscale.
- **Mechanism:** MoltBot exposes a local API endpoint (e.g., `localhost:8000/execute`) securely to Nuzantara's backend IP only.

## 3. "Maximum Power" Use Cases

### A. The "Self-Healing" Loop 🛡️

1. **Event:** Nuzantara Detects a Crash on Fly.io (via Sentry/Logs).
2. **Analysis:** Brain diagnoses "Out of Memory on Machine 3".
3. **Command:** Brain signals Hand: "Scale up VM size instantly."
4. **Execution:** MoltBot runs `fly scale vm shared-cpu-4x -a nuzantara-rag`.
5. **Result:** Crisis averted while you sleep.

### B. The "Intel Vacuum" 🕵️

1. **Event:** You save a PDF to `~/Desktop/Startups_Bali_2026.pdf`.
2. **Detection:** MoltBot watches the folder.
3. **Action:** MoltBot OCRs the file locally (saving cloud costs) and pushes clean JSON to Nuzantara's API.
4. **Integration:** Nuzantara indexes it into Qdrant immediately.

### C. The "Coding Partner" 👨‍💻

1. **Request:** You tell Nuzantara "Refactor the authentication module."
2. **Generation:** Nuzantara writes the new code files in memory.
3. **Transmission:** Brain sends files to Hand.
4. **Application:** MoltBot creates a git branch, writes files to disk, runs `./sentinel` (Tests), and commits.
5. **Review:** You just see a PR ready to merge.

## 4. Security Protocols (The "Asimov" Layer)

To prevent "SkyNet" scenarios, we implement strict Rules of Engagement:

1. **Human-in-the-Loop (Level 1):** MoltBot requires a 👍 reaction on Telegram from YOU before executing any `write` or `delete` command.
2. **Sandbox:** MoltBot operates ONLY within `/Users/antonellosiano/Projects/nuzantara`.
3. **Kill Switch:** A specific Telegram command (`/shutdown`) instantly kills the MoltBot process.

## 5. Implementation Roadmap

1. **Configure MoltBot:** Give it access to the Nuzantara repo and the `scripts/` folder.
2. **Create the "Hand" Identity:** In Nuzantara's database, register MoltBot as a special Team Member (role: `system_agent`).
3. **Build the Bridge:** Update `bali-intel-scraper` to support "Command Mode" messages.

---

**Next Step:** Deploy Phase 1 (Telegram Bridge) using the existing bot infrastructure.
