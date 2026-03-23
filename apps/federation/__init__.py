"""Nuzantara Federation — ADK + A2A multi-agent orchestration.

Modules:
  orchestrator.py   — v3 pipeline (async functions, backward compat)
  adk_agents.py     — ADK native agents (ClassifierAgent, DispatcherAgent, etc.)
  a2a_service.py    — FastAPI wrapper for CLI agents as A2A services
  discovery.py      — Cross-machine agent registry and health checks
  launcher.py       — Start all A2A services with heartbeat monitoring
  workflows.py      — Pre-defined multi-agent pipelines
  mcp_bridge.py     — ADK McpToolset integration for 224 MCP tools
  tracing.py        — OpenTelemetry tracing with LangSmith export
  setup_air.sh      — Air machine deployment script
"""
