#!/usr/bin/env python3
"""
ESEMPIO PRATICO: Come usare MultiAIAdapter

Questo script mostra esempi concreti di come usare il sistema Multi-AI.
"""

import asyncio
import sys
from pathlib import Path

# Aggiungi path al progetto
sys.path.insert(0, str(Path(__file__).parent / "apps" / "backend-rag"))

from backend.agents.services.multi_ai_adapter import (
    AIRequest,
    TaskType,
    AITool,
    get_multi_ai_adapter,
)


async def esempio_1_analizza_codice():
    """Esempio 1: Analizza codice usando Claude Max"""
    print("\n📊 ESEMPIO 1: Analizza codice")
    print("-" * 50)

    multi_ai = get_multi_ai_adapter()

    codice = """
def calcola_totale(items):
    totale = 0
    for item in items:
        totale += item.prezzo
    return totale
"""

    request = AIRequest(
        task_type=TaskType.CODE_ANALYSIS,
        prompt=f"Analizza questo codice Python e suggerisci miglioramenti:\n\n{codice}",
    )

    response = await multi_ai.generate(request)
    print(f"✅ Tool usato: {response.tool_used.value}")
    print(f"📝 Risposta: {response.text[:200]}...")


async def esempio_2_genera_test():
    """Esempio 2: Genera test usando Qwen"""
    print("\n🧪 ESEMPIO 2: Genera test")
    print("-" * 50)

    multi_ai = get_multi_ai_adapter()

    codice = """
def moltiplica(a, b):
    return a * b
"""

    request = AIRequest(
        task_type=TaskType.TEST_GENERATION,
        prompt=f"Genera test pytest per questa funzione:\n\n{codice}",
    )

    response = await multi_ai.generate(request)
    print(f"✅ Tool usato: {response.tool_used.value}")
    print(f"📝 Risposta: {response.text[:200]}...")


async def esempio_3_forza_claude():
    """Esempio 3: Forza uso di Claude Max"""
    print("\n🎯 ESEMPIO 3: Forza Claude Max")
    print("-" * 50)

    multi_ai = get_multi_ai_adapter()

    request = AIRequest(
        task_type=TaskType.CODE_ANALYSIS,
        prompt="Spiega cosa fa questo codice: def hello(): print('world')",
        preferred_tool=AITool.CLAUDE,  # Forza Claude Max
    )

    response = await multi_ai.generate(request)
    print(f"✅ Tool usato: {response.tool_used.value}")
    print(f"📝 Risposta: {response.text[:200]}...")


def esempio_4_apri_file_cursor():
    """Esempio 4: Apri file in Cursor IDE"""
    print("\n📂 ESEMPIO 4: Apri file in Cursor")
    print("-" * 50)

    from backend.agents.services.cursor_adapter import get_cursor_adapter

    cursor = get_cursor_adapter()

    # Apri file in Cursor IDE
    file_path = "apps/backend-rag/backend/app/main.py"
    if cursor.open_file(file_path):
        print(f"✅ File aperto in Cursor: {file_path}")
    else:
        print(f"❌ Errore aprendo file: {file_path}")


def esempio_5_apri_file_windsurf():
    """Esempio 5: Apri file in Windsurf IDE"""
    print("\n🌊 ESEMPIO 5: Apri file in Windsurf")
    print("-" * 50)

    from backend.agents.services.windsurf_adapter import get_windsurf_adapter

    windsurf = get_windsurf_adapter()

    if windsurf.is_available():
        file_path = "apps/backend-rag/backend/app/main.py"
        if windsurf.open_file(file_path):
            print(f"✅ File aperto in Windsurf: {file_path}")
        else:
            print(f"❌ Errore aprendo file: {file_path}")
    else:
        print("❌ Windsurf non disponibile")


async def esempio_6_lista_tools():
    """Esempio 6: Lista tools disponibili"""
    print("\n🔧 ESEMPIO 6: Tools disponibili")
    print("-" * 50)

    multi_ai = get_multi_ai_adapter()
    tools = multi_ai.get_available_tools()

    print("✅ Tools disponibili:")
    for tool in tools:
        print(f"   - {tool.value}")


async def main():
    """Esegui tutti gli esempi"""
    print("🚀 ESEMPI PRATICI: Come usare MultiAIAdapter")
    print("=" * 50)

    # Esempi async
    await esempio_1_analizza_codice()
    await esempio_2_genera_test()
    await esempio_3_forza_claude()
    await esempio_6_lista_tools()

    # Esempi sync
    esempio_4_apri_file_cursor()
    esempio_5_apri_file_windsurf()

    print("\n" + "=" * 50)
    print("✅ Esempi completati!")


if __name__ == "__main__":
    asyncio.run(main())
