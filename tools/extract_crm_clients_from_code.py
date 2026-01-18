#!/usr/bin/env python3
"""
Extract CRM Clients from Backend Code

Analizza il codice del backend per estrarre informazioni sui clienti
e costruisce una lista per il matching automatico.
"""

import json
import re
from pathlib import Path

BACKEND_DIR = Path.home() / "Desktop/nuzantara/apps/backend-rag/backend"


def search_for_client_data():
    """Search backend code for client data, migrations, seeds, etc."""

    print("\n" + "=" * 80)
    print("🔍 RICERCA DATI CLIENTI NEL CODICE BACKEND")
    print("=" * 80 + "\n")

    client_data = []

    # 1. Check migrations for seed data
    migrations_dir = BACKEND_DIR / "migrations"
    if migrations_dir.exists():
        print("📂 Cerco in migrations...")
        for migration_file in migrations_dir.rglob("*.py"):
            try:
                content = migration_file.read_text()
                # Look for INSERT statements or seed data
                if "INSERT" in content or "clients" in content.lower():
                    print(f"   Found: {migration_file.name}")
            except Exception:
                pass

    # 2. Check for seed files
    data_dir = BACKEND_DIR / "data"
    if data_dir.exists():
        print("\n📂 Cerco in data/...")
        for data_file in data_dir.rglob("*.json"):
            try:
                with open(data_file) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "name" in item:
                                print(
                                    f"   Found: {data_file.name} - {item.get('name')}"
                                )
                                client_data.append(item)
            except Exception:
                pass

        for data_file in data_dir.rglob("*.csv"):
            print(f"   Found CSV: {data_file.name}")

    # 3. Check test files for sample data
    tests_dir = BACKEND_DIR / "tests"
    if tests_dir.exists():
        print("\n📂 Cerco in tests/...")
        for test_file in tests_dir.rglob("*crm*.py"):
            try:
                content = test_file.read_text()
                # Look for client names in test data
                names = re.findall(r'["\']([A-Z][a-z]+ [A-Z][a-z]+)["\']', content)
                if names:
                    print(f"   Found in {test_file.name}: {len(names)} names")
                    for name in set(names):
                        client_data.append({"name": name})
            except Exception:
                pass

    return client_data


def main():
    client_data = search_for_client_data()

    if client_data:
        print("\n" + "=" * 80)
        print(f"✅ Trovati {len(client_data)} potenziali clienti")
        print("=" * 80 + "\n")

        # Save to JSON
        output_file = "extracted_crm_clients.json"
        with open(output_file, "w") as f:
            json.dump(client_data, f, indent=2)

        print(f"💾 Salvato in: {output_file}\n")
    else:
        print("\n⚠️  Nessun dato cliente trovato nel codice backend")
        print("Procedo con approccio alternativo...\n")


if __name__ == "__main__":
    main()
