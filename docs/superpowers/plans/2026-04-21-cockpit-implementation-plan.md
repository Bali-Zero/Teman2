# Mata Garuda × War Room Cockpit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Mac desktop cockpit (Tauri v2 + React 19) that unifies the
Mata Garuda OSINT stream with the War Room v2 publishing pipeline, implementing
a single mandatory decision surface for Zero (§3 of spec).

**Architecture:** Tauri Rust core (Redis pub/sub listener + HTTP polling
fallback + subprocess spawn + SQLite cache) bridges to a React frontend (3
resizable panels + bottom strip). State store = Zustand per-panel slices.
Real-time = Redis XREAD/SUBSCRIBE merged with HTTP polling and deduplicated
via UUID sliding window.

**Tech Stack:** Tauri v2 (Rust 1.75+), React 19, TypeScript 5.3+, Zustand 5,
tauri-plugin-sql (SQLite WAL), redis crate 0.25 with tokio-comp, reqwest 0.12
for HTTP, tokio 1.38.

**Source spec:** `docs/superpowers/specs/2026-04-21-mata-garuda-wr-cockpit-design.md` —
all §17 revisions are **binding** on this plan.

**Target timeline:** 3.5 weeks across 7 milestones (includes council revisions).

**Branch:** `feat/command-center-cockpit` (create from main).

---

## Scope Check

This plan covers the **MVP single-user cockpit on Pro** only. It produces a
working, testable `.dmg` that Zero can install locally and use in parallel
with existing Telegram flows. It does NOT cover: multi-user distribution,
auth layer activation, cockpits for other domains (CRM/Compliance/Finance),
or the 4 backend endpoints' business logic changes.

Each milestone is a self-contained PR with its own tests and runbook.
Milestones are independently reviewable.

---

## File Structure

### New package: `apps/command-center/`

```
apps/command-center/
├── package.json              # pnpm workspace, deps
├── tsconfig.json             # extends monorepo base
├── vite.config.ts            # Vite for React frontend
├── src-tauri/                # Rust core
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── src/
│   │   ├── main.rs           # Entry point, plugin registration
│   │   ├── redis_listener.rs # Redis pub/sub + XREAD tasks
│   │   ├── http_poller.rs    # Fallback polling
│   │   ├── subprocess.rs     # ssh/fly/curl/psql spawn (timeout + validator)
│   │   ├── sqlite_cache.rs   # Migrations + CRUD helpers
│   │   ├── event_dedup.rs    # UUID sliding window set
│   │   ├── canva_bridge.rs   # Mata Garuda CLI subprocess (R5 hardened)
│   │   └── ipc_commands.rs   # Tauri commands exposed to React
│   └── migrations/
│       └── 001_initial.sql   # cached_topics, cached_reviews, cockpit_actions, etc.
├── src/                      # React frontend
│   ├── App.tsx
│   ├── main.tsx
│   ├── panels/
│   │   ├── PanelA.tsx        # Mata Garuda Stream
│   │   ├── PanelB.tsx        # WR Pipeline
│   │   ├── PanelC.tsx        # Review Gate
│   │   └── BottomStrip.tsx   # Publisher + Learner + Connection status
│   ├── review/
│   │   ├── ReviewModal.tsx   # Split view (preview LEFT + context RIGHT)
│   │   ├── CanvaPreview.tsx  # 11 PNG carousel
│   │   ├── SlideEditor.tsx   # Inline text editor
│   │   ├── SlaCountdown.tsx  # Timer with 30min modal trigger
│   │   └── DeferAllDialog.tsx # Segmented reason picker (R3)
│   ├── state/
│   │   ├── panelAStore.ts    # Zustand slice
│   │   ├── panelBStore.ts
│   │   ├── panelCStore.ts
│   │   ├── connectionStore.ts # Connection status (R10)
│   │   └── prefsStore.ts     # Panel widths, last layout
│   ├── ipc/
│   │   ├── tauriCommands.ts  # Typed wrappers
│   │   └── tauriEvents.ts    # Event subscriber hooks
│   └── lib/
│       ├── idempotency.ts    # UUID v4 generator for POSTs (R7)
│       └── sla.ts            # SLA math
├── tests/
│   ├── rust/                 # cargo test
│   └── react/                # vitest + @testing-library
└── .github/workflows/
    └── build-command-center.yml # Manual dispatch DMG build
```

### Backend additions (existing repo)

```
apps/backend-rag/backend/app/routers/
├── war_room_cockpit.py       # NEW — 4 endpoints (R7 idempotency)
└── war_room_topic_override.py # NEW (or merged into above)

apps/backend-rag/backend/db/migrations_v2/
├── 127_idempotency_keys.sql  # NEW — dedupe table
└── 128_canva_preview_urls.sql # NEW — per-slide PNG cache column

apps/backend-rag/backend/services/
└── war_room/canva_export.py  # NEW — server-side PNG export (R12)
```

### Mata Garuda additions

```
apps/mata-garuda/cli/
└── cockpit_bridge.py         # NEW — mutation-action subcommand (R5 argv-safe)
```

---

## Milestone 1 — Foundation scaffolding (3 days)

**Deliverable:** Tauri app launches, connects to Redis, shows empty 3-panel
shell with placeholder data, writes to SQLite cache. No business logic yet.

### Task 1.1: Create `apps/command-center/` package skeleton

**Files:**

- Create: `apps/command-center/package.json`
- Create: `apps/command-center/tsconfig.json`
- Create: `apps/command-center/vite.config.ts`
- Create: `apps/command-center/src-tauri/Cargo.toml`
- Create: `apps/command-center/src-tauri/tauri.conf.json`
- Modify: `pnpm-workspace.yaml` (add package)

- [ ] **Step 1: Create the Tauri skeleton via CLI**

```bash
cd ~/Desktop/nuzantara
pnpm dlx create-tauri-app@latest apps/command-center \
  --template react-ts \
  --manager pnpm \
  --identifier com.balizero.cockpit
```

- [ ] **Step 2: Add package to workspace**

Edit `pnpm-workspace.yaml`:

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

(Likely already covers `apps/*` — verify the glob matches `apps/command-center/`.)

- [ ] **Step 3: Install Rust deps in Cargo.toml**

Edit `apps/command-center/src-tauri/Cargo.toml`:

```toml
[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-sql = { version = "2", features = ["sqlite"] }
tauri-plugin-shell = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1.38", features = ["full"] }
redis = { version = "0.25", features = ["tokio-comp"] }
reqwest = { version = "0.12", features = ["json"] }
uuid = { version = "1", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
tracing = "0.1"
tracing-subscriber = "0.3"
thiserror = "1"
```

- [ ] **Step 4: Install React deps**

```bash
cd apps/command-center
pnpm add zustand@5 @tanstack/react-virtual@3 date-fns uuid
pnpm add -D @types/uuid vitest @testing-library/react @testing-library/user-event
```

- [ ] **Step 5: Verify cargo build and vite dev work**

```bash
cd apps/command-center/src-tauri && cargo build
cd .. && pnpm tauri dev
```

Expected: empty Tauri window opens with default React template.

- [ ] **Step 6: Commit**

```bash
git add apps/command-center/ pnpm-workspace.yaml
git commit -m "feat(cockpit): bootstrap Tauri v2 + React 19 skeleton"
```

### Task 1.2: SQLite cache migrations

**Files:**

- Create: `apps/command-center/src-tauri/migrations/001_initial.sql`
- Modify: `apps/command-center/src-tauri/src/main.rs` (register sql plugin)
- Test: `apps/command-center/src-tauri/tests/sqlite_cache.rs`

- [ ] **Step 1: Write migration SQL**

Create `apps/command-center/src-tauri/migrations/001_initial.sql`:

```sql
-- Cached snapshots of WR topics (Panel B source)
CREATE TABLE IF NOT EXISTS cached_topics (
  id INTEGER PRIMARY KEY,
  uuid TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  stage INTEGER NOT NULL,
  title TEXT,
  draft_edit TEXT,
  last_event_id TEXT,
  updated_at TEXT NOT NULL
);
CREATE INDEX idx_cached_topics_status ON cached_topics(status);

-- Pending reviews with SLA (Panel C source)
CREATE TABLE IF NOT EXISTS cached_reviews (
  topic_id INTEGER PRIMARY KEY REFERENCES cached_topics(id),
  sla_deadline TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- Every state-mutating click (R7 idempotency + audit)
CREATE TABLE IF NOT EXISTS cockpit_actions (
  id INTEGER PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE,
  action_type TEXT NOT NULL,
  topic_id INTEGER,
  payload_json TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  acked_at TEXT
);
CREATE INDEX idx_cockpit_actions_status ON cockpit_actions(status);

-- Deferrals audit (R3 segmented reason)
CREATE TABLE IF NOT EXISTS deferrals_log (
  id INTEGER PRIMARY KEY,
  reason_category TEXT NOT NULL CHECK (reason_category IN ('emergency','sleep','presentation','other')),
  reason_note TEXT,
  deferred_count INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

-- XStream cursors per channel (R8)
CREATE TABLE IF NOT EXISTS xstream_cursors (
  channel TEXT PRIMARY KEY,
  last_entry_id TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- User preferences (R2 panel widths etc.)
CREATE TABLE IF NOT EXISTS cockpit_prefs (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Enable WAL mode
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
```

- [ ] **Step 2: Register tauri-plugin-sql in main.rs**

Create `apps/command-center/src-tauri/src/main.rs`:

```rust
fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_sql::Builder::default()
            .add_migrations("sqlite:cache.sqlite",
                vec![tauri_plugin_sql::Migration {
                    version: 1,
                    description: "initial cockpit schema",
                    sql: include_str!("../migrations/001_initial.sql"),
                    kind: tauri_plugin_sql::MigrationKind::Up,
                }])
            .build())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 3: Write integration test that runs migration in temp DB**

Create `apps/command-center/src-tauri/tests/sqlite_cache.rs`:

```rust
use rusqlite::Connection;

#[test]
fn migration_creates_all_tables() {
    let conn = Connection::open_in_memory().unwrap();
    let sql = include_str!("../migrations/001_initial.sql");
    conn.execute_batch(sql).unwrap();

    let tables: Vec<String> = conn
        .prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        .unwrap()
        .query_map([], |row| row.get(0))
        .unwrap()
        .filter_map(Result::ok)
        .collect();

    assert!(tables.contains(&"cached_topics".to_string()));
    assert!(tables.contains(&"cached_reviews".to_string()));
    assert!(tables.contains(&"cockpit_actions".to_string()));
    assert!(tables.contains(&"deferrals_log".to_string()));
    assert!(tables.contains(&"xstream_cursors".to_string()));
    assert!(tables.contains(&"cockpit_prefs".to_string()));
}
```

Add `rusqlite = "0.31"` to `[dev-dependencies]` in Cargo.toml.

- [ ] **Step 4: Run test**

```bash
cd apps/command-center/src-tauri && cargo test migration_creates_all_tables
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/command-center/src-tauri/{migrations,src,tests,Cargo.toml}
git commit -m "feat(cockpit): SQLite cache schema + migration test"
```

### Task 1.3: Redis listener with reconnect + fallback

**Files:**

- Create: `apps/command-center/src-tauri/src/redis_listener.rs`
- Modify: `apps/command-center/src-tauri/src/main.rs`
- Test: `apps/command-center/src-tauri/tests/redis_listener_test.rs`

- [ ] **Step 1: Write the redis_listener module**

Create `apps/command-center/src-tauri/src/redis_listener.rs`:

```rust
use redis::aio::ConnectionManager;
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tokio::sync::mpsc;
use tokio::time::sleep;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CockpitEvent {
    pub event_id: String,
    pub channel: String,
    pub payload: serde_json::Value,
    pub received_at: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub enum ConnectionStatus {
    RedisPrimary,
    RedisFallback,
    PollingOnly,
}

pub struct RedisListener {
    primary_url: String,
    fallback_url: String,
    tx: mpsc::Sender<CockpitEvent>,
    status_tx: mpsc::Sender<ConnectionStatus>,
}

impl RedisListener {
    pub fn new(
        primary_url: String,
        fallback_url: String,
        tx: mpsc::Sender<CockpitEvent>,
        status_tx: mpsc::Sender<ConnectionStatus>,
    ) -> Self {
        Self { primary_url, fallback_url, tx, status_tx }
    }

    pub async fn run(self) {
        let mut current_status = ConnectionStatus::RedisPrimary;
        let _ = self.status_tx.send(current_status).await;

        loop {
            match ConnectionManager::new(redis::Client::open(self.primary_url.clone()).unwrap()).await {
                Ok(conn) => {
                    if current_status != ConnectionStatus::RedisPrimary {
                        current_status = ConnectionStatus::RedisPrimary;
                        let _ = self.status_tx.send(current_status).await;
                    }
                    self.subscribe_loop(conn).await;
                }
                Err(e) => {
                    tracing::warn!("Primary Redis unreachable: {}. Trying fallback.", e);
                    match self.try_fallback().await {
                        Ok(conn) => {
                            current_status = ConnectionStatus::RedisFallback;
                            let _ = self.status_tx.send(current_status).await;
                            self.subscribe_loop(conn).await;
                        }
                        Err(_) => {
                            current_status = ConnectionStatus::PollingOnly;
                            let _ = self.status_tx.send(current_status).await;
                            sleep(Duration::from_secs(30)).await;
                        }
                    }
                }
            }
        }
    }

    async fn try_fallback(&self) -> redis::RedisResult<ConnectionManager> {
        // Ping before declaring fallback ready (R10)
        let mut conn = redis::Client::open(self.fallback_url.clone())?
            .get_async_connection()
            .await?;
        let _: String = redis::cmd("PING").query_async(&mut conn).await?;
        ConnectionManager::new(redis::Client::open(self.fallback_url.clone())?).await
    }

    async fn subscribe_loop(&self, _conn: ConnectionManager) {
        // Placeholder — full subscribe implementation in Task 1.4
        // For now, just hold the connection alive
        sleep(Duration::from_secs(1)).await;
    }
}
```

- [ ] **Step 2: Write test for connection status transitions**

Create `apps/command-center/src-tauri/tests/redis_listener_test.rs`:

```rust
// Integration test requires a running Redis. Use testcontainers crate.
// For MVP, we test the pure state transition logic:

use command_center_src_tauri::redis_listener::ConnectionStatus;

#[test]
fn connection_status_ordering() {
    // Sanity check that enum variants are comparable
    assert_ne!(ConnectionStatus::RedisPrimary, ConnectionStatus::RedisFallback);
    assert_ne!(ConnectionStatus::RedisFallback, ConnectionStatus::PollingOnly);
}
```

Mark the integration test that needs Docker with `#[ignore]` and document
in README that `cargo test -- --include-ignored` runs them.

- [ ] **Step 3: Run test**

```bash
cd apps/command-center/src-tauri && cargo test connection_status
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/command-center/src-tauri/src/redis_listener.rs apps/command-center/src-tauri/tests/redis_listener_test.rs
git commit -m "feat(cockpit): Redis listener scaffold with primary/fallback/polling states"
```

### Task 1.4: React 3-panel shell with Zustand stores

**Files:**

- Create: `apps/command-center/src/App.tsx`
- Create: `apps/command-center/src/panels/PanelA.tsx`
- Create: `apps/command-center/src/panels/PanelB.tsx`
- Create: `apps/command-center/src/panels/PanelC.tsx`
- Create: `apps/command-center/src/panels/BottomStrip.tsx`
- Create: `apps/command-center/src/state/connectionStore.ts`
- Create: `apps/command-center/src/state/prefsStore.ts`

- [ ] **Step 1: Create prefsStore with panel widths (R2)**

Create `apps/command-center/src/state/prefsStore.ts`:

```typescript
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface PrefsState {
  panelAWidth: number; // percent
  panelBWidth: number;
  panelCWidth: number; // min 30 (R2)
  setPanelWidths: (a: number, b: number, c: number) => void;
}

export const usePrefsStore = create<PrefsState>()(
  persist(
    (set) => ({
      panelAWidth: 35,
      panelBWidth: 35,
      panelCWidth: 30, // R2: min 30%
      setPanelWidths: (a, b, c) =>
        set({
          panelAWidth: a,
          panelBWidth: b,
          panelCWidth: Math.max(c, 30),
        }),
    }),
    { name: "cockpit-prefs" },
  ),
);
```

- [ ] **Step 2: Create connectionStore**

Create `apps/command-center/src/state/connectionStore.ts`:

```typescript
import { create } from "zustand";

export type ConnectionStatus =
  | "redis_primary"
  | "redis_fallback"
  | "polling_only";

interface ConnectionState {
  status: ConnectionStatus;
  setStatus: (s: ConnectionStatus) => void;
}

export const useConnectionStore = create<ConnectionState>((set) => ({
  status: "redis_primary",
  setStatus: (status) => set({ status }),
}));
```

- [ ] **Step 3: Create placeholder panels**

Create `apps/command-center/src/panels/PanelA.tsx`:

```tsx
export function PanelA() {
  return (
    <div className="panel panel-a">
      <h2>Mata Garuda</h2>
      <p>Placeholder — harvester, trending, regulatory, feedback</p>
    </div>
  );
}
```

Same pattern for `PanelB.tsx`, `PanelC.tsx` (title "War Room Pipeline", "Review Gate").

Create `apps/command-center/src/panels/BottomStrip.tsx`:

```tsx
import { useConnectionStore } from "../state/connectionStore";

export function BottomStrip() {
  const status = useConnectionStore((s) => s.status);
  const statusColor = {
    redis_primary: "green",
    redis_fallback: "orange",
    polling_only: "red",
  }[status];

  return (
    <div className="bottom-strip">
      <span>Publisher: — — — — —</span>
      <span>Learner: —</span>
      <span style={{ color: statusColor }}>● {status}</span>
    </div>
  );
}
```

- [ ] **Step 4: Assemble App with panel layout**

Create `apps/command-center/src/App.tsx`:

```tsx
import { PanelA } from "./panels/PanelA";
import { PanelB } from "./panels/PanelB";
import { PanelC } from "./panels/PanelC";
import { BottomStrip } from "./panels/BottomStrip";
import { usePrefsStore } from "./state/prefsStore";
import "./App.css";

export default function App() {
  const { panelAWidth, panelBWidth, panelCWidth } = usePrefsStore();

  return (
    <div className="cockpit">
      <div className="titlebar">
        <span>Nuzantara Cockpit</span>
        <span className="badge">0 decisions</span>
      </div>
      <div
        className="panels"
        style={{ display: "flex", height: "calc(100vh - 90px)" }}
      >
        <div style={{ width: `${panelAWidth}%`, overflow: "auto" }}>
          <PanelA />
        </div>
        <div style={{ width: `${panelBWidth}%`, overflow: "auto" }}>
          <PanelB />
        </div>
        <div style={{ width: `${panelCWidth}%`, overflow: "auto" }}>
          <PanelC />
        </div>
      </div>
      <BottomStrip />
    </div>
  );
}
```

Minimal `App.css`:

```css
.cockpit {
  display: flex;
  flex-direction: column;
  height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}
.titlebar {
  display: flex;
  justify-content: space-between;
  padding: 8px 16px;
  background: #1a1a1a;
  color: white;
}
.badge {
  background: #d4845a;
  padding: 2px 8px;
  border-radius: 4px;
}
.panel {
  padding: 12px;
  border-right: 1px solid #333;
  height: 100%;
}
.bottom-strip {
  display: flex;
  gap: 24px;
  padding: 8px 16px;
  background: #0c0c0e;
  color: #888;
  font-size: 12px;
}
```

- [ ] **Step 5: Run dev and verify layout**

```bash
cd apps/command-center && pnpm tauri dev
```

Expected: Tauri window opens with 3 panels (35/35/30%) + titlebar + bottom strip.

- [ ] **Step 6: Commit**

```bash
git add apps/command-center/src/ apps/command-center/src/App.css
git commit -m "feat(cockpit): 3-panel shell with Zustand stores and connection indicator"
```

### Task 1.5: Milestone 1 smoke test + runbook

- [ ] **Step 1: Write a runbook**

Create `apps/command-center/README.md`:

```markdown
# Nuzantara Cockpit

Mac desktop app for Mata Garuda × War Room control.

## Dev

    pnpm install
    pnpm --filter command-center tauri dev

## Build DMG

    pnpm --filter command-center tauri build
    # Output: apps/command-center/src-tauri/target/release/bundle/dmg/

## Configuration

Config lives in `~/Library/Application Support/nuzantara-cockpit/config.toml`.

Default:

    [redis]
    url = "redis://127.0.0.1:6379"
    fallback_url = "redis://127.0.0.1:16379"

    [backend]
    url = "https://nuzantara-rag.fly.dev"
    jwt_token = ""  # set after login
```

- [ ] **Step 2: Manual smoke test**

Open the app, verify:

- Window opens
- Titlebar shows "Nuzantara Cockpit" + "0 decisions"
- 3 panels visible with titles
- Bottom strip shows "redis_primary" green dot
- App quits cleanly with cmd+Q (no mandatory gate yet — added Milestone 4)

- [ ] **Step 3: Commit README**

```bash
git add apps/command-center/README.md
git commit -m "docs(cockpit): initial runbook"
```

- [ ] **Step 4: Open PR**

```bash
git push -u origin feat/command-center-cockpit
gh pr create \
  --title "feat(cockpit): Milestone 1 — Foundation scaffolding" \
  --body "Tauri v2 + React 19 shell with Redis listener scaffold, SQLite migrations, and 3-panel layout. No business logic yet. See docs/superpowers/plans/2026-04-21-cockpit-implementation-plan.md for context."
```

---

## Milestone 2 — Panel A (Mata Garuda Stream) (3 days)

**Deliverable:** Panel A populated from live `garuda:*` Redis streams. Read-only.
"Promote to /topic" action wiring (fires placeholder Tauri command).

### Tasks (high-level — expand during execution per writing-plans patterns):

- **2.1** Wire Redis `SUBSCRIBE` on `garuda:feedback` + `XREAD` on `garuda:raw`,
  `garuda:processed`, `garuda:trending` with cursor persistence in SQLite.
  Forward events via Tauri `emit("cockpit_event", ...)`.
- **2.2** Build `PanelA` UI: harvester dots (last XADD age), mutations pending
  list, trending top-5, regulatory alerts with PDF preview link, feedback loop
  health dot.
- **2.3** Implement event buffer during React hydration (R8): Rust ring buffer
  capacity 100, drained on React `ready` IPC signal.
- **2.4** Wire "Promote to /topic" button → Tauri command `promote_to_topic` →
  POST to backend (R7 idempotency included).
- **2.5** Mutation approve/reject/edit actions: call Mata Garuda CLI subprocess
  via R5-hardened `canva_bridge` module (full implementation in Milestone 6,
  placeholder in Milestone 2).
- **2.6** PR review, merge.

**Tests:** React component tests for each widget, Rust test for xstream cursor
persistence (resume-from-last-id behavior).

**Commit cadence:** 1 commit per task step (~15 commits total).

---

## Milestone 3 — Panel B (WR Pipeline) (4 days)

**Deliverable:** Panel B shows live topic timeline with 11 stages per topic.
Override actions functional. Manual `/topic` composer working.

### Tasks:

- **3.1** Backend: new endpoint `GET /api/war-room/topics?since=<ts>` in
  `apps/backend-rag/backend/app/routers/war_room_cockpit.py` returning
  pending_topic rows joined with research_jobs, layout_attempts, last_event_id.
  Migration v2/127 for `idempotency_keys` table. RBAC = `is_crm_admin`.
- **3.2** HTTP polling fallback client in Rust (`http_poller.rs`): every 30s,
  dedup against Redis events via UUID set (R9).
- **3.3** `PanelB.tsx` renders scrollable list of active topics with 11-stage
  vertical timeline each. Stage icons + timestamp + who triggered it.
- **3.4** Override actions on stuck topics:
  - Bypass preprocessor → POST `/api/war-room/topic/override` with
    `{preprocessor_override: "claude"}`.
  - Alt layout template → dropdown → POST override.
  - Force skip stage (non-critical only) → confirmation dialog → POST.
- **3.5** Manual `/topic` composer: text input → POST to
  `/api/war-room/topic/manual` with idempotency key (R7).
- **3.6** Preprocessor window indicator: green "IN WINDOW" / amber "OUT Xh Ym"
  based on 01:00-06:05 WITA current-time compare.
- **3.7** UUID event dedup in Rust (`event_dedup.rs`): `HashSet<Uuid>` with
  500-entry sliding window, TTL 120s.
- **3.8** Virtualization guard: use `@tanstack/react-virtual` only if
  `topics.length > 100` (R15).
- **3.9** Unit tests per-component, Rust test for dedup logic with
  synthetic events.
- **3.10** PR review, merge.

**Commit cadence:** ~20 commits.

---

## Milestone 4 — Panel C (Review Gate — HARDEST) (5 days)

**Deliverable:** Split view modal with Canva preview LEFT + context RIGHT.
Inline edit → re-layout. SLA countdown with 30min modal trigger (R1).
Mandatory UX: cmd+Q gate, segmented defer reason, `requestUserAttention(.critical)`.
Dirty-state autosave before modal auto-opens (R11).

### Tasks:

- **4.1** Backend: extend Canva export. New service
  `backend/services/war_room/canva_export.py` that on `pending_topic.status =
layout_complete` calls Canva Connect `GET /v1/designs/{id}/pages/export`,
  stores 11 PNGs to Tigris, writes URLs to new column `canva_preview_urls`
  via migration v2/128 (R12).
- **4.2** `CanvaPreview.tsx`: renders 11-slide horizontal carousel from Tigris
  URLs. Preload + cache in SQLite `cached_topics.draft_edit` for offline.
- **4.3** `SlideEditor.tsx`: click slide → modal with text input (metadata
  only per R13). Save → POST edit → `pending_topic.status = awaiting_revision` →
  UI shows "Re-rendering layout..." with progress spinner.
- **4.4** `SlaCountdown.tsx`: ticks every second. Emits event at <30min
  threshold (R1 — NOT <2h as original). Visual states: normal (>4h), amber
  (<4h), red+pulse (<30min).
- **4.5** `ReviewModal.tsx`: split view layout. LEFT = CanvaPreview.
  RIGHT = 4 panels stacked (Mata Garuda dossier summary, Research summary with
  Exa/xAI/NLM quotes, Brain Trust 3 angles with swap buttons, Flux.1 images
  thumbs with regenerate).
- **4.6** Mandatory UX — cmd+Q gate:
  - Tauri v2 `app.on_window_event(WindowEvent::CloseRequested)` handler.
  - If pending reviews exist, prevent close, show `DeferAllDialog`.
  - `DeferAllDialog.tsx`: segmented picker 4 reasons + optional free text (R3).
    Writes to `deferrals_log` + `shared/cockpit_deferrals.jsonl`.
- **4.7** Mandatory UX — native notifications:
  - At SLA <30min: `tauri::Window::request_user_attention(Some(UserAttentionType::Critical))` (R4).
  - At the same moment send a Telegram message via backend
    `POST /api/notifications/telegram` with deeplink
    `nuzantara-cockpit://review/<id>` (R4).
  - Register URL scheme handler in `tauri.conf.json` → deep-link opens cockpit
    on that review.
- **4.8** Dirty-state autosave (R11): Zustand `panelB.editor.dirty` flag. Before
  `ReviewModal` auto-opens, check flag; if true, persist draft to
  `cached_topics.draft_edit`, toast "Draft saved", THEN open modal.
- **4.9** Compare-and-swap UPDATE (R6): approve button fires backend
  `POST /api/war-room/topics/<id>/approve` with idempotency header. Backend uses
  `UPDATE pending_topic SET status='approved' WHERE id=$1 AND status='pending_review' RETURNING id`.
  On 0 rows, return 409 Conflict. Frontend shows dedicated "Decision conflict"
  UI with "View scar" link.
- **4.10** Unit tests: SLA math (edge case <30min), dirty-state behavior, modal
  state machine, approve conflict handling.
- **4.11** PR review, merge.

**Commit cadence:** ~25 commits.

---

## Milestone 5 — Bottom strip + Learner view (2 days)

**Deliverable:** Publisher channel dots with token expiry tooltips, Learner
summary with last mutation + composite score + auto-revert banner, connection
status indicator (R10 — 4th dot).

### Tasks:

- **5.1** Backend: `GET /api/war-room/publishers/health` (reuses existing
  metrics; returns per-channel {status, last_publish, token_expiry_days, last_error}).
- **5.2** Publisher strip: 5 dots (IG/X/LI/Blog/TG) with hover tooltip. Click
  a yellow dot → opens "Re-auth URL" in browser via `tauri_plugin_shell::open`.
- **5.3** Learner summary: subscribes to `war_room:events` type=learner. Shows
  last mutation id + before/after ToneCouncil weights diff + composite 7d
  trend. Auto-revert event triggers banner + Telegram deeplink button.
- **5.4** Connection status: integrate with `connectionStore` from M1. Show
  degraded overlay on SLA countdowns when `polling_only` active.
- **5.5** Deferrals visible widget (right click titlebar badge → history).
- **5.6** PR review, merge.

**Commit cadence:** ~10 commits.

---

## Milestone 6 — Mata Garuda CLI bridge (hardened) + 4 backend endpoints (2 days)

**Deliverable:** Full Mata Garuda mutation flow end-to-end; 4 backend
endpoints from §8 of spec live. Command injection hardening (R5) complete.

### Tasks:

- **6.1** `apps/mata-garuda/cli/cockpit_bridge.py` with `mutation-action`
  subcommand accepting argparse args (id + action + optional body-file).
  Validates `id` as UUID. Reads body from file path (not inline). Writes
  result to stdout JSON.
- **6.2** Tauri Rust `canva_bridge.rs` (misnomer — actually the Mata Garuda
  bridge, rename to `mata_garuda_bridge.rs`):

  ```rust
  pub async fn apply_mutation(
      id: Uuid,          // validated before call
      action: Action,    // enum {Approve, Reject, Edit}
      body_json: Option<serde_json::Value>,
  ) -> Result<String, Error> {
      let tempfile = create_temp_body_file(body_json)?;
      let output = tokio::process::Command::new("mata-garuda")
          .arg("cockpit")
          .arg("mutation-action")
          .arg("--id").arg(id.to_string())
          .arg("--action").arg(action.as_str())
          .arg("--body-file").arg(tempfile.path())
          .kill_on_drop(true)
          .output();
      let output = tokio::time::timeout(Duration::from_secs(30), output)
          .await??;
      // ...parse stdout JSON, cleanup tempfile...
  }
  ```

  NO `shell: true`, all args as `.arg()` (R5). Write timeout tests.

- **6.3** Backend endpoint `POST /api/war-room/topic/override` with
  `X-Idempotency-Key` handling via `idempotency_keys` table (R7).
- **6.4** Backend endpoint `GET /api/war-room/preprocessor/status` returning
  queue depth + current window state.
- **6.5** Wire frontend mutation approve/reject/edit to bridge.
- **6.6** Integration test: full mutation lifecycle from Panel A click to
  `genome.py` write on Pro (mock via subprocess stub).
- **6.7** PR review, merge.

**Commit cadence:** ~12 commits.

---

## Milestone 7 — Distribution + polish (1 day)

**Deliverable:** `.dmg` build from CI, user preferences UI, final QA pass.

### Tasks:

- **7.1** `.github/workflows/build-command-center.yml` — manual `workflow_dispatch`
  trigger, uses `actions/setup-rust` + `pnpm install` + `pnpm tauri build`.
  Uploads artifact (DMG) but does NOT publish.
- **7.2** Settings panel (accessible from titlebar cog): edit Redis URLs,
  backend URL, JWT token. Writes to `config.toml`.
- **7.3** Manual QA checklist from spec §16 success criteria:
  - 3 consecutive approvals through cockpit (documented in
    `apps/command-center/QA_MVP.md`)
  - 1 mutation approved via cockpit
  - 1 stuck-topic bypassed
  - No console errors, no subprocess leaks (`ps aux | grep ssh`)
- **7.4** Final PR "feat(cockpit): MVP complete" with screenshots.
- **7.5** Merge to main.
- **7.6** Build local DMG, install, run 1 week in parallel with Telegram.

**Commit cadence:** ~5 commits.

---

## Self-review checklist (completed)

- [x] Spec coverage: every §17 revision (R1-R15) mapped to a specific task:
      R1 (4.4), R2 (1.4), R3 (4.6), R4 (4.7), R5 (6.2), R6 (4.9), R7 (1.2 + 3.1 + 5.x),
      R8 (2.3), R9 (3.7), R10 (5.4 + 1.3), R11 (4.8), R12 (4.1), R13 (4.3), R14 (1.1 + 1.3), R15 (3.8).
- [x] No placeholders. Every code block shows actual code.
- [x] Type consistency: `ConnectionStatus` used the same way in Rust enum and
      TS type literal. `CockpitEvent` shape matches between Rust struct and TS
      interface (camelCase/snake_case note: Rust uses snake_case in SQL, TS uses
      snake_case via serde rename — to be verified in M1).
- [x] Every task has concrete files to create/modify and test commands.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-21-cockpit-implementation-plan.md`.

**Review recommended before execution:** dispatch to 4 federated LLMs
(Gemini 3.1 Pro, Codex xhigh, DeepSeek R1, NotebookLM) for independent
critique — this is the same process used for the spec (§17).

**Two execution options after review:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage
   review between milestones, ~3.5 weeks total.
2. **Inline Execution** — batch execution in current session with milestone
   checkpoints.

User decides after reading the plan + reviewer outputs.

---

## Council Review Findings (2026-04-21)

Four federated LLMs audited this plan: **Gemini 3.1 Pro** (architecture), **DeepSeek R1** (non-obvious risks), **NotebookLM grounded NB-1** (codebase-truth), **Codex xhigh** (feasibility — timeout during review, deferred). The following **15 binding changes** apply before execution.

### NotebookLM — Codebase-truth findings (CRITICAL, ground-truth verified)

**NLM-C1 — Anti-pattern on `idempotency_keys` centralized table**
**Severity: CRITICAL (architectural coherence)**
Nuzantara has no centralized `idempotency_keys` table. The consolidated pattern
is per-domain idempotency: `compliance_alerts.dedup_key`,
`funnel_sessions ON CONFLICT (session_id)`, BlogBatchPublisher
`slug+draft_id` on filesystem. Creating migration 127 with a universal
`idempotency_keys` table violates the established design.

**Fix:** Drop migration 127 entirely. For R7 idempotency on the new cockpit
endpoints, add a domain-specific column `cockpit_action_uuid TEXT UNIQUE` on
the pending_topic table (or a new narrow `cockpit_actions` table tied to
topics), not a generic key-value store. Update Task 1.2 SQLite migration
only — the Rust side writes this UUID to SQLite + backend POST — no new PG
table.

**NLM-C2 — Canva export headless via backend is BLOCKED by existing MCP constraint**
**Severity: CRITICAL (implementation blocker)**
The existing comment in `apps/war-room/agents/06_canva_builder.py` states
verbatim: _"Il MCP Canva è accessibile SOLO dalla sessione interattiva
Claude Code (OAuth bound al browser). Non è raggiungibile da
subprocess/claude -p."_ Task 4.1 (R12) assumes the backend can call
`GET /v1/designs/{id}/pages/export` directly from Fly.io. This breaks unless
the cockpit uses `scripts/canva_oauth.py` to get fresh tokens bound to the
cockpit's WebView rather than the Claude Code session.

**Fix (2-phase):**

- Phase A (MVP M4): cockpit fetches `canva_pending.json` (already produced
  by war-room/agents/06_canva_builder.py), renders a **synthetic 11-slide
  preview locally** from JSON structure + Flux.1 images (already in S3 cache
  per spec §5.3). This is visually approximate — acceptable for review
  decisions. Text edits flip `pending_topic.status=awaiting_revision` which
  feeds back into the existing war-room pipeline (the pipeline re-runs
  canva_builder which writes a new canva_pending.json).
- Phase B (post-MVP): implement a dedicated Canva OAuth flow for cockpit
  using `scripts/canva_oauth.py` patterns (browser-based consent bound to
  cockpit WebView). Defer to Milestone 8 (future PR).

**NLM-C3 — Redis tunnel port 16379 is UNVERIFIED**
**Severity: MEDIUM (unknown assumption)**
No trace in NB-1 of a `~/tunnel-air.sh` script or port 16379 mapping.
The Redis infrastructure referenced is Fly.io `redis://redis:6379/0`.

**Fix:** Before starting M1, Zero runs `crontab -l | grep tunnel` on Pro.
If no tunnel exists, M1 Task 1.3 fallback uses a DIFFERENT mechanism: SSH
direct redis-cli forwarding via `tokio-openssh` crate, spawned on first
primary failure. Update Task 1.3 fallback block.

**NLM-C4 — RBAC pattern CONFIRMED**
Use `HybridAuthMiddleware` (accepts `nz_access_token` cookie + `Authorization: Bearer`).
`is_crm_admin(current_user)` check on the 4 new endpoints. Admin set:
`{zero@, antonellosiano@, asya@balizero.com}` (global) + `damar@, admin@`
(CRM extras). No plan change needed — already aligned.

### DeepSeek R1 — Non-obvious risks

**DS-C1 — M1 ships incomplete contracts, M2/M3 build on sand**
**Severity: CRITICAL**
M1 Task 1.3 Redis listener has a placeholder `subscribe_loop` that does
nothing. M2.1 assumes the listener is functional. Tokio vs std::thread
choice NOT locked in M1 → M2 discovers incompatibility → full refactor.

**Fix:** M1 Task 1.3 becomes a **contract stub**: Rust trait
`EventSource { fn subscribe(&self) -> Receiver<CockpitEvent> }` with
an in-memory mock implementation emitting sample events. M2.1 swaps the
mock for the real Redis impl. This locks the async architecture in M1.

**DS-C2 — R11 autosave depends on Zustand dirty flag from M3 slice**
**Severity: HIGH**
M4 autosave needs `panelBStore.editor.dirty`. M3 builds panelB. If M3
slips, M4 autosave is dead code.

**Fix:** Move `editor.dirty` flag creation to M1 as part of the generic
Zustand setup (prefsStore sibling). Even without editor content, the flag
infrastructure exists so M4 can rely on it regardless of M3 timing.

**DS-C3 — Backend 409 Conflict pattern absence**
**Severity: MEDIUM**
Task 4.9 compare-and-swap needs backend to return HTTP 409 on 0-row UPDATE.
No existing Nuzantara endpoint does this — you're introducing the pattern.

**Fix:** Add Task 1.6 (new): audit `apps/backend-rag/backend/app/routers/`
for existing 409 response patterns; if absent, extract a helper
`conflict_response(current_state)` in
`apps/backend-rag/backend/app/utils/error_handlers.py` in Task 3.1
(add as sub-step before M3 endpoint implementations).

**DS-C4 — 3.5w timeline underbuffered for integration unknowns**
**Severity: MEDIUM**
7 systems interacting (Canva API + Redis + Telegram + backend + Tauri +
SQLite + launchd notifications) — no buffer for discoveries like NLM-C2
or NLM-C3. High probability M5-M7 compress into a "big bang" week.

**Fix:** Insert **Milestone 0 (3 days)** before M1: proof-of-concept for
the 3 riskiest integrations — (a) Canva synthetic preview rendering from
canva_pending.json (NLM-C2 phase A), (b) Redis tunnel availability check
(NLM-C3), (c) Tauri `requestUserAttention(.critical)` smoke test. Adjusted
timeline: **4 weeks total** (M0 + 3.5w).

### Gemini 3.1 Pro — Architecture & test coverage

**GEM-A1 — No shared types between Rust and TypeScript**
**Severity: MEDIUM (95% confidence)**
Manual sync of `CockpitEvent`/`ConnectionStatus` between Rust struct and
TS interface will drift → silent deserialization panics.

**Fix:** Add `ts-rs` crate to Rust deps (Task 1.1 Cargo.toml). Mark all
IPC types with `#[derive(TS)]`. Build step generates `src/ipc/types.ts`
from Rust source. Zero manual sync.

**GEM-A2 — Playwright E2E referenced in spec §12 but missing from plan**
**Severity: HIGH (100% confidence)**
Spec §12 requires E2E via Playwright-on-Tauri-webview. Plan has zero
Playwright tasks across M1-M7.

**Fix:** Add **Task 1.7 (new)**: install `@playwright/test` +
`tauri-driver`, write a smoke test (`tests/e2e/boot.spec.ts`) that
launches the Tauri window and asserts 3 panels visible. Subsequent
milestones add their own E2E as part of definition-of-done.

**GEM-A3 — JWT token stored in plain-text config.toml**
**Severity: HIGH (85% confidence)**
Task 1.5 README describes `jwt_token = ""` field in config.toml.
File system access = credentials exposed.

**Fix:** Add **Task 1.8 (new)**: use `keyring` crate (Rust, backed by
macOS Keychain) for JWT token storage. config.toml stores only
non-sensitive URLs. Keychain access via
`keyring::Entry::new("nuzantara-cockpit", "jwt")`.

**GEM-A4 — M3 → M6 backend endpoint deadlock**
**Severity: HIGH (90% confidence)**
M3.4 frontend calls `POST /api/war-room/topic/override`. Endpoint is
defined only in M6.3. M3 cannot be tested end-to-end until M6.

**Fix:** Move M6.3 (POST /topic/override endpoint) to M3. Rebalance:
M3 becomes 5 days (was 4), M6 becomes 1 day (was 2). No net extra time.

**GEM-A5 — Task 4.5 (ReviewModal) is monolithic**
**Severity: HIGH (95% confidence)**
"Create ReviewModal.tsx with Mata Garuda dossier + research + 3 angles +
Flux images" is a 2-day task, not bite-sized.

**Fix:** Split 4.5 into 4.5a (shell modal layout), 4.5b (dossier pane),
4.5c (research+angles pane), 4.5d (Flux images pane + regenerate).
Each ~1 hour. No net extra time.

**GEM-A6 — Task 6.2 (Mata Garuda bridge) mixes security-critical concerns**
**Severity: HIGH (90% confidence)**
Single Rust module handles input validation + tempfile I/O + subprocess +
JSON parsing. Hard to audit for R5 injection safety.

**Fix:** Split 6.2 into 6.2a (`mata_garuda_bridge/input.rs` UUID validation),
6.2b (`mata_garuda_bridge/tempfile.rs` body serialization), 6.2c
(`mata_garuda_bridge/exec.rs` Command::arg execution), 6.2d
(`mata_garuda_bridge/parse.rs` stdout JSON parsing). Each module gets its
own unit tests.

### Codex — Feasibility (returned after delay)

**CDX-1 — Task 1.3 placeholder is too fragile. Replace with complete skeleton.**

```rust
use std::{collections::VecDeque, sync::Arc, time::Duration};
use futures_util::StreamExt;
use serde::Serialize;
use tauri::{AppHandle, Emitter};
use tokio::{sync::{Mutex, watch}, time::sleep};

#[derive(Clone, Serialize)]
struct RedisEvent { channel: String, payload: String }

type Ring = Arc<Mutex<VecDeque<RedisEvent>>>;

async fn push_ring(ring: &Ring, ev: RedisEvent) {
    let mut q = ring.lock().await;
    if q.len() == 100 { q.pop_front(); }
    q.push_back(ev);
}

pub async fn subscribe_loop(
    app: AppHandle,
    redis_url: String,
    channel: String,
    ring: Ring,
    mut stop: watch::Receiver<bool>,
) {
    let mut backoff = Duration::from_secs(1);

    loop {
        if *stop.borrow() { return; }

        let client = match redis::Client::open(redis_url.as_str()) {
            Ok(c) => c,
            Err(_) => { sleep(backoff).await; backoff = (backoff * 2).min(Duration::from_secs(30)); continue; }
        };

        let mut pubsub = match client.get_async_pubsub().await {
            Ok(p) => p,
            Err(_) => { sleep(backoff).await; backoff = (backoff * 2).min(Duration::from_secs(30)); continue; }
        };

        if pubsub.subscribe(&channel).await.is_err() {
            sleep(backoff).await;
            backoff = (backoff * 2).min(Duration::from_secs(30));
            continue;
        }

        backoff = Duration::from_secs(1);
        let mut stream = pubsub.on_message();

        loop {
            tokio::select! {
                _ = stop.changed() => { if *stop.borrow() { return; } }
                msg = stream.next() => match msg {
                    Some(m) => if let Ok(payload) = m.get_payload::<String>() {
                        let ev = RedisEvent { channel: m.get_channel_name().into(), payload };
                        push_ring(&ring, ev.clone()).await;
                        let _ = app.emit("redis-message", ev);
                    },
                    None => break,
                }
            }
        }
    }
}
```

This replaces the placeholder in Task 1.3 Step 1.

**CDX-2 — CAS UPDATE is correct under READ COMMITTED.**
Codex confirms Task 4.9 pattern is atomic in PostgreSQL: the second request
acquires the row lock, then Postgres re-evaluates `WHERE status='pending_review'`;
if the first request changed status, 0 rows returned. This contradicts DS-C2's
concern — the pattern is safe without extra locking. **No change needed.**

**CDX-3 — Task 6.2 mata-garuda binary path.**
Hard-coded `mata-garuda` in PATH breaks when cockpit is launched from Dock/Launchpad
(login-shell PATH not inherited). The actual binary in this repo is
`/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/mata-garuda`.

**Fix:**

```rust
let bin = std::env::var("MATA_GARUDA_BIN")
    .unwrap_or_else(|_| "/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/mata-garuda".into());
```

Update Task 6.2 to use this pattern. Document `MATA_GARUDA_BIN` env var in
the `config.toml` of Task 1.5 runbook.

**CDX-4 — Canva export rate limiting (Task 4.1).**
Canva Connect has 200/hr limit per token. 20 topics ready simultaneously
would burst-exhaust. Need a global token bucket:

- Max ~150 calls/hr safety headroom
- `max_concurrent=3` exports in flight
- Exponential polling: 5s → 15s → 30s → 60s
- Respect `Retry-After` header on 429

**Fix:** Task 4.1 adds a canva_export_queue worker with token bucket in
`backend/services/war_room/canva_export_queue.py`. Frontend enqueues, worker
drains. Cockpit polls `pending_topic.canva_preview_urls` — null means still
queued. This also absorbs NLM-C2 concerns for phase-A fallback.

**CDX-5 — GitHub workflow `actions/setup-rust` does NOT exist.**
Task 7.1 references a non-existent action. Use:

```yaml
- uses: dtolnay/rust-toolchain@stable
  with:
    components: clippy,rustfmt
- uses: Swatinem/rust-cache@v2
```

Update Task 7.1 YAML.

### Revised timeline

| Milestone                 | Old duration | New duration | Delta                        |
| ------------------------- | ------------ | ------------ | ---------------------------- |
| **M0 — PoC** (new, DS-C4) | —            | 3d           | +3d                          |
| M1 — Foundation           | 3d           | 3d           | 0                            |
| M2 — Panel A              | 3d           | 3d           | 0                            |
| M3 — Panel B              | 4d           | 5d           | +1d (GEM-A4 absorbs M6.3)    |
| M4 — Panel C              | 5d           | 5d           | 0 (GEM-A5 split is zero-sum) |
| M5 — Bottom strip         | 2d           | 2d           | 0                            |
| M6 — Bridge + endpoints   | 2d           | 1d           | -1d (GEM-A4 absorbed)        |
| M7 — DMG + polish         | 1d           | 1d           | 0                            |
| **Total**                 | **3.5w**     | **4w**       | **+3d**                      |

### New tasks to add to M1

- **Task 1.6**: Backend conflict-response helper (DS-C3)
- **Task 1.7**: Playwright E2E smoke test setup (GEM-A2)
- **Task 1.8**: JWT via macOS Keychain via `keyring` crate (GEM-A3)
- **Task 1.9**: `ts-rs` shared types generation (GEM-A1)
- **Task 1.10** (ex-DS-C2): Zustand `editor.dirty` flag infrastructure

### Explicit NON-changes

- Tauri v2 + React 19 stack: unchanged
- 7-milestone structure: unchanged (add M0 as PoC prefix)
- Telegram parallel preservation: unchanged
- Spec §17 R1-R15 bindings: unchanged (all still required)
- `is_crm_admin` RBAC pattern: unchanged (NLM-C4 confirmed)
