#!/usr/bin/env python3
"""
Script per testare 40 domande business su Zantara AI Webapp
Genera report dettagliato con risultati e risposte precise
"""

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp

# Configurazione (può essere sovrascritta da env vars)
# Usa webapp endpoint che gestisce autenticazione
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://zantara.balizero.com")
API_ENDPOINT = f"{WEBAPP_URL}/api/chat/stream"  # Endpoint webapp che fa proxy al backend
TEST_USER_EMAIL = os.getenv("TEST_USER_EMAIL", "test@balizero.com")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", None)  # Bearer token (opzionale)
API_KEY = os.getenv("NUZANTARA_API_KEY", None)  # API key per service-to-service

# Domande organizzate per categoria
QUESTIONS = {
    "immigrazione": [
        {
            "id": "Q1",
            "text": "Ciao! Che tipo di visto serve per aprire un'attività a Bali?",
            "language": "it",
            "complexity": "semplice",
        },
        {
            "id": "Q2",
            "text": "Quanto costa il visto investitore KITAS e quali sono i requisiti completi?",
            "language": "it",
            "complexity": "media",
        },
        {
            "id": "Q3",
            "text": "Devo rinnovare il mio visto lavoro, ma la mia azienda ha cambiato nome legale. Cosa devo fare? Quali documenti servono e quanto tempo ci vuole?",
            "language": "it",
            "complexity": "complessa",
        },
        {
            "id": "Q4",
            "text": "Hey! What visa do I need to work remotely from Bali?",
            "language": "en",
            "complexity": "semplice",
        },
        {
            "id": "Q5",
            "text": "What's the difference between KITAS and KITAP? Which one is better for long-term stay?",
            "language": "en",
            "complexity": "media",
        },
        {
            "id": "Q6",
            "text": "Halo! Visa apa yang perlu untuk buka usaha di Indonesia?",
            "language": "id",
            "complexity": "semplice",
        },
        {
            "id": "Q7",
            "text": "Berapa lama proses KITAS investor? Dokumen apa saja yang diperlukan dan berapa biayanya?",
            "language": "id",
            "complexity": "media",
        },
        {
            "id": "Q8",
            "text": "Hola! ¿Qué visa necesito para trabajar en Indonesia?",
            "language": "es",
            "complexity": "semplice",
        },
    ],
    "tasse": [
        {
            "id": "Q9",
            "text": "Come funziona il sistema fiscale in Indonesia? Devo pagare le tasse se sono straniero?",
            "language": "it",
            "complexity": "semplice",
        },
        {
            "id": "Q10",
            "text": "Ho un'attività PT PMA. Quali sono le tasse che devo pagare e quando sono le scadenze?",
            "language": "it",
            "complexity": "media",
        },
        {
            "id": "Q11",
            "text": "La mia azienda ha fatturato 4.5 miliardi di rupie quest'anno. Qual è la struttura fiscale ottimale per ridurre il carico fiscale? Ci sono incentivi fiscali disponibili?",
            "language": "it",
            "complexity": "complessa",
        },
        {
            "id": "Q12",
            "text": "Do I need to pay taxes in Indonesia if I'm a foreigner working here?",
            "language": "en",
            "complexity": "semplice",
        },
        {
            "id": "Q13",
            "text": "What's the corporate tax rate for PT PMA companies? Are there any tax incentives?",
            "language": "en",
            "complexity": "media",
        },
        {
            "id": "Q14",
            "text": "My company operates in multiple sectors (tourism, tech, consulting). How do I optimize tax structure with different tax incentives? What are the reporting requirements?",
            "language": "en",
            "complexity": "complessa",
        },
        {
            "id": "Q15",
            "text": "Bagaimana cara bayar pajak perusahaan? Kapan deadline-nya?",
            "language": "id",
            "complexity": "semplice",
        },
        {
            "id": "Q16",
            "text": "PT saya baru dapat NPWP. Apa saja kewajiban pajak yang harus dipenuhi setiap bulan?",
            "language": "id",
            "complexity": "media",
        },
        {
            "id": "Q17",
            "text": "¿Cómo funciona el sistema de impuestos para empresas extranjeras en Indonesia?",
            "language": "es",
            "complexity": "semplice",
        },
    ],
    "kbli": [
        {
            "id": "Q18",
            "text": "Cos'è il KBLI e perché è importante per la mia azienda?",
            "language": "it",
            "complexity": "semplice",
        },
        {
            "id": "Q19",
            "text": "Voglio aprire un'attività di consulenza digitale e marketing online. Quale codice KBLI devo usare?",
            "language": "it",
            "complexity": "media",
        },
        {
            "id": "Q20",
            "text": "Devo cambiare il codice KBLI della mia azienda perché abbiamo aggiunto una nuova attività (da ristorante a ristorante + catering). Qual è la procedura completa? Ci sono implicazioni fiscali o legali?",
            "language": "it",
            "complexity": "complessa",
        },
        {
            "id": "Q21",
            "text": "What is KBLI code and why do I need it for my business?",
            "language": "en",
            "complexity": "semplice",
        },
        {
            "id": "Q22",
            "text": "I want to start an e-commerce business selling Indonesian products online. Which KBLI code should I use?",
            "language": "en",
            "complexity": "media",
        },
        {
            "id": "Q23",
            "text": "My PT PMA has multiple business activities (software development, consulting, training). Can I have multiple KBLI codes? What are the implications for foreign ownership limits?",
            "language": "en",
            "complexity": "complessa",
        },
        {
            "id": "Q24",
            "text": "Apa itu KBLI? Kenapa penting untuk bisnis?",
            "language": "id",
            "complexity": "semplice",
        },
        {
            "id": "Q25",
            "text": "Saya mau buka usaha kuliner (restoran + cafe). KBLI apa yang cocok?",
            "language": "id",
            "complexity": "media",
        },
        {
            "id": "Q26",
            "text": "PT saya mau tambah kegiatan usaha baru (dari jual barang jadi jual barang + jasa konsultasi). Bagaimana prosedur perubahan KBLI? Perlu ubah NIB juga?",
            "language": "id",
            "complexity": "complessa",
        },
        {
            "id": "Q27",
            "text": "¿Qué es el código KBLI y cómo lo obtengo?",
            "language": "es",
            "complexity": "semplice",
        },
    ],
    "legal": [
        {
            "id": "Q28",
            "text": "Quali sono i documenti necessari per aprire una PT PMA?",
            "language": "it",
            "complexity": "semplice",
        },
        {
            "id": "Q29",
            "text": "La mia azienda deve rispettare le norme OSS. Cosa significa e quali sono gli obblighi?",
            "language": "it",
            "complexity": "media",
        },
        {
            "id": "Q30",
            "text": "Ho bisogno di cambiare la struttura societaria della mia PT (da PT biasa a PT PMA). Quali sono le implicazioni legali e fiscali? Qual è la procedura completa?",
            "language": "it",
            "complexity": "complessa",
        },
        {
            "id": "Q31",
            "text": "What documents do I need to set up a PT PMA company in Indonesia?",
            "language": "en",
            "complexity": "semplice",
        },
        {
            "id": "Q32",
            "text": "What are the compliance requirements for foreign companies operating in Indonesia?",
            "language": "en",
            "complexity": "media",
        },
        {
            "id": "Q33",
            "text": "My company needs to comply with BKPM regulations. What are the reporting requirements and deadlines? What happens if I miss a deadline?",
            "language": "en",
            "complexity": "complessa",
        },
        {
            "id": "Q34",
            "text": "Dokumen apa saja yang perlu untuk buka PT?",
            "language": "id",
            "complexity": "semplice",
        },
        {
            "id": "Q35",
            "text": "Apa itu OSS dan kenapa penting untuk bisnis? Apa kewajiban yang harus dipenuhi?",
            "language": "id",
            "complexity": "media",
        },
    ],
    "property": [
        {
            "id": "Q36",
            "text": "Posso comprare una casa a Bali come straniero? Quali sono le opzioni?",
            "language": "it",
            "complexity": "semplice",
        },
        {
            "id": "Q37",
            "text": "Quali sono le opzioni per investire in immobiliare in Indonesia? Quali sono i vantaggi e svantaggi di ciascuna?",
            "language": "it",
            "complexity": "media",
        },
        {
            "id": "Q38",
            "text": "Can foreigners buy property in Indonesia? What are the legal structures?",
            "language": "en",
            "complexity": "semplice",
        },
        {
            "id": "Q39",
            "text": "What are the legal structures for property investment in Indonesia? Which one is best for long-term investment?",
            "language": "en",
            "complexity": "media",
        },
    ],
    "general": [
        {
            "id": "Q40",
            "text": "Quali sono i principali errori da evitare quando si apre un'attività in Indonesia?",
            "language": "it",
            "complexity": "media",
        },
        {
            "id": "Q41",
            "text": "What are the biggest challenges for expats starting a business in Indonesia? How can I prepare?",
            "language": "en",
            "complexity": "media",
        },
    ],
}


async def test_question(
    session: aiohttp.ClientSession, question: dict[str, Any]
) -> dict[str, Any]:
    """Testa una singola domanda e ritorna risultati (gestisce streaming)"""
    start_time = time.time()
    result = {
        "question_id": question["id"],
        "question": question["text"],
        "language": question["language"],
        "complexity": question["complexity"],
        "success": False,
        "response_time": 0,
        "response": "",
        "error": None,
        "model_used": None,
    }

    try:
        headers = {"Content-Type": "application/json"}
        if AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

        # Webapp endpoint usa POST con body JSON
        payload = {
            "message": question["text"],
            "conversation_history": [],
            "metadata": {
                "client_locale": question["language"],
                "client_timezone": "UTC",
            },
        }

        async with session.post(
            API_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120),  # Streaming può richiedere più tempo
        ) as response:
            if response.status == 200:
                # Leggi streaming response (text/plain, chunked)
                full_response = ""
                async for chunk in response.content.iter_chunked(1024):
                    if chunk:
                        try:
                            decoded = chunk.decode("utf-8", errors="ignore")
                            full_response += decoded
                        except Exception as e:
                            print(f"  ⚠️ Decode error: {e}")

                result["response_time"] = time.time() - start_time
                result["success"] = True
                result["response"] = full_response.strip()
                
                # Cerca model info nel response (se presente)
                response_lower = full_response.lower()
                if "gemma" in response_lower or "jaksel" in response_lower:
                    result["model_used"] = "gemma-9b-jaksel"
                elif "gemini" in response_lower:
                    result["model_used"] = "gemini-fallback"
                else:
                    result["model_used"] = "unknown"
            else:
                error_text = await response.text()
                result["error"] = f"HTTP {response.status}: {error_text}"
                result["response_time"] = time.time() - start_time

    except asyncio.TimeoutError:
        result["error"] = "Timeout (>60s)"
        result["response_time"] = time.time() - start_time
    except Exception as e:
        result["error"] = str(e)
        result["response_time"] = time.time() - start_time

    return result


async def run_all_tests() -> dict[str, Any]:
    """Esegue tutti i test e genera report"""
    print("🚀 Starting Business Questions Test Suite...")
    print(f"📡 Testing endpoint: {API_ENDPOINT}")
    print(f"👤 Test user: {TEST_USER_EMAIL}\n")

    all_results = []
    category_stats = {}

    async with aiohttp.ClientSession() as session:
        # Test tutte le domande
        for category, questions in QUESTIONS.items():
            print(f"📂 Testing category: {category.upper()} ({len(questions)} questions)")
            category_results = []

            for question in questions:
                print(f"  ⏳ Testing {question['id']} ({question['language']}, {question['complexity']})...", end=" ")
                result = await test_question(session, question)
                category_results.append(result)
                all_results.append(result)

                if result["success"]:
                    print(f"✅ ({result['response_time']:.2f}s)")
                else:
                    print(f"❌ ERROR: {result['error']}")

                # Small delay between requests
                await asyncio.sleep(1)

            # Stats per categoria
            success_count = sum(1 for r in category_results if r["success"])
            avg_time = (
                sum(r["response_time"] for r in category_results) / len(category_results)
                if category_results
                else 0
            )
            category_stats[category] = {
                "total": len(questions),
                "success": success_count,
                "success_rate": (success_count / len(questions) * 100) if questions else 0,
                "avg_time": avg_time,
            }

            print(f"  ✅ Category complete: {success_count}/{len(questions)} success\n")

    # Calcola statistiche globali
    total_questions = len(all_results)
    total_success = sum(1 for r in all_results if r["success"])
    total_failed = total_questions - total_success
    avg_response_time = sum(r["response_time"] for r in all_results) / total_questions if all_results else 0

    # Model usage stats
    model_usage = {}
    for result in all_results:
        model = result.get("model_used", "unknown")
        model_usage[model] = model_usage.get(model, 0) + 1

    return {
        "timestamp": datetime.now().isoformat(),
        "endpoint": API_ENDPOINT,
        "test_user": TEST_USER_EMAIL,
        "summary": {
            "total_questions": total_questions,
            "success": total_success,
            "failed": total_failed,
            "success_rate": (total_success / total_questions * 100) if total_questions > 0 else 0,
            "avg_response_time": avg_response_time,
            "min_response_time": min((r["response_time"] for r in all_results), default=0),
            "max_response_time": max((r["response_time"] for r in all_results), default=0),
        },
        "category_stats": category_stats,
        "model_usage": model_usage,
        "results": all_results,
    }


def generate_markdown_report(results: dict[str, Any]) -> str:
    """Genera report markdown dettagliato"""
    report = f"""# Test Results - Business Questions

**Data Test**: {results['timestamp']}  
**Endpoint**: {results['endpoint']}  
**Test User**: {results['test_user']}

---

## 📊 SUMMARY STATISTICS

- **Total Questions**: {results['summary']['total_questions']}
- **Success**: {results['summary']['success']} ({results['summary']['success_rate']:.1f}%)
- **Failed**: {results['summary']['failed']}
- **Average Response Time**: {results['summary']['avg_response_time']:.2f}s
- **Min Response Time**: {results['summary']['min_response_time']:.2f}s
- **Max Response Time**: {results['summary']['max_response_time']:.2f}s

### Model Usage

"""
    for model, count in results["model_usage"].items():
        percentage = (count / results["summary"]["total_questions"] * 100) if results["summary"]["total_questions"] > 0 else 0
        report += f"- **{model}**: {count} ({percentage:.1f}%)\n"

    report += "\n---\n\n## 📂 PER CATEGORY\n\n"
    for category, stats in results["category_stats"].items():
        report += f"### {category.upper()}\n"
        report += f"- Total: {stats['total']}\n"
        report += f"- Success: {stats['success']} ({stats['success_rate']:.1f}%)\n"
        report += f"- Avg Time: {stats['avg_time']:.2f}s\n\n"

    report += "---\n\n## 📝 DETAILED RESULTS\n\n"
    for result in results["results"]:
        status = "✅" if result["success"] else "❌"
        report += f"### {status} {result['question_id']} - {result['language'].upper()} ({result['complexity']})\n\n"
        report += f"**Question**: {result['question']}\n\n"
        if result["success"]:
            report += f"**Response Time**: {result['response_time']:.2f}s\n"
            report += f"**Model Used**: {result.get('model_used', 'unknown')}\n\n"
            report += f"**Response**:\n\n{result['response']}\n\n"
        else:
            report += f"**Error**: {result['error']}\n\n"
        report += "---\n\n"

    return report


async def main():
    """Main function"""
    try:
        results = await run_all_tests()

        # Salva risultati JSON
        output_dir = Path("test_results")
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        json_file = output_dir / f"business_test_results_{timestamp}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 JSON results saved: {json_file}")

        # Genera report markdown
        markdown_report = generate_markdown_report(results)
        md_file = output_dir / f"business_test_report_{timestamp}.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(markdown_report)
        print(f"📄 Markdown report saved: {md_file}")

        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Questions: {results['summary']['total_questions']}")
        print(f"Success Rate: {results['summary']['success_rate']:.1f}%")
        print(f"Average Response Time: {results['summary']['avg_response_time']:.2f}s")
        print(f"\nModel Usage:")
        for model, count in results["model_usage"].items():
            print(f"  - {model}: {count}")
        print("\n✅ Test complete!")

    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

