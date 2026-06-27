# KBLI Navigator Native App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`).

**Goal:** Native macOS SwiftUI app to browse KBLI 2025 codes (search → editorial detail with Bali-moratorium status), read the book/articles (media), and chat with a KBLI-grounded Zantara (GPT-5.5 via OpenClaw), running native on M5+Pro+Mini.

**Architecture:** Standalone repo `~/Desktop/kbli-navigator-app` (like `wr2-control-app`), compiled with `build.sh` (swiftc + Xcode-beta macro plugin) → `.app`. 3 isolated units (KBLIStore / MediaLibrary / OpenClawRunner) wired by a thin KBLI-specific `AppState`. Data bundled in `Resources/` (offline). Chat = single OpenClaw brain on Mini, reached locally on Mini or via `ssh mini` from M5/Pro.

**Tech Stack:** SwiftUI, AppKit, PDFKit, Foundation (AttributedString) — Apple-native only, NO Swift Package Manager. zsh `build.sh`. OpenClaw CLI (`agent --json`) as chat backend.

## Global Constraints

- **NO Swift Package Manager** — only Apple frameworks + single-file vendored Swift (build.sh swiftc constraint).
- **Target:** `arm64-apple-macosx26.0`. Xcode-beta at `~/Downloads/Xcode-beta.app` (M5) or `/Applications/Xcode.app` (Pro).
- **No Anthropic SDK / no paid API.** Chat = OpenClaw (GPT-5.5 via MAX-sanctioned codex auth on Mini). Strip `ANTHROPIC_API_KEY` from child env (defense-in-depth, like ClaudeRunner).
- **Dataset:** `KBLI_2025_FINAL_CLEAN.json` v10.0-L2-oss-risk (1559 records) from `.worktrees/intel-kbli-rag-source-align/apps/mouth/data/`. Fields: `kode_kbli_2025`, `judul`, `uraian`, `ruang_lingkup`, `per_skala[]`, `pma_status`, `l4_bali{status,reason,blocked,moratorium{...}}`.
- **Content source:** `~/Desktop/KBLI-2025-Content/` (20 articles, 13 book-chapters, 2 PDFs EN/ID).
- **PII:** none (public codes). All grounding/retrieval local.
- **After each Task:** severe 4-LLM/Codex review of the diff + run tests. Operator gate stays with parent (verify on disk in-turn).
- **Markdown renderer (F3 decision):** vendored block renderer handling `#/##/###`, `- `/`* ` bullets (1 level nesting), `> ` blockquote, `**bold**`/`*italic*`/`[link](url)` inline via per-line `AttributedString(markdown:)`, paragraph spacing, fenced ``` code. Target the article corpus shape, not full GFM (no tables — articles use them sparsely; render raw `|` rows monospaced as fallback, logged).

---

### Task 0: Repo scaffold + build.sh + empty app launches

**Files:**
- Create: `~/Desktop/kbli-navigator-app/build.sh` (adapt from wr2-control-app)
- Create: `~/Desktop/kbli-navigator-app/Info.plist`
- Create: `~/Desktop/kbli-navigator-app/Sources/KBLINavigatorApp.swift`
- Create: `~/Desktop/kbli-navigator-app/Sources/Theme.swift` (copy from WR2)
- Create: `~/Desktop/kbli-navigator-app/.gitignore` (`build/`)

**Interfaces:**
- Produces: a buildable `.app` skeleton; `Theme` enum (colors/fonts) reused by all views.

- [ ] **Step 1:** `git init` repo, copy `Theme.swift` verbatim from `~/Desktop/wr2-control-app/Sources/Theme.swift`, copy+adapt `build.sh` (rename APP_NAME="KBLI Navigator", EXEC="KBLINavigator"), copy `Info.plist` (bundle id `com.balizero.kbli-navigator`).
- [ ] **Step 2:** Write minimal `KBLINavigatorApp.swift`: `@main struct App` with `WindowGroup` showing `Text("KBLI Navigator")`.
- [ ] **Step 3:** Run `./build.sh` → expect exit 0, `build/KBLI Navigator.app` created.
- [ ] **Step 4:** `open "build/KBLI Navigator.app"` → window appears with the text.
- [ ] **Step 5:** Commit `chore: scaffold kbli-navigator app skeleton + build.sh`.

---

### Task 1: Models + KBLIStore (load 1559, search ranking)

**Files:**
- Create: `Sources/Models.swift` — `KBLI`, `PerSkala`, `L4Bali`, `Moratorium` (Codable, map JSON keys)
- Create: `Sources/KBLIStore.swift` — `final class KBLIStore: ObservableObject`, loads bundled JSON, `func search(_ q: String) -> [KBLI]` (ranked), `func code(_ k: String) -> KBLI?`
- Create: `Tests/storetest/main.swift` — standalone executable test
- Resource: copy `KBLI_2025_FINAL_CLEAN.json` into `Resources/`

**Interfaces:**
- Produces: `KBLI { kode: String, judul: String, uraian: String, ruangLingkup: String?, perSkala: [PerSkala], pmaStatus: String?, l4Bali: L4Bali? }`; `L4Bali { status: String, reason: String?, blocked: Bool, moratorium: Moratorium? }`; `KBLIStore.search(q) -> [KBLI]` ranked exact-code>prefix-code>judul-prefix>substring; `KBLIStore.code(k) -> KBLI?`.

- [ ] **Step 1:** Write `Tests/storetest/main.swift`: load JSON from `Resources/`, assert `store.all.count == 1559`, `store.code("55203")?.l4Bali?.status == "CHIUSO_PMA_NO_BESAR"`, `store.code("55203")?.l4Bali?.blocked == true`, `store.search("55203").first?.kode == "55203"`, `store.search("villa").contains{$0.kode=="55203"}`.
- [ ] **Step 2:** Run test → FAIL (no Models/KBLIStore).
- [ ] **Step 3:** Write `Models.swift` (CodingKeys mapping `kode_kbli_2025`→`kode` etc.) + `KBLIStore.swift` (decode `data` array, `rank()` per research snippet, search sorted by rank then code).
- [ ] **Step 4:** Run test → PASS (all asserts).
- [ ] **Step 5:** Commit `feat: KBLI models + store with ranked search (1559 codes)`.

---

### Task 2: NavigationSplitView shell + AppState (surgical fork) + search list

**Files:**
- Create: `Sources/AppState.swift` — slim KBLI `ObservableObject` (selectedKBLI, query, chat state) — NO WarRoom/QueueWriter
- Create: `Sources/Localization.swift` — copy LanguageManager from WR2, replace keys with KBLI ones (IT/EN/ID)
- Create: `Sources/Views/RootView.swift` — `NavigationSplitView` 3-col (sidebar Section enum / search list / detail)
- Create: `Sources/Views/SearchListView.swift` — `.searchable` + `List` of results with status badge
- Modify: `KBLINavigatorApp.swift` — wire AppState + RootView

**Interfaces:**
- Consumes: `KBLIStore.search`, `KBLI`.
- Produces: `enum Section { search, media, chat }`; `AppState { @Published query, @Published selected: KBLI?, store: KBLIStore }`; `statusColor(_ status:String)->Color` + `statusSymbol(_:)->String` helpers.

- [ ] **Step 1:** Write `Tests/uitest/main.swift` (logic-only): assert `statusColor("OK_or_HIGHER_RISK")==Theme.green`, `statusColor("BLOCCATO_CLASSE_RISCHIO")==Theme.red`, `statusSymbol("NEEDS_REVIEW_NO_OSS_SCOPE")=="questionmark.circle"`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `AppState`, `Section`, status helpers, `RootView` (NavigationSplitView), `SearchListView` (.searchable bound to AppState.query, List of `store.search(query)` rows: badge + kode mono + judul, selection → AppState.selected).
- [ ] **Step 4:** Run helper test → PASS. Build → exit 0. `open` → sidebar + search bar; typing "55203" shows the row.
- [ ] **Step 5:** Commit `feat: 3-col NavigationSplitView shell + searchable code list`.

---

### Task 3: KBLIDetailView (editorial card + moratorium callout)

**Files:**
- Create: `Sources/Views/KBLIDetailView.swift`

**Interfaces:**
- Consumes: `KBLI`, `L4Bali`, status helpers.
- Produces: detail view rendering header(badge+kode+judul+pma) / moratorium callout (if `l4Bali.blocked`) / uraian+scope / per-skala GroupBoxes / "Ask Zantara" toolbar button → `AppState.openChat(forCode:)`.

- [ ] **Step 1:** Write logic test in uitest: `KBLIDetailView.shouldShowMoratorium(l4)` true when `blocked==true`, false otherwise; `moratoriumText(l4)` contains "2026-05-13" for 55203.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `KBLIDetailView`: `ScrollView` of `GroupBox` sections on material (no dividers), amber callout for moratorium, per-skala cards, `.toolbar` primaryAction "Ask Zantara".
- [ ] **Step 4:** Test PASS; build+open, select 55203 → red badge + amber moratorium callout w/ 13/5/26.
- [ ] **Step 5:** Commit `feat: KBLI detail card with Bali-moratorium callout`.

---

### Task 4: MediaLibrary + MarkdownView + PDFViewer

**Files:**
- Create: `Sources/MediaLibrary.swift` — enumerate articles/chapters/pdf from Resources
- Create: `Sources/MarkdownView.swift` — vendored block renderer (per Global Constraints)
- Create: `Sources/Views/MediaView.swift` — list + markdown detail + PDF tab (PDFKit NSViewRepresentable, bg-thread load)
- Resource: copy 20 articles + 13 chapters + 2 PDFs into `Resources/`
- Test: `Tests/mediatest/main.swift`

**Interfaces:**
- Consumes: bundled Resources.
- Produces: `MediaLibrary { articles:[MediaItem], chapters:[MediaItem], books:[PDFItem] }`; `MarkdownView(text:)` rendering blocks; `PDFViewer(url:)`.

- [ ] **Step 1:** mediatest: assert `library.articles.count==20`, `library.chapters.count==13`, both PDFs exist; `Markdown.blocks("## H2\n- a\n- b")` yields 1 heading + 2 bullets.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement MediaLibrary (FileManager enumerate), MarkdownView (line-based block parser + per-line AttributedString inline), MediaView (List + PDFViewer with `Task.detached` load + `document=nil` onDisappear).
- [ ] **Step 4:** Test PASS; build+open Media → an article shows H2+bullets (not flat), book PDF opens + EN/ID switch.
- [ ] **Step 5:** Commit `feat: media library — markdown articles + native PDF book viewer`.

---

### Task 5: FASE 0 — arm OpenClaw on Mini (gateway + zantara-kbli agent)

**Files (on Mini, via ssh):**
- Fix `~/.openclaw/openclaw.json` (remove 3 invalid keys / make env optional)
- Create agent `zantara-kbli` (system-prompt: KBLI 2025 + Bali moratorium, grounded, GPT-5.5)
- Create: `~/Desktop/kbli-navigator-app/deploy/arm-openclaw-mini.sh` (idempotent, documents the steps)
- LaunchAgent for gateway H24 (or document `--local` fallback)

**Interfaces:**
- Produces: working `~/.openclaw/bin/openclaw agent --agent zantara-kbli --message <q> --json` → JSON with `result.finalAssistantVisibleText`.

- [ ] **Step 1:** `ssh mini` validate current `openclaw config validate` errors; back up `openclaw.json` (chmod 0600).
- [ ] **Step 2:** Fix config (drop `openai-codex.models.0.contextTokens`, fix `telegram.streaming`, make OPENROUTER/DEEPSEEK keys optional); create `zantara-kbli` agent.
- [ ] **Step 3:** Start gateway (LaunchAgent) OR confirm `--local` works with codex auth.
- [ ] **Step 4:** Test: `ssh mini '~/.openclaw/bin/openclaw agent --agent zantara-kbli --message "Cos'\''è il KBLI 55203?" --json'` → exit 0, JSON parses, `finalAssistantVisibleText` non-empty + mentions villa/55203. **Acceptance #6.**
- [ ] **Step 5:** Commit `feat(deploy): arm OpenClaw zantara-kbli agent on Mini`.

---

### Task 6: OpenClawRunner (dual-mode) + grounding + ChatView fork

**Files:**
- Create: `Sources/OpenClawRunner.swift` — dual-mode (local on Mini / `ssh mini` from M5/Pro), parse JSON `finalAssistantVisibleText`
- Create: `Sources/Grounding.swift` — local retrieval → "FONTI" block from KBLIStore + articles
- Create: `Sources/Views/ChatView.swift` — fork of WR2 ChatView, wired to AppState (no WarRoom)
- Test: `Tests/runnertest/main.swift`

**Interfaces:**
- Consumes: `KBLIStore` (grounding), `AppState`.
- Produces: `OpenClawRunner.ask(prompt:, sources:, onReply:, onError:)`; `Grounding.sources(for query:, code:) -> String`; `OpenClawRunner.hostMode -> .local | .ssh`.

- [ ] **Step 1:** runnertest: `OpenClawRunner.parseReply(mockJSON)` extracts `finalAssistantVisibleText`; `OpenClawRunner.commandArgs(host:"Air-M5")` starts with `ssh`; `commandArgs(host:"Mini-Pro2")` is local; `Grounding.sources(code:"55203")` contains "55203" + "CHIUSO_PMA_NO_BESAR".
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement OpenClawRunner (Process zsh -lc, dual-mode arg build, strip ANTHROPIC_API_KEY, JSON parse, gateway-down fallback), Grounding (retrieval), ChatView fork (AppState-bound, inject sources, "Ask Zantara from code" entry).
- [ ] **Step 4:** Test PASS. Build+open on M5 → Chat "cos'è il 55203?" → reply via ssh mini citing real Bali status; stop gateway → clean "chat unavailable", no hang. **Acceptance #7, #10.**
- [ ] **Step 5:** Commit `feat: OpenClaw dual-mode chat runner + KBLI grounding + chat UI`.

---

### Task 7: 3-Mac deploy + Gatekeeper fix (F2) + final QA

**Files:**
- Create: `deploy/install-3mac.sh` — build once, rsync to M5+Pro+Mini, `xattr -cr` + `codesign --force --sign -` on each
- Create: `PROVENANCE.md` — WR2 reuse + dataset provenance + research + panel
- Create: `README.md`

**Interfaces:** none (deploy + docs).

- [ ] **Step 1:** Write `install-3mac.sh`: build on current host, then for each target `rsync -a --delete "$APP" "$T":'~/Applications/'` + `ssh "$T" 'xattr -cr ~/Applications/"KBLI Navigator.app"; codesign --force --deep --sign - ~/Applications/"KBLI Navigator.app"'`.
- [ ] **Step 2:** Run deploy to Mini first → `ssh mini 'open ~/Applications/"KBLI Navigator.app"'` → launches WITHOUT "damaged" (verifies F2). **Acceptance #9.**
- [ ] **Step 3:** Deploy to Pro + M5; spot-check launch on each.
- [ ] **Step 4:** Full acceptance run §8.1-§8.10; write PROVENANCE.md + README.
- [ ] **Step 5:** Commit `feat(deploy): 3-Mac install + Gatekeeper re-sign + docs`.

---

## Self-Review

**Spec coverage:** §2 arch→T0-T2; §3 search→T1-T3; §4 media→T4; §5 chat+grounding→T5-T6; §2 3-Mac→T7; §9 F1→T6, F2→T7, F3→T4, S2→T2. All covered.
**Placeholder scan:** none — every task has concrete asserts + commands.
**Type consistency:** `KBLI.kode`/`l4Bali`/`status` consistent T1→T3→T6; `OpenClawRunner.parseReply`/`commandArgs`/`hostMode` consistent T6.
