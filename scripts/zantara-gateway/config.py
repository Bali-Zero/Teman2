# scripts/zantara-gateway/config.py
"""
Gateway configuration loader.

Reads ~/.zantara-gateway/config.json. Falls back to sane defaults.
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("zantara-gateway.config")

CONFIG_DIR = Path.home() / ".zantara-gateway"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class GatewayConfig:
    port: int = 8090
    role: str = "visa_specialist"
    agent_name: str = "Team Member"
    gateway_token: str = ""
    # Gemini CLI
    gemini_timeout: int = 60
    gemini_allowed_mcp: list[str] = field(default_factory=lambda: ["nuzantara"])
    # Gemini API direct (bypasses CLI for zero cold start)
    gemini_api_key: str = ""
    gemini_api_model: str = "gemini-2.5-flash"
    # Ollama fallback
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = ""  # auto-detected from RAM
    ollama_max_tool_iterations: int = 3
    ollama_tool_fail_threshold: int = 2
    # CORS
    allowed_origins: list[str] = field(
        default_factory=lambda: ["https://kita.balizero.com"]
    )
    # TLS
    tls_cert: str = str(CONFIG_DIR / "cert.pem")
    tls_key: str = str(CONFIG_DIR / "key.pem")

    def has_tls(self) -> bool:
        return os.path.isfile(self.tls_cert) and os.path.isfile(self.tls_key)


def _detect_ollama_model() -> str:
    """Pick Gemma 4 variant based on system RAM."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=5,
        )
        ram_gb = int(result.stdout.strip()) / (1024**3)
        if ram_gb >= 14:
            return "gemma4:e4b"
        return "gemma4:e2b"
    except Exception:
        return "gemma4:e2b"


def load_config() -> GatewayConfig:
    """Load config from JSON file, merge with defaults."""
    cfg = GatewayConfig()

    if CONFIG_FILE.is_file():
        try:
            raw = json.loads(CONFIG_FILE.read_text())
            cfg.port = raw.get("port", cfg.port)
            cfg.role = raw.get("role", cfg.role)
            cfg.agent_name = raw.get("agent_name", cfg.agent_name)
            cfg.gateway_token = raw.get("gateway_token", cfg.gateway_token)

            gemini = raw.get("gemini_cli", {})
            cfg.gemini_timeout = gemini.get("timeout_seconds", cfg.gemini_timeout)
            cfg.gemini_allowed_mcp = gemini.get(
                "allowed_mcp_servers", cfg.gemini_allowed_mcp
            )

            gemini_api = raw.get("gemini_api", {})
            cfg.gemini_api_key = gemini_api.get("api_key", cfg.gemini_api_key)
            cfg.gemini_api_model = gemini_api.get("model", cfg.gemini_api_model)

            ollama = raw.get("ollama", {})
            cfg.ollama_url = ollama.get("url", cfg.ollama_url)
            cfg.ollama_model = ollama.get("model", "")
            cfg.ollama_max_tool_iterations = ollama.get(
                "max_tool_iterations", cfg.ollama_max_tool_iterations
            )
            cfg.ollama_tool_fail_threshold = ollama.get(
                "tool_fail_threshold", cfg.ollama_tool_fail_threshold
            )

            cors = raw.get("cors", {})
            cfg.allowed_origins = cors.get("allowed_origins", cfg.allowed_origins)

            tls = raw.get("tls", {})
            cfg.tls_cert = tls.get("cert", cfg.tls_cert)
            cfg.tls_key = tls.get("key", cfg.tls_key)

            logger.info("Config loaded from %s", CONFIG_FILE)
        except Exception as e:
            logger.warning("Failed to parse config: %s — using defaults", e)

    # Auto-detect Ollama model if not set
    if not cfg.ollama_model:
        cfg.ollama_model = _detect_ollama_model()

    if not cfg.gateway_token:
        logger.warning("No gateway_token set — auth disabled")

    return cfg
