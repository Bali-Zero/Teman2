"""
Test Coverage Analysis
Script per analizzare la copertura dei test e identificare gap

Coverage:
- Analisi endpoint coperti
- Identificazione gap di copertura
- Metriche di copertura
"""

from pathlib import Path


# Analizza la copertura dei test
def analyze_test_coverage():
    """Analizza la copertura completa dei test"""

    # Router principali da analizzare
    routers = {
        "agents": "agents.py",
        "auth": "auth.py",
        "crm_clients": "crm_clients.py",
        "crm_interactions": "crm_interactions.py",
        "crm_practices": "crm_practices.py",
        "crm_shared_memory": "crm_shared_memory.py",
        "conversations": "conversations.py",
        "handlers": "handlers.py",
        "health": "health.py",
        "intel": "intel.py",
        "legal_ingest": "legal_ingest.py",
        "media": "media.py",
        "memory_vector": "memory_vector.py",
        "notifications": "notifications.py",
        "oracle_universal": "oracle_universal.py",
        "oracle_ingest": "oracle_ingest.py",
        "productivity": "productivity.py",
        "root_endpoints": "root_endpoints.py",
        "team_activity": "team_activity.py",
        "whatsapp": "whatsapp.py",
        "instagram": "instagram.py",
        "ingest": "ingest.py",
        "image_generation": "image_generation.py",
        "agentic_rag": "agentic_rag.py",
        "autonomous_agents": "autonomous_agents.py",
    }

    # Analizza i test esistenti
    test_path = Path("tests/api")
    coverage = {}

    if test_path.exists():
        for router_name, router_file in routers.items():
            coverage[router_name] = {
                "has_tests": False,
                "test_files": [],
                "endpoint_count": 0,
            }

            # Cerca file di test correlati
            for test_file in test_path.glob("test_*.py"):
                content = test_file.read_text(encoding="utf-8", errors="ignore")

                # Verifica se il test copre questo router
                if (
                    router_name in content.lower()
                    or router_name.replace("_", "") in content.lower()
                    or router_file.replace(".py", "") in content.lower()
                ):
                    coverage[router_name]["has_tests"] = True
                    coverage[router_name]["test_files"].append(test_file.name)

    return coverage, routers


if __name__ == "__main__":
    coverage, routers = analyze_test_coverage()

    print("=== TEST COVERAGE ANALYSIS ===")
    print()

    covered = sum(1 for c in coverage.values() if c["has_tests"])
    total = len(coverage)

    print(f"Coverage: {covered}/{total} routers ({covered / total * 100:.1f}%)")
    print()

    print("Router Coverage:")
    for router_name, data in sorted(coverage.items()):
        status = "✅" if data["has_tests"] else "❌"
        test_files = ", ".join(data["test_files"][:3])
        if len(data["test_files"]) > 3:
            test_files += f" ... (+{len(data['test_files']) - 3} more)"
        print(f"  {status} {router_name}: {test_files if data['has_tests'] else 'No tests'}")










