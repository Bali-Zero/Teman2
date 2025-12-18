"""Check coverage for all assigned files"""
import subprocess
import re

files_to_check = [
    ("backend/app/routers/oracle_universal.py", "tests/unit/test_router_oracle_universal.py", 487, 272),
    ("backend/services/semantic_cache.py", "tests/unit/test_semantic_cache.py", 124, 89),
    ("backend/app/routers/crm_interactions.py", "tests/unit/test_router_crm_interactions.py", 217, 87),
    ("backend/app/routers/crm_clients.py", "tests/unit/test_router_crm_clients.py", 232, 64),
    ("backend/app/routers/crm_shared_memory.py", "tests/unit/test_router_crm_shared_memory.py", 137, 63),
    ("backend/app/routers/crm_practices.py", "tests/unit/test_router_crm_practices.py", 238, 60),
    ("backend/services/memory_service_postgres.py", "tests/unit/test_memory_service_postgres.py", 184, 49),
    ("backend/app/routers/oracle_ingest.py", "tests/unit/test_router_oracle_ingest.py", 78, 39),
    ("backend/app/routers/auth.py", "tests/unit/test_router_auth.py", 111, 26),
    ("backend/app/routers/agents.py", "tests/unit/test_router_agents.py", 125, 22),
    ("backend/services/collective_memory_workflow.py", "tests/unit/test_collective_memory_workflow.py", 181, 17),
    ("backend/app/routers/productivity.py", "tests/unit/test_router_productivity.py", 45, 17),
    ("backend/app/routers/notifications.py", "tests/unit/test_router_notifications.py", 53, 13),
    ("backend/app/routers/autonomous_agents.py", "tests/unit/test_router_autonomous_agents.py", 95, 5),
    ("backend/services/collective_memory_emitter.py", "tests/unit/test_collective_memory_emitter.py", 52, 4),
    ("backend/app/routers/health.py", "tests/unit/test_router_health.py", 23, 3),
    ("backend/app/routers/handlers.py", "tests/unit/test_router_handlers.py", 35, 0),
]

print("=" * 100)
print(f"{'FILE':<50} {'STMTS':<8} {'IMPACT':<8} {'CURRENT':<10} {'TARGET':<8} {'STATUS':<10}")
print("=" * 100)

total_stmts = 0
total_impact = 0

for source_file, test_file, stmts, impact in files_to_check:
    total_stmts += stmts
    total_impact += impact
    
    try:
        # Run coverage for this specific file
        cmd = f"python -m pytest {test_file} --cov={source_file} --cov-report=term-missing --no-cov-on-fail -q 2>&1"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        # Extract coverage percentage
        output = result.stdout + result.stderr
        
        # Look for coverage line
        coverage_match = re.search(rf"{re.escape(source_file)}\s+\d+\s+\d+\s+\d+\s+\d+\s+([\d.]+)%", output)
        
        if coverage_match:
            current_coverage = float(coverage_match.group(1))
            status = "✅ DONE" if current_coverage >= 90 else "🔴 TODO"
            print(f"{source_file.split('/')[-1]:<50} {stmts:<8} {impact:<8} {current_coverage:<9.1f}% {'90%':<8} {status:<10}")
        else:
            print(f"{source_file.split('/')[-1]:<50} {stmts:<8} {impact:<8} {'ERROR':<10} {'90%':<8} {'❌ ERROR':<10}")
    except Exception as e:
        print(f"{source_file.split('/')[-1]:<50} {stmts:<8} {impact:<8} {'ERROR':<10} {'90%':<8} {'❌ ERROR':<10}")

print("=" * 100)
print(f"{'TOTAL':<50} {total_stmts:<8} {total_impact:<8}")
print("=" * 100)
