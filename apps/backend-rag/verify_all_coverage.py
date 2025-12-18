"""Verify coverage for all critical files"""

import re
import subprocess

files = [
    "app.routers.crm_clients",
    "app.routers.crm_interactions",
    "app.routers.crm_shared_memory",
    "app.routers.agents",
    "app.routers.auth",
]

print("=" * 80)
print(f"{'FILE':<40} {'COVERAGE':<15} {'STATUS':<15}")
print("=" * 80)

for module in files:
    test_file = f"tests/unit/test_router_{module.split('.')[-1]}.py"
    cmd = f"python -m pytest {test_file} --cov={module} --cov-report=term -q 2>&1"

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr

        # Extract coverage percentage
        match = re.search(r"(\d+)%\s*$", output, re.MULTILINE)
        if match:
            cov = int(match.group(1))
            status = "✅ DONE" if cov >= 90 else "🔴 TODO"
            print(f"{module.split('.')[-1]:<40} {cov}%{'':<12} {status:<15}")
        else:
            print(f"{module.split('.')[-1]:<40} {'ERROR':<15} {'❌ ERROR':<15}")
    except Exception:
        print(f"{module.split('.')[-1]:<40} {'ERROR':<15} {'❌ ERROR':<15}")

print("=" * 80)
