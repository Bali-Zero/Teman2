"""
Generate A2A Agent Cards from federation_capability_table.py.

Single source of truth: AGENTS + CAPABILITY_DOMAINS → agent_card.json files.
Run: python apps/federation/generate_agent_cards.py
"""

import json
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.federation_capability_table import AGENTS, CAPABILITY_DOMAINS
from apps.federation.discovery import AGENT_REGISTRY

# Derived from the single source of truth in discovery.py
AGENT_PORTS = {aid: r["port"] for aid, r in AGENT_REGISTRY.items()}
AGENT_HOST = {aid: r["host"] for aid, r in AGENT_REGISTRY.items()}

# Streaming capability per agent
AGENT_STREAMING = {
    "claude-code": True,     # Opus streams
    "gemini-search": True,   # Gemini streams
    "gemini-explore": True,  # Gemini streams
    "codex-sandbox": False,  # Codex returns complete results
    "claude-review": True,   # Claude streams
    "aider": False,          # Aider returns diffs
    "notebooklm": False,     # NLM returns complete answers
    "gws": False,            # GWS returns structured data
}


def build_skills_for_agent(agent_id: str) -> list[dict]:
    """Extract skills from CAPABILITY_DOMAINS where best_agent matches."""
    skills = []
    for domain_id, domain in CAPABILITY_DOMAINS.items():
        if domain["best_agent"] != agent_id:
            continue

        # Build example prompts from keywords
        examples = []
        keywords = domain.get("keywords", [])
        if len(keywords) >= 2:
            examples.append(f"Help me with {keywords[0]}")
            examples.append(f"I need information about {keywords[1]}")
        elif keywords:
            examples.append(f"Help me with {keywords[0]}")

        skill = {
            "id": domain_id,
            "name": domain_id.replace("-", " ").replace("_", " ").title(),
            "description": domain["description"],
            "tags": keywords[:10],  # A2A spec: keyword tags
            "examples": examples,
        }

        # Add input/output modes if domain has specific needs
        if domain_id in ("browser", "document-ocr", "media-generation"):
            skill["input_modes"] = ["text/plain", "image/*"]
        if domain_id in ("media-generation",):
            skill["output_modes"] = ["text/plain", "image/png", "video/mp4"]

        skills.append(skill)

    return skills


def build_agent_card(agent_id: str) -> dict:
    """Build a complete A2A AgentCard for one agent."""
    agent = AGENTS[agent_id]
    port = AGENT_PORTS[agent_id]
    host = AGENT_HOST[agent_id]
    streams = AGENT_STREAMING[agent_id]

    skills = build_skills_for_agent(agent_id)

    # If agent has no domains as best_agent, create a meta-skill from strengths
    if not skills:
        skills.append({
            "id": f"{agent_id}-core",
            "name": agent["name"],
            "description": agent["role"],
            "tags": agent["strengths"][:5],
            "examples": [f"Use {agent['name']} for {s}" for s in agent["strengths"][:2]],
        })

    card = {
        "name": agent["name"],
        "description": agent["role"],
        "url": f"http://{host}:{port}/",
        "version": "1.0.0",
        "protocol_version": "0.3.0",
        "provider": {
            "organization": "Nuzantara Federation",
            "url": "https://kita.balizero.com",
        },
        "capabilities": {
            "streaming": streams,
            "push_notifications": False,
            "state_transition_history": True,
        },
        "default_input_modes": ["text/plain"],
        "default_output_modes": ["text/plain"],
        "skills": skills,
    }

    # Add dispatch command as extension metadata
    if agent.get("dispatch_cmd"):
        card["extensions"] = [{
            "uri": "urn:nuzantara:dispatch",
            "description": f"CLI dispatch command: {agent['dispatch_cmd']}",
            "params": {
                "dispatch_cmd": agent["dispatch_cmd"],
                "cost": agent.get("cost", "unknown"),
                "limits": agent.get("limits", ""),
            },
        }]

    return card


def main() -> None:
    output_dir = Path(__file__).parent / "agents"

    generated = []
    for agent_id in AGENTS:
        card = build_agent_card(agent_id)
        agent_dir = output_dir / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        card_path = agent_dir / "agent_card.json"
        with open(card_path, "w") as f:
            json.dump(card, f, indent=2, ensure_ascii=False)

        skill_count = len(card["skills"])
        generated.append(f"  ✅ {agent_id}: {skill_count} skills → {card_path.relative_to(output_dir.parent)}")

    print(f"Generated {len(generated)} Agent Cards:\n")
    print("\n".join(generated))

    # Also generate a discovery index
    index = {}
    for agent_id in AGENTS:
        port = AGENT_PORTS[agent_id]
        host = AGENT_HOST[agent_id]
        index[agent_id] = {
            "url": f"http://{host}:{port}/",
            "card_path": f"agents/{agent_id}/agent_card.json",
        }

    index_path = output_dir.parent / "discovery_index.json"
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    print(f"\n  📋 Discovery index → {index_path.relative_to(output_dir.parent.parent)}")


if __name__ == "__main__":
    main()
