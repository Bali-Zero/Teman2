#!/usr/bin/env python3
"""
Smart Matching - Automatic or Manual

Prova prima il matching automatico tramite API.
Se fallisce, genera un template per matching manuale.
"""

import sys
import subprocess


def main():
    print("\n" + "=" * 80)
    print("🔍 SMART MATCHING: Dropbox → CRM")
    print("=" * 80 + "\n")

    print("🎯 Strategia: Provo prima il matching automatico via API...")
    print("   Se fallisce, genero un template per compilazione manuale.\n")

    # Try automatic matching first
    print("=" * 80)
    print("TENTATIVO 1: Matching automatico via API")
    print("=" * 80 + "\n")

    try:
        result = subprocess.run(
            [sys.executable, "run_real_client_matching_api.py"],
            capture_output=False,
            text=True,
        )

        if result.returncode == 0:
            print("\n" + "=" * 80)
            print("✅ MATCHING AUTOMATICO COMPLETATO!")
            print("=" * 80 + "\n")
            return 0

    except Exception as e:
        print(f"⚠️  Matching automatico fallito: {e}\n")

    # If automatic matching failed, generate template
    print("=" * 80)
    print("FALLBACK: Generazione template per matching manuale")
    print("=" * 80 + "\n")

    try:
        result = subprocess.run(
            [sys.executable, "generate_matching_template.py"],
            capture_output=False,
            text=True,
        )

        if result.returncode == 0:
            print("\n" + "=" * 80)
            print("✅ TEMPLATE GENERATO!")
            print("=" * 80)
            print("\nUsa il CSV template per completare il matching manualmente.")
            print("Segui le istruzioni stampate sopra.\n")
            print("=" * 80 + "\n")
            return 0

    except Exception as e:
        print(f"\n❌ Errore nella generazione del template: {e}\n")
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
