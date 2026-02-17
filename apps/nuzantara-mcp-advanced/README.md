# Nuzantara Advanced MCP Server

Advanced MCP (Model Context Protocol) server for Nuzantara operations, deployment, and diagnostics.

## Overview

This MCP server complements the main [Nuzantara MCP Server](../nuzantara-mcp/) with advanced operational capabilities for developers and operators.

## Installation

```bash
cd apps/nuzantara-mcp-advanced
pip install -e .
```

## Tools Provided

### Deployment Tools

- `check_fly_status()` - Check Fly.io application status
- `get_fly_logs(lines, filter_str)` - Retrieve application logs
- `check_deployment_readiness()` - Run pre-deployment checks

### Testing Tools

- `run_backend_tests(test_path, verbose)` - Run pytest with options
- `run_type_checking()` - Run mypy type checking
- `run_linting()` - Run ruff linting and formatting

### System Diagnostics

- `check_system_health()` - Comprehensive health check
- `get_collection_stats()` - Qdrant collection statistics
- `search_codebase(query, file_pattern)` - Search codebase

### Documentation Tools

- `find_documentation(topic)` - Find relevant docs
- `get_file_structure(path)` - Get directory tree

## Usage

### With Claude Code

Add to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "nuzantara-advanced": {
      "command": "nuzantara-mcp-advanced",
      "env": {
        "NUZANTARA_BACKEND_URL": "https://nuzantara-rag.fly.dev",
        "FLY_APP": "nuzantara-rag",
        "NUZANTARA_ROOT": "/Users/nuzantara/Desktop/nuzantara"
      }
    }
  }
}
```

### Environment Variables

| Variable                | Description       | Default                              |
| ----------------------- | ----------------- | ------------------------------------ |
| `NUZANTARA_BACKEND_URL` | Backend URL       | `https://nuzantara-rag.fly.dev`      |
| `FLY_APP`               | Fly.io app name   | `nuzantara-rag`                      |
| `NUZANTARA_ROOT`        | Project root path | `/Users/nuzantara/Desktop/nuzantara` |

## Prompts

### Deployment Checklist

Use the `deployment_checklist` prompt to verify readiness before deploying:

```
@mcp.prompt("deployment_checklist")
```

### Debug KG Issues

Use the `debug_kg_issue` prompt for Knowledge Graph troubleshooting:

```
@mcp.prompt("debug_kg_issue")
```

### Investigate Test Failures

Use the `investigate_test_failure` prompt when tests fail:

```
@mcp.prompt("investigate_test_failure")
```

## Requirements

- Python 3.11+
- flyctl (for Fly.io operations)
- Access to Nuzantara project directory

## License

MIT
