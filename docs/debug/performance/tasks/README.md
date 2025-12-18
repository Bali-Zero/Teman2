# Performance Debug Task Files

This directory contains JSON task files for parallel Composer debugging sessions.

## Task Files Structure

Each task file contains:
- **priority**: critical | warning | info
- **area**: Specific area to debug
- **score**: Priority score (0-100)
- **scope**: List of files to analyze
- **metrics_to_collect**: Performance metrics to track
- **key_issues**: Known issues to address
- **tasks**: List of debugging tasks
- **expected_output**: Path to generated report
- **success_criteria**: Measurable success metrics

## Usage

Each Composer should:
1. Read the assigned task file JSON
2. Analyze the scope files
3. Collect the specified metrics
4. Address the key issues
5. Generate a report at the expected_output path
6. Document fixes and benchmarks

## Task Assignment

### Composer 1: Critical Priority
- `critical_rag_pipeline.json`
- `critical_database.json`
- `critical_llm_api.json`

### Composer 2: Warning Priority
- `warning_memory.json`
- `warning_agentic.json`

### Composer 3: Info Priority
- `info_code_quality.json`

## Running Tasks

```bash
# Example: Load task file and start debugging
python -c "
import json
with open('docs/debug/performance/tasks/critical_rag_pipeline.json') as f:
    task = json.load(f)
    print(f\"Area: {task['area']}\")
    print(f\"Priority: {task['priority']}\")
    print(f\"Tasks: {task['tasks']}\")
"
```

