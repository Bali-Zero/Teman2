#!/usr/bin/env python3
"""
Analisi completa performance reranking
Genera report con metriche, costi e precisione
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://nuzantara-rag.fly.dev"
OUTPUT_DIR = Path("monitoring/reranking")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def fetch_metrics() -> dict[str, Any]:
    """Fetch Prometheus metrics"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/metrics")
        return parse_metrics(response.text)


def parse_metrics(metrics_text: str) -> dict[str, Any]:
    """Parse Prometheus metrics text"""
    metrics = {}

    for line in metrics_text.split("\n"):
        if line.startswith("#") or not line.strip():
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        metric_name = parts[0]
        value = parts[1]

        # Extract key metrics
        if "rag_reranking_duration_seconds_count" in metric_name:
            metrics["rerank_calls"] = float(value)
        elif metric_name == "zantara_rag_early_exit_total":
            metrics["early_exits"] = float(value)
        elif "rag_context_length_tokens_bucket" in metric_name and "le=" in metric_name:
            # Get last bucket value
            if 'le="+Inf"' in metric_name:
                metrics["context_length_total"] = float(value)

    return metrics


def calculate_costs(metrics: dict[str, Any]) -> dict[str, float]:
    """Calculate costs and savings"""
    # These should be updated with real values from dashboards
    ZERANK_COST_PER_CALL = 0.0001  # Update from ZeroEntropy dashboard
    GEMINI_SAVINGS_PER_QUERY = 0.00028  # Average estimated savings

    rerank_calls = metrics.get("rerank_calls", 0)
    early_exits = metrics.get("early_exits", 0)
    total_queries = rerank_calls + early_exits

    zerank_cost = rerank_calls * ZERANK_COST_PER_CALL
    gemini_savings = rerank_calls * GEMINI_SAVINGS_PER_QUERY
    net_savings = gemini_savings - zerank_cost

    return {
        "total_queries": total_queries,
        "rerank_calls": rerank_calls,
        "early_exits": early_exits,
        "early_exit_rate": (early_exits / (total_queries + 1)) * 100,
        "zerank_cost": zerank_cost,
        "gemini_savings": gemini_savings,
        "net_savings": net_savings,
        "roi_positive": net_savings > 0,
    }


def generate_report(metrics: dict[str, Any], costs: dict[str, float]) -> str:
    """Generate comprehensive report"""
    timestamp = datetime.now().isoformat()

    report = f"""# 📊 REPORT ANALISI RERANKING

**Data Generazione**: {timestamp}
**Endpoint**: {BASE_URL}

---

## 📈 METRICHE PERFORMANCE

### Reranking
- **Chiamate reranking**: {metrics.get("rerank_calls", 0):.0f}
- **Early exits**: {metrics.get("early_exits", 0):.0f}
- **Early exit rate**: {costs["early_exit_rate"]:.2f}%
- **Query totali**: {costs["total_queries"]:.0f}

### Context Length
- **Token totali processati**: {metrics.get("context_length_total", "N/A")}

---

## 💰 ANALISI COSTI

### ZeRank API
- **Costo totale**: ${costs["zerank_cost"]:.6f}
- **Costo per chiamata**: $0.0001 (da verificare su dashboard)

### Gemini Savings
- **Risparmio totale**: ${costs["gemini_savings"]:.6f}
- **Risparmio per query**: $0.00028 (stimato)

### ROI
- **Risparmio netto**: ${costs["net_savings"]:.6f}
- **Status**: {"✅ ROI POSITIVO" if costs["roi_positive"] else "⚠️ ROI NEGATIVO"}

---

## 🎯 VALUTAZIONE PRECISIONE

### Metriche Qualità
- **Evidence Score**: Da verificare nei log
- **User Feedback**: Da raccogliere
- **Relevance**: Da analizzare

### Raccomandazioni
1. Verificare costi reali su dashboard ZeroEntropy
2. Confrontare risultati con/senza reranking
3. Misurare precision@5
4. Raccogliere feedback utenti

---

## 📝 PROSSIMI PASSI

1. ⏳ Monitorare per altre 24h
2. ⏳ Aggiornare costi reali da dashboard
3. ⏳ Analizzare feedback utenti
4. ⏳ Ottimizzare se necessario

---

**Nota**: I costi sono stime. Verificare valori reali su:
- ZeroEntropy Dashboard: https://zeroentropy.dev/dashboard
- Gemini Usage Dashboard: Google Cloud Console
"""

    return report


async def main():
    """Main function"""
    print("📊 ANALISI PERFORMANCE RERANKING")
    print("=" * 50)
    print()

    # Fetch metrics
    print("📡 Recuperando metriche...")
    metrics = await fetch_metrics()
    print(f"✅ Metriche recuperate: {len(metrics)} metriche")
    print()

    # Calculate costs
    print("💰 Calcolando costi...")
    costs = calculate_costs(metrics)
    print("✅ Analisi costi completata")
    print()

    # Generate report
    print("📝 Generando report...")
    report = generate_report(metrics, costs)

    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = OUTPUT_DIR / f"performance_report_{timestamp}.md"
    report_file.write_text(report)

    print(f"✅ Report salvato: {report_file}")
    print()
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
