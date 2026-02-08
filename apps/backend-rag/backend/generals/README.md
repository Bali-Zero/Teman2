# The Generals Multi-Agent System

A distributed task execution system where specialized "Generals" handle different types of tasks:
- **Coding General**: Executes code-related tasks (shell commands, Python scripts, code execution)
- **Intelligence General**: Performs research and analysis using Gemini 3 Pro
- **Antigravity General**: System orchestrator for multi-tool coordination and IDE automation
- **Task Coordinator**: Provides high-level API for ZANTARA to submit tasks and monitor execution

## Architecture

The system uses PostgreSQL tables for coordination:
- `generals_tasks`: Task queue with status tracking
- `generals_memory`: Shared memory between generals (key-value store with expiration)
- `generals_activity`: Activity log for monitoring and debugging

## Database Schema

The schema is defined in `schema.sql` and includes:
- Task queue with priority, status tracking, and result storage
- Shared memory with expiration support
- Activity logging for all operations

## Components

### CodingGeneral (`coding_general.py`)

Polls `generals_tasks` for tasks with `task_type='code'` and executes them.

**Features:**
- Polls database for pending code tasks
- Executes shell commands, Python scripts, or Python code strings
- Updates task status and results
- Logs all activities

**Usage:**
```python
from backend.generals import CodingGeneral

general = CodingGeneral(poll_interval=5)
await general.initialize()

# Run polling loop (blocking)
await general.run_loop()

# Or poll manually
task = await general.poll_task()
if task:
    result = await general.execute_task(task)
```

### IntelligenceGeneral (`intelligence_general.py`)

Polls `generals_tasks` for tasks with `task_type='research'` and uses Gemini 3 Pro for analysis.

**Features:**
- Polls database for pending research tasks
- Uses Gemini 3 Pro (gemini-2.0-pro-exp-02-05) for research
- Reads/writes shared memory for context
- Extracts insights and sources from analysis
- Supports memory context in queries

**Usage:**
```python
from backend.generals import IntelligenceGeneral

general = IntelligenceGeneral(poll_interval=5)
await general.initialize()

# Run polling loop (blocking)
await general.run_loop()

# Or poll manually
task = await general.poll_task()
if task:
    result = await general.execute_task(task)
```

**Task Payload Options:**
- `query`: Research query string
- `context`: Additional context for the query
- `memory_keys`: List of memory keys to read for context
- `save_to_memory`: Boolean to save result to memory
- `memory_key`: Key to save result under
- `memory_ttl_seconds`: TTL for saved memory
- `max_tokens`: Maximum tokens for response (default: 8192)
- `temperature`: Temperature for generation (default: 0.7)
- `model`: Override model name (default: gemini-2.0-pro-exp-02-05)

### AntigravityGeneral (`antigravity_general.py`)

Polls `generals_tasks` for tasks with `task_type='orchestration'` and handles system-level coordination.

**Features:**
- Polls database for pending orchestration tasks
- Controls Antigravity.app via AppleScript
- Executes multi-tool workflows
- System-level automation
- IDE coordination

**Usage:**
```python
from backend.generals import AntigravityGeneral

general = AntigravityGeneral(poll_interval=10)
await general.initialize()

# Run polling loop (blocking)
await general.run()

# Or use singleton
from backend.generals.antigravity_general import get_antigravity_general
general = get_antigravity_general()
```

**Task Payload Options:**
- `app_command`: Control Antigravity app ('open' | 'quit' | 'activate' | 'status')
- `applescript`: Raw AppleScript code to execute
- `description`: Human-readable orchestration task description (for future LLM-based planning)

**Examples:**
```python
# Open Antigravity IDE
await coordinator.submit_task(
    task_type="orchestration",
    title="Open Antigravity IDE",
    payload={"app_command": "open"},
)

# Execute custom AppleScript
await coordinator.submit_task(
    task_type="orchestration",
    title="Custom automation",
    payload={
        "applescript": 'tell application "Finder" to get name of startup disk'
    },
)

# Check app status
await coordinator.submit_task(
    task_type="orchestration",
    title="Check Antigravity status",
    payload={"app_command": "status"},
)
```

### TaskCoordinator (`task_coordinator.py`)

High-level API for ZANTARA to interact with the system.

**Features:**
- Submit tasks (code or research)
- Monitor task status
- Retrieve results
- Manage shared memory
- View activity logs
- Get system statistics

**Usage:**
```python
from backend.generals import TaskCoordinator

coordinator = TaskCoordinator()
await coordinator.initialize()

# Submit a code task
task_id = await coordinator.submit_task(
    task_type="code",
    title="Run script",
    payload={"command": "python script.py"},
    priority=7,
)

# Wait for completion
result = await coordinator.wait_for_task(task_id, timeout=60)

# Submit a research task
research_id = await coordinator.submit_task(
    task_type="research",
    title="Research AI trends",
    payload={
        "query": "What are the latest AI trends?",
        "save_to_memory": True,
        "memory_key": "ai_trends",
    },
    priority=8,
)

# Get task result
result = await coordinator.get_task_result(research_id)

# Memory operations
await coordinator.set_memory("key", {"data": "value"})
memory = await coordinator.get_memory("key")
await coordinator.delete_memory("key")

# Monitoring
stats = await coordinator.get_stats()
activities = await coordinator.get_activity(limit=10)
tasks = await coordinator.get_tasks(status="pending")
```

## Task Types

### Code Tasks (`task_type='code'`)

Payload options:
- `command`: Shell command to execute
- `script_path`: Path to Python script to execute
- `code`: Python code string to execute
- `working_dir`: Working directory for execution
- `env_vars`: Environment variables dict
- `args`: Arguments for script execution
- `globals`: Global variables dict for code execution

### Research Tasks (`task_type='research'`)

Payload options:
- `query`: Research query (required)
- `context`: Additional context
- `memory_keys`: List of memory keys to read
- `save_to_memory`: Save result to memory
- `memory_key`: Key to save result under
- `memory_ttl_seconds`: TTL for memory
- `max_tokens`: Max tokens (default: 8192)
- `temperature`: Temperature (default: 0.7)
- `model`: Model override

### Orchestration Tasks (`task_type='orchestration'`)

Payload options:
- `app_command`: Control Antigravity app ('open' | 'quit' | 'activate' | 'status')
- `applescript`: Raw AppleScript code to execute
- `description`: Orchestration task description (for future LLM planning)

Examples:
```python
# Open Antigravity IDE
{"app_command": "open"}

# Check if app is running
{"app_command": "status"}

# Custom AppleScript
{"applescript": 'tell application "System Events" to get name of processes'}

# Future: Complex orchestration
{"description": "Deploy frontend to production and notify team"}
```

## Task Status Flow

1. `pending` - Task created, waiting for assignment
2. `assigned` - Task assigned to a general
3. `in_progress` - Task being executed
4. `completed` - Task completed successfully
5. `failed` - Task failed with error
6. `cancelled` - Task cancelled (only from pending/assigned)

## Priority System

Tasks have priority 1-10 (higher = more important):
- Default: 5
- High priority: 8-10
- Low priority: 1-3

Tasks are processed in priority order (highest first), then by creation time.

## Memory System

Shared memory allows generals to share context:
- Key-value store (JSONB values)
- Optional expiration (TTL)
- Automatic cleanup of expired entries
- Used for context sharing between tasks

## Activity Logging

All operations are logged to `generals_activity`:
- `task_polled`: Task was polled by a general
- `task_started`: Task execution started
- `task_completed`: Task completed successfully
- `task_failed`: Task failed
- `memory_read`: Memory key was read
- `memory_written`: Memory key was written
- `error`: Error occurred

## Testing

Run tests with:
```bash
pytest backend/generals/test_generals.py -v
```

Tests cover:
- Task polling and assignment
- Task execution (code and research)
- Memory operations
- Task coordination
- Integration workflows
- Error handling

## Examples

See `example_usage.py` for complete examples:
- Submitting and waiting for tasks
- Research tasks with memory
- Running generals in background
- Memory sharing between tasks
- System monitoring

## Integration with ZANTARA

ZANTARA can use TaskCoordinator to:
1. Submit tasks for execution
2. Monitor task progress
3. Retrieve results
4. Share context via memory
5. Monitor system health

Example integration:
```python
from backend.generals import TaskCoordinator

coordinator = TaskCoordinator()
await coordinator.initialize()

# Submit task from ZANTARA
task_id = await coordinator.submit_task(
    task_type="research",
    title="User query research",
    payload={"query": user_query},
    priority=7,
)

# Get result
result = await coordinator.wait_for_task(task_id)
```

## Requirements

- PostgreSQL database with schema from `schema.sql`
- Python 3.10+
- asyncpg for database access
- google-genai SDK for Gemini integration
- Environment variable `DATABASE_URL` configured

## Configuration

Set environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `GOOGLE_API_KEY` or `GOOGLE_CREDENTIALS_JSON`: For Gemini API access

## Notes

- Generals run independently and can be scaled horizontally
- Database polling uses `FOR UPDATE SKIP LOCKED` for concurrent safety
- Memory expiration is checked on read
- Activity logs are kept for monitoring and debugging
- Task results are stored as JSONB for flexibility
