import asyncio
import json
import logging
import time
from pathlib import Path

import asyncpg

from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Nuzantara-Retail-Sync")

# DATA_SOURCE: Intelligence Strategica Sezione G (Retail/Wholesale) fornita da Zero
RETAIL_INTELLIGENCE = {
    "47111": {  # Supermarket
        "market_sentiment": "Fine dell'economia informale. Ascesa del Social Commerce (TikTok Shop + Tokopedia). Dominio dello 'Smarter Spending'.",
        "bali_nuance": "Boutique Supermarkets ad alta densità (Pepito, GrandLucky). Domanda expat per prodotti biologici e importati.",
        "operational_risks": "Soglia 1.200mq per 100% PMA. Tracciabilità totale via NITKU e CoreTax. Vendor pruning forzato.",
        "investment_outlook": "ROI eccellente per format premium. I margini assorbono gli alti canoni di locazione balinesi.",
        "legacy_bridge": "Mapping stabile dal 2020, ma con barriere architettoniche più rigide per il controllo straniero.",
    },
    "47112": {  # Minimarket
        "market_sentiment": "Format di prossimità flessibili. Competizione oligopolistica (Indomaret/Alfamart).",
        "bali_nuance": "Mercato di quartiere per turisti. Indispensabile integrazione con QRIS e E-wallets.",
        "operational_risks": "CHIUSO alle PT PMA se < 400mq. Richiede modelli di master franchising o partnership locali.",
        "investment_outlook": "Margini compressi dalla guerra dei prezzi. Difficile per investitori esteri diretti.",
        "legacy_bridge": "Resta il baluardo protezionistico per le MSME indonesiane.",
    },
    "47724": {  # Retail Cosmetici (ex 46443 Wholesale logic)
        "market_sentiment": "Boom Men's Grooming (+300%). Fenomeno 'De-influencing' e ascesa degli Expert Creators (dermatologi).",
        "bali_nuance": "Skincare vegana e filtri solari etici a Uluwatu/Canggu. Margini simili ai mercati occidentali.",
        "operational_risks": "Registrazione BPOM (ML/MD) per ogni SKU. Scadenza perentoria Halal Ottobre 2026.",
        "investment_outlook": "Fossato competitivo per chi ottiene la certificazione Halal prima della tabula rasa di Ottobre 2026.",
        "legacy_bridge": "Codice 2025 per il dettaglio cosmetico, eredita la complessità regolatoria del vecchio wholesale.",
    },
    "46441": {  # Wholesale Pharma
        "market_sentiment": "Integrazione catena del freddo critica. Ascesa dei farmaci OTC tramite marketing D2C.",
        "bali_nuance": "Catalizzatore Sanur Health SEZ. Polo per forniture mediche oncologiche e di medicina estetica.",
        "operational_risks": "Licenza CDOB obbligatoria. Necessità di audit tecnici profondi e farmacisti a tempo pieno.",
        "investment_outlook": "Margini 12-25% per generici, fino al 35% per farmaci da banco (OTC).",
        "legacy_bridge": "Consolidamento per prevenire elusione normativa su preparati chimici e farmaci.",
    },
    "47214": {  # Retail Carne
        "market_sentiment": "Consumatori selettivi: focus su tracciabilità, origine (grass-fed) e certificazioni etiche.",
        "bali_nuance": "Dipendenza logistica da Gilimanuk. Vulnerabilità della cold chain durante i blocchi camion (Nataru).",
        "operational_risks": "Audit algoritmici CoreTax su sconti volumi B2B vs prezzi retail. Rischio shrinkage elevato.",
        "investment_outlook": "Alta redditività per boutique gastronomiche specializzate in tagli premium importati.",
        "legacy_bridge": "Specializzazione del retail alimentare per proteggere i margini contro la GDO generalista.",
    },
}


async def sync_postgres():
    pool = await asyncpg.create_pool(settings.database_url)
    for code, intel in RETAIL_INTELLIGENCE.items():
        entity_id = f"kbli:{code}"
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT properties FROM kg_nodes WHERE entity_id = $1", entity_id
                )
                current_props = json.loads(row["properties"]) if row and row["properties"] else {}
                updated_props = {
                    **current_props,
                    "intel_2026": {
                        **intel,
                        "last_updated": int(time.time()),
                        "source": "Gemini 3 PRO Deep Research - Retail & Pharma",
                    },
                    "is_enriched": True,
                }
                await conn.execute(
                    "UPDATE kg_nodes SET properties = $1, updated_at = NOW() WHERE entity_id = $2",
                    json.dumps(updated_props),
                    entity_id,
                )
                logger.info(f"✅ [Postgres] KBLI {code} updated.")
        except Exception as e:
            logger.error(f"❌ [Postgres] Failed KBLI {code}: {e}")
    await pool.close()


def sync_json():
    data_path = Path("../../source_documents/KBLI_2025_FINAL_CLEAN.json")
    with open(data_path) as f:
        full_data = json.load(f)
    updated = 0
    for item in full_data["data"]:
        code = item.get("kode_kbli_2025")
        if code in RETAIL_INTELLIGENCE:
            item["intel_2026"] = RETAIL_INTELLIGENCE[code]
            updated += 1
    with open(data_path, "w") as f:
        json.dump(full_data, f, indent=2)
    logger.info(f"✅ [JSON] Updated {updated} codes in KBLI_2025_FINAL_CLEAN.json")


async def main():
    await sync_postgres()
    sync_json()
    logger.info("🏁 RETAIL & PHARMA SYNC COMPLETE.")


if __name__ == "__main__":
    asyncio.run(main())
