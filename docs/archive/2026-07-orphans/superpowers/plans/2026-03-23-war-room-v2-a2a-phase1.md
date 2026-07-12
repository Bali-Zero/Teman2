# War Room v2 A2A Migration — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register 7 war-room agents as A2A services in the federation system so they can be discovered and invoked individually via the A2A protocol.

**Architecture:** Each war-room Python script (00-09) is wrapped as a CLI command in `a2a_service.py`'s `AGENT_CLI_COMMANDS` dict. An Agent Card JSON is created for discovery. The launcher and discovery modules are updated with port allocations. No changes to existing war-room agents or pipeline.sh.

**Tech Stack:** Python 3.11, A2A SDK 0.3.25, FastAPI (via a2a_service.py), existing war-room scripts unchanged.

---

## File Structure

**New files to create (7 agent cards):**

- `apps/federation/agents/war-room-topic/agent_card.json`
- `apps/federation/agents/war-room-researcher/agent_card.json`
- `apps/federation/agents/war-room-strategist/agent_card.json`
- `apps/federation/agents/war-room-director/agent_card.json`
- `apps/federation/agents/war-room-image-gen/agent_card.json`
- `apps/federation/agents/war-room-canva/agent_card.json`
- `apps/federation/agents/war-room-delivery/agent_card.json`

**Existing files to modify (3 files, additive only):**

- `apps/federation/a2a_service.py` — add 7 entries to `AGENT_CLI_COMMANDS` dict after line 108
- `apps/federation/launcher.py` — add 7 entries to `AGENT_PORTS` dict after line 31
- `apps/federation/discovery.py` — add 7 entries to `AGENT_REGISTRY` dict after line 141

**Test file to create:**

- `apps/federation/tests/test_war_room_agents.py`

---

### Task 1: Create Agent Cards (7 JSON files)

**Files:**

- Create: `apps/federation/agents/war-room-topic/agent_card.json`
- Create: `apps/federation/agents/war-room-researcher/agent_card.json`
- Create: `apps/federation/agents/war-room-strategist/agent_card.json`
- Create: `apps/federation/agents/war-room-director/agent_card.json`
- Create: `apps/federation/agents/war-room-image-gen/agent_card.json`
- Create: `apps/federation/agents/war-room-canva/agent_card.json`
- Create: `apps/federation/agents/war-room-delivery/agent_card.json`

Each card follows the exact schema from `apps/federation/agents/gemini-search/agent_card.json`.

- [ ] **Step 1: Create war-room-topic agent card**

```json
{
  "name": "War Room Topic Selector",
  "description": "Selects optimal carousel topic from intel scraper output + Google Trends",
  "url": "http://localhost:8100/",
  "version": "1.0.0",
  "protocol_version": "0.3.0",
  "provider": {
    "organization": "Nuzantara Federation",
    "url": "https://kita.balizero.com"
  },
  "capabilities": {
    "streaming": false,
    "push_notifications": false,
    "state_transition_history": true
  },
  "default_input_modes": ["text/plain"],
  "default_output_modes": ["application/json"],
  "skills": [
    {
      "id": "topic-selection",
      "name": "Topic Selection",
      "description": "Analyzes intel scraper output to pick optimal Instagram carousel topic for Bali Zero. Pass a topic hint as prompt to override auto-selection.",
      "tags": ["topic", "intel", "carousel", "content-strategy", "war-room"],
      "examples": [
        "Select best topic from today's intel",
        "What should we post about this week"
      ]
    }
  ],
  "extensions": [
    {
      "uri": "urn:nuzantara:dispatch",
      "description": "CLI dispatch: war-room topic selector",
      "params": {
        "dispatch_cmd": "war-room-topic",
        "cost": "$0 (Gemini CLI + Qwen local)",
        "limits": "requires intel_output_latest.json"
      }
    }
  ]
}
```

Write to `apps/federation/agents/war-room-topic/agent_card.json`.

- [ ] **Step 2: Create war-room-researcher agent card**

```json
{
  "name": "War Room Researcher",
  "description": "Deep research via ChatGPT + Exa in parallel, merged and preprocessed by Qwen",
  "url": "http://localhost:8100/",
  "version": "1.0.0",
  "protocol_version": "0.3.0",
  "provider": {
    "organization": "Nuzantara Federation",
    "url": "https://kita.balizero.com"
  },
  "capabilities": {
    "streaming": false,
    "push_notifications": false,
    "state_transition_history": true
  },
  "default_input_modes": ["text/plain"],
  "default_output_modes": ["application/json"],
  "skills": [
    {
      "id": "content-research",
      "name": "Content Research",
      "description": "Parallel deep research using ChatGPT broad search + Exa deep scrape, merged and preprocessed by Qwen 3.5",
      "tags": ["research", "chatgpt", "exa", "qwen", "war-room", "content"],
      "examples": [
        "Research KBLI 2025 villa impact",
        "Find data on Coretax enforcement"
      ]
    }
  ],
  "extensions": [
    {
      "uri": "urn:nuzantara:dispatch",
      "params": {
        "dispatch_cmd": "war-room-researcher",
        "cost": "~$0.10 (ChatGPT + Exa API)",
        "limits": "timeout 600s"
      }
    }
  ]
}
```

Write to `apps/federation/agents/war-room-researcher/agent_card.json`.

- [ ] **Step 3: Create remaining 5 agent cards**

Create these 5 cards following the same schema. Key differences per agent:

**war-room-strategist** (port 8102): `"description": "Content strategy via Gemini — generates 3 narrative concepts"`, skill id `content-strategy`, tags include `gemini`, `strategy`, `narrative`. Extensions: `dispatch_cmd: "war-room-strategist"`, cost `"$0 (Gemini CLI)"`.

**war-room-director** (port 8103): `"description": "Creative director — writes slide copy, image prompts, Instagram caption via Gemini"`, skill id `slide-direction`, tags include `copywriting`, `slides`, `instagram`, `director`. Extensions: `dispatch_cmd: "war-room-director"`, cost `"$0 (Gemini CLI)"`.

**war-room-image-gen** (port 8104): `"description": "Image generation via Gemini Flash Image Preview (Chrome CDP)"`, skill id `image-generation`, tags include `gemini`, `image`, `chrome-cdp`. Extensions: `dispatch_cmd: "war-room-image-gen"`, limits `"requires Chrome debug mode on Pro"`.

**war-room-canva** (port 8105): `"description": "Canva carousel builder — converts slides JSON into canva_pending.json operations"`, skill id `canva-builder`, tags include `canva`, `carousel`, `design`. Extensions: `dispatch_cmd: "war-room-canva"`, limits `"output is canva_pending.json, NOT actual Canva API calls"`.

**war-room-delivery** (port 8106): `"description": "Delivery agent — uploads to Google Drive and sends Telegram notification"`, skill id `delivery`, tags include `drive`, `telegram`, `publish`. Extensions: `dispatch_cmd: "war-room-delivery"`, cost `"$0"`.

Write each to `apps/federation/agents/war-room-{name}/agent_card.json`.

- [ ] **Step 4: Verify all 7 card directories exist**

Run: `ls -la apps/federation/agents/war-room-*/agent_card.json`
Expected: 7 files listed.

- [ ] **Step 5: Validate JSON syntax of all cards**

Run: `for f in apps/federation/agents/war-room-*/agent_card.json; do python3 -c "import json; json.load(open('$f')); print('OK:', '$f')" || echo "FAIL: $f"; done`
Expected: 7 "OK" lines.

- [ ] **Step 6: Commit**

```bash
git add apps/federation/agents/war-room-*/agent_card.json
git commit -m "feat(federation): add 7 war-room A2A agent cards"
```

---

### Task 2: Register CLI commands in a2a_service.py

**Files:**

- Modify: `apps/federation/a2a_service.py:108` — add 7 entries after `"air-batch"` entry

- [ ] **Step 1: Add war-room CLI commands to AGENT_CLI_COMMANDS**

Add after line 108 (after `"air-batch"` closing brace), before the closing `}` of the dict:

```python
    # ═══════════════════════════════════════════════════════
    # War Room agents (ports 8100-8106, Pro only)
    # Ports start at 8100 to avoid conflict with air-batch (8101)
    # ═══════════════════════════════════════════════════════
    "war-room-topic": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/00_topic_selector.py "
            "--intel $HOME/Desktop/nuzantara/apps/bali-intel-scraper/data/intel_output_latest.json "
            "--hint \"{prompt}\" "
            "--output output/strategy/selected_topic.json 2>&1 && "
            "cat output/strategy/selected_topic.json",
        ],
        "timeout": 240,
        "stream": False,
    },
    "war-room-researcher": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/01_chatgpt_researcher.py --topic \"{prompt}\" "
            "--output output/raw/chatgpt_dump.json 2>&1 & "
            "python agents/09_exa_researcher.py --topic \"{prompt}\" "
            "--output output/raw/exa_dump.json 2>&1 & "
            "wait && "
            "python -c '"
            "import json; from pathlib import Path; "
            "sources = [Path(\"output/raw/chatgpt_dump.json\"), Path(\"output/raw/exa_dump.json\")]; "
            "merged = {\"facts\": [], \"merged\": True}; "
            "[merged[\"facts\"].extend(json.loads(s.read_text()).get(\"facts\",[])) for s in sources if s.exists()]; "
            "Path(\"output/raw/merged_dump.json\").write_text(json.dumps(merged))' && "
            "python agents/015_qwen_preprocessor.py "
            "--research output/raw/merged_dump.json "
            "--output output/raw/processed_dump.json 2>&1 && "
            "cat output/raw/processed_dump.json",
        ],
        "timeout": 600,
        "stream": False,
    },
    "war-room-strategist": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/03_gemini_strategist.py "
            "--dump output/raw/processed_dump.json "
            "--topic \"{prompt}\" "
            "--output output/strategy/gemini_concepts.json 2>&1 && "
            "cat output/strategy/gemini_concepts.json",
        ],
        "timeout": 600,
        "stream": False,
    },
    "war-room-director": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/04_claude_director.py "
            "--concepts output/strategy/gemini_concepts.json "
            "--topic \"{prompt}\" "
            "--output output/strategy/claude_slides.json 2>&1 && "
            "cat output/strategy/claude_slides.json",
        ],
        "timeout": 600,
        "stream": False,
    },
    "war-room-image-gen": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/05_gemini_images.py "
            "--slides output/strategy/claude_slides.json "
            "--output output/images/ "
            "--cdp http://localhost:9222 2>&1 && "
            "cat output/images/manifest.json",
        ],
        "timeout": 300,
        "stream": False,
    },
    "war-room-canva": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "source .venv/bin/activate 2>/dev/null; "
            "python agents/06_canva_builder.py "
            "--slides output/strategy/claude_slides.json "
            "--output output/canva/ "
            "--master output/master/ "
            "--design-id DAHEME4mocU "
            "--row all --page 1 2>&1 && "
            "cat output/canva/canva_pending.json",
        ],
        "timeout": 120,
        "stream": False,
    },
    "war-room-delivery": {
        "cmd_template": [
            "bash", "-c",
            "cd /Users/nuzantara/Desktop/nuzantara/apps/war-room && "
            "bash agents/07_delivery.sh --topic \"{prompt}\" 2>&1",
        ],
        "timeout": 120,
        "stream": False,
    },
```

- [ ] **Step 2: Verify syntax**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -c "from apps.federation.a2a_service import AGENT_CLI_COMMANDS; print(f'{len(AGENT_CLI_COMMANDS)} agents registered'); [print(f'  {k}') for k in AGENT_CLI_COMMANDS if k.startswith('war-room')]"`
Expected: `16 agents registered` followed by 7 `war-room-*` lines.

- [ ] **Step 3: Commit**

```bash
git add apps/federation/a2a_service.py
git commit -m "feat(federation): register 7 war-room CLI commands in A2A service"
```

---

### Task 3: Register ports in launcher.py

**Files:**

- Modify: `apps/federation/launcher.py:22-31` — add 7 entries to `AGENT_PORTS`

- [ ] **Step 1: Add war-room ports to AGENT_PORTS**

Add after line 30 (`"gws": 8088,`), before the comment about claude-code:

```python
    # War Room agents (Pro only)
    "war-room-topic": 8100,
    "war-room-researcher": 8101,
    "war-room-strategist": 8102,
    "war-room-director": 8103,
    "war-room-image-gen": 8104,
    "war-room-canva": 8105,
    "war-room-delivery": 8106,
```

- [ ] **Step 2: Verify**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -c "from apps.federation.launcher import AGENT_PORTS; print(f'{len(AGENT_PORTS)} ports'); [print(f'  {k}: {v}') for k,v in AGENT_PORTS.items() if k.startswith('war-room')]"`
Expected: `14 ports` followed by 7 war-room entries (8100-8106).

- [ ] **Step 3: Verify listing works**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -m apps.federation.launcher --list`
Expected: All 14 agents listed with their ports, including 7 war-room agents.

- [ ] **Step 4: Commit**

```bash
git add apps/federation/launcher.py
git commit -m "feat(federation): add war-room agent ports 8100-8106 to launcher"
```

---

### Task 4: Register in discovery.py

**Files:**

- Modify: `apps/federation/discovery.py:129-141` — add 7 entries to `AGENT_REGISTRY`

- [ ] **Step 1: Add war-room agents to AGENT_REGISTRY**

Add after line 140 (`"air-batch": ...`), before the closing `}`:

```python
    # War Room agents (Pro only)
    "war-room-topic": {"host": "localhost", "port": 8100, "machine": "pro"},
    "war-room-researcher": {"host": "localhost", "port": 8101, "machine": "pro"},
    "war-room-strategist": {"host": "localhost", "port": 8102, "machine": "pro"},
    "war-room-director": {"host": "localhost", "port": 8103, "machine": "pro"},
    "war-room-image-gen": {"host": "localhost", "port": 8104, "machine": "pro"},
    "war-room-canva": {"host": "localhost", "port": 8105, "machine": "pro"},
    "war-room-delivery": {"host": "localhost", "port": 8106, "machine": "pro"},
```

- [ ] **Step 2: Verify**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -c "from apps.federation.discovery import AGENT_REGISTRY; print(f'{len(AGENT_REGISTRY)} agents in registry'); [print(f'  {k}: port {v[\"port\"]}') for k,v in AGENT_REGISTRY.items() if k.startswith('war-room')]"`
Expected: `16 agents in registry` followed by 7 war-room entries.

- [ ] **Step 3: Commit**

```bash
git add apps/federation/discovery.py
git commit -m "feat(federation): register war-room agents in discovery registry"
```

---

### Task 5: Smoke test — start one agent and verify A2A endpoint

**Files:**

- No new files — testing existing code with new config

- [ ] **Step 1: Start war-room-canva agent (simplest, no external deps)**

Run in a separate terminal:

```bash
cd /Users/nuzantara/Desktop/nuzantara
python3 -m apps.federation.a2a_service --agent war-room-canva --port 8105
```

Expected: uvicorn starts, logs show `Serving war-room-canva on port 8105`.

- [ ] **Step 2: Verify Agent Card endpoint**

Run:

```bash
curl -s http://localhost:8105/.well-known/agent.json | python3 -m json.tool | head -20
```

Expected: JSON with `"name": "War Room Canva Builder"`, `"url": "http://localhost:8105/"`.

- [ ] **Step 3: Verify discovery finds the agent**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara
python3 -c "
import asyncio
from apps.federation.discovery import check_agent_health
result = asyncio.run(check_agent_health('war-room-canva'))
print(result)
"
```

Expected: `{'agent_id': 'war-room-canva', 'status': 'healthy', ...}`.

- [ ] **Step 4: Stop the test agent (Ctrl+C in the terminal)**

- [ ] **Step 5: Done — manual verification complete, move to Task 6**

---

### Task 6: Write automated tests

**Files:**

- Create: `apps/federation/tests/__init__.py`
- Create: `apps/federation/tests/test_war_room_agents.py`

- [ ] **Step 0: Create tests directory with **init**.py**

Run: `mkdir -p apps/federation/tests && touch apps/federation/tests/__init__.py`

- [ ] **Step 1: Write test file**

> Note: Tests import from `apps.federation.*` — requires `PYTHONPATH=.` (monorepo root).

```python
"""Tests for War Room A2A agent registration.

Verifies that all 7 war-room agents are correctly registered
in a2a_service.py, launcher.py, and discovery.py with matching
agent cards on disk.
"""

import json
from pathlib import Path

import pytest

WAR_ROOM_AGENTS = [
    "war-room-topic",
    "war-room-researcher",
    "war-room-strategist",
    "war-room-director",
    "war-room-image-gen",
    "war-room-canva",
    "war-room-delivery",
]

EXPECTED_PORTS = {
    "war-room-topic": 8100,
    "war-room-researcher": 8101,
    "war-room-strategist": 8102,
    "war-room-director": 8103,
    "war-room-image-gen": 8104,
    "war-room-canva": 8105,
    "war-room-delivery": 8106,
}

FEDERATION_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = FEDERATION_ROOT / "agents"


class TestWarRoomAgentCards:
    """Verify agent cards exist and have valid structure."""

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_agent_card_exists(self, agent_id: str) -> None:
        card_path = AGENTS_DIR / agent_id / "agent_card.json"
        assert card_path.exists(), f"Missing agent card: {card_path}"

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_agent_card_valid_json(self, agent_id: str) -> None:
        card_path = AGENTS_DIR / agent_id / "agent_card.json"
        card = json.loads(card_path.read_text())
        assert "name" in card
        assert "url" in card
        assert "skills" in card
        assert len(card["skills"]) > 0
        assert card["protocol_version"] == "0.3.0"

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_agent_card_port_matches(self, agent_id: str) -> None:
        card_path = AGENTS_DIR / agent_id / "agent_card.json"
        card = json.loads(card_path.read_text())
        expected_port = EXPECTED_PORTS[agent_id]
        assert f":{expected_port}/" in card["url"], (
            f"Card URL {card['url']} doesn't contain port {expected_port}"
        )


class TestWarRoomCLICommands:
    """Verify CLI commands are registered in a2a_service.py."""

    def test_all_agents_in_cli_commands(self) -> None:
        from apps.federation.a2a_service import AGENT_CLI_COMMANDS

        for agent_id in WAR_ROOM_AGENTS:
            assert agent_id in AGENT_CLI_COMMANDS, (
                f"{agent_id} not in AGENT_CLI_COMMANDS"
            )

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_cli_command_has_required_keys(self, agent_id: str) -> None:
        from apps.federation.a2a_service import AGENT_CLI_COMMANDS

        cmd = AGENT_CLI_COMMANDS[agent_id]
        assert "cmd_template" in cmd
        assert "timeout" in cmd
        assert cmd["timeout"] > 0


class TestWarRoomLauncher:
    """Verify ports are registered in launcher.py."""

    def test_all_agents_in_launcher(self) -> None:
        from apps.federation.launcher import AGENT_PORTS

        for agent_id in WAR_ROOM_AGENTS:
            assert agent_id in AGENT_PORTS, f"{agent_id} not in AGENT_PORTS"

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_port_matches_expected(self, agent_id: str) -> None:
        from apps.federation.launcher import AGENT_PORTS

        assert AGENT_PORTS[agent_id] == EXPECTED_PORTS[agent_id]


class TestWarRoomDiscovery:
    """Verify agents are registered in discovery.py."""

    def test_all_agents_in_registry(self) -> None:
        from apps.federation.discovery import AGENT_REGISTRY

        for agent_id in WAR_ROOM_AGENTS:
            assert agent_id in AGENT_REGISTRY, (
                f"{agent_id} not in AGENT_REGISTRY"
            )

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_agent_on_pro_machine(self, agent_id: str) -> None:
        from apps.federation.discovery import AGENT_REGISTRY

        assert AGENT_REGISTRY[agent_id]["machine"] == "pro"

    @pytest.mark.parametrize("agent_id", WAR_ROOM_AGENTS)
    def test_port_consistent_across_modules(self, agent_id: str) -> None:
        from apps.federation.discovery import AGENT_REGISTRY
        from apps.federation.launcher import AGENT_PORTS

        assert AGENT_REGISTRY[agent_id]["port"] == AGENT_PORTS[agent_id], (
            f"Port mismatch for {agent_id}: "
            f"discovery={AGENT_REGISTRY[agent_id]['port']}, "
            f"launcher={AGENT_PORTS[agent_id]}"
        )
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/nuzantara/Desktop/nuzantara && PYTHONPATH=. pytest apps/federation/tests/test_war_room_agents.py -v`
Expected: All tests pass (~52 parametrized tests across 4 test classes).

- [ ] **Step 3: Commit**

```bash
git add apps/federation/tests/test_war_room_agents.py
git commit -m "test(federation): add comprehensive tests for war-room A2A agent registration"
```

---

### Task 7: Final integration commit

- [ ] **Step 1: Run full discovery to verify**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -m apps.federation.discovery`
Expected: Shows 16 agents total. War-room agents show as ⚫ offline (services not running), which is correct — they'll be started when needed.

- [ ] **Step 2: Final commit with summary**

```bash
git add -A
git commit -m "feat(federation): War Room v2 A2A Phase 1 complete — 7 agents registered

- 7 Agent Cards in apps/federation/agents/war-room-*/
- CLI commands registered in a2a_service.py (ports 8100-8106, no conflict with air-batch 8091)
- Ports registered in launcher.py
- Discovery registry updated in discovery.py
- ~52 tests passing
- No changes to existing pipeline.sh or war-room agents

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```
