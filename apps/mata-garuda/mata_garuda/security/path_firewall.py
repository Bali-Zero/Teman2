"""
Mata Garuda — Path Firewall.

Vincolo OSINT blindato: il meta-agent può creare agenti SOLO sotto
mata_garuda/agents/. Qualsiasi tentativo di scrivere altrove è bloccato.

Nomi agente che contengono keyword proibite (frontend, client, team, etc.)
sono rifiutati a priori.
"""
from __future__ import annotations

import re
from pathlib import Path

# Unica directory dove il meta-agent può creare file agente
AGENTS_DIR = Path(__file__).parent.parent / "agents"

# Nomi vietati — se il nome agente matcha una di queste keyword, rifiuta
FORBIDDEN_NAME_PATTERNS = re.compile(
    r"(frontend|client|team|channel|api|cloud|deploy|vercel|fly|"
    r"auth|password|credential|secret|token|env|ssh|key)",
    re.IGNORECASE,
)

# Estensioni ammesse per i file creati dal meta-agent
ALLOWED_EXTENSIONS = {".py", ".md"}


class PathFirewallError(Exception):
    """Raised when a path operation violates the firewall."""


def validate_agent_name(name: str) -> None:
    """
    Validate agent name against forbidden patterns.

    Raises:
        PathFirewallError: if name contains forbidden keywords
    """
    if not name or not name.strip():
        raise PathFirewallError("Agent name cannot be empty")

    # Check forbidden patterns
    match = FORBIDDEN_NAME_PATTERNS.search(name)
    if match:
        raise PathFirewallError(
            f"Agent name '{name}' contains forbidden keyword: '{match.group()}'. "
            f"OSINT blindato: agents must not reference {match.group()}."
        )

    # Sanitize: only alphanumeric, underscore, space, dash
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_ -]*$", name):
        raise PathFirewallError(
            f"Agent name '{name}' contains invalid characters. "
            f"Use only letters, digits, underscores, spaces, dashes."
        )


def validate_write_path(target_path: str | Path) -> Path:
    """
    Validate that target_path is inside AGENTS_DIR.

    Args:
        target_path: path where the meta-agent wants to write

    Returns:
        Resolved absolute path (safe to write to)

    Raises:
        PathFirewallError: if path is outside AGENTS_DIR
    """
    resolved = Path(target_path).resolve()
    agents_resolved = AGENTS_DIR.resolve()

    if not str(resolved).startswith(str(agents_resolved)):
        raise PathFirewallError(
            f"Write blocked: {resolved} is outside {agents_resolved}. "
            f"Meta-agent can ONLY write under mata_garuda/agents/."
        )

    # Check extension
    if resolved.suffix and resolved.suffix not in ALLOWED_EXTENSIONS:
        raise PathFirewallError(
            f"Write blocked: extension '{resolved.suffix}' not allowed. "
            f"Allowed: {ALLOWED_EXTENSIONS}"
        )

    return resolved


def validate_agent_creation(agent_name: str) -> Path:
    """
    Full validation for creating a new agent: name + path.

    Returns:
        Path where the agent .py file should be written
    """
    validate_agent_name(agent_name)

    safe_name = agent_name.lower().replace(" ", "_").replace("-", "_")
    target = AGENTS_DIR / f"{safe_name}.py"
    return validate_write_path(target)
