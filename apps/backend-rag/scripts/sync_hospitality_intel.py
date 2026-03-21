import asyncio
import json
import logging
import time
from pathlib import Path

import asyncpg

from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Nuzantara-Hospitality-Sync")

# DATA_SOURCE: Intelligence Strategica Sezione I fornita da Zero
HOSPITALITY_INTELLIGENCE = {
    # --- ACCOMMODATION (55xxx) ---
    "55101": {
        "market_sentiment": "Saturazione a Sud. Trend 2026: Wellness & Eco-Resort nel Nord/Est di Bali. Focus su infrastrutture aeroportuali future.",
        "bali_nuance": "Pressione massima su Pink Zones. Sfida logistica per approvvigionamento fine-dining causa congestione Gilimanuk.",
        "operational_risks": "Standard ambientali PBG/SLF più stringenti. Gestione rifiuti liquidi obbligatoria.",
        "investment_outlook": "ROI 8-12%. Fossato competitivo: infrastruttura integrata (Spa/Co-working) per massimizzare TRevPAR.",
        "legacy_bridge": "Mapping stabile, ma con rigida applicazione del piano regolatore (RDTR) locale.",
    },
    "55203": {
        "market_sentiment": "Core business di Bali. Passaggio da autogestione a Branded Villas gestite da professional Management Companies.",
        "bali_nuance": "Rischio Green Zone letale (no licenza turistica). Il Banjar impone tasse informali e regole di vicinato.",
        "operational_risks": "Oversupply a Canggu. Necessità di marketing algoritmico per competere su Airbnb/Booking.",
        "investment_outlook": "ROI 12-18%. Terreni e fabbricati contano nel calcolo dei 10 Miliardi (BKPM 5/2025).",
        "legacy_bridge": "Codice definitivo per Vila nel 2025 (ex 55193 in alcune bozze). Include gestione professionale.",
    },
    "55204": {
        "market_sentiment": "Golden asset class 2026. Ibrido hotel/appartamento per Global Nomads e expat a medio-lungo termine.",
        "bali_nuance": "Verticalizzazione (max 15 metri) per risolvere la mancanza di spazio a Canggu e Uluwatu.",
        "operational_risks": "Opex inferiori rispetto a hotel tradizionale. Gestione servizi centralizzati.",
        "investment_outlook": "Occupazione stabile >80%. ROI eccellente grazie a costi operativi ridotti.",
        "legacy_bridge": "Classificazione iper-specifica per Aparthotel, distinta dalle ville e dagli hotel puri.",
    },
    "55201": {
        "market_sentiment": "Mercato in contrazione per investitori esteri. ROI compresso dalla guerra dei prezzi.",
        "bali_nuance": "Storicamente riservato ai locali (Pondok Wisata). PMA sconsigliata per questo codice.",
        "operational_risks": "Rischio chiusura per strutture non MSME. Limiti operativi stringenti.",
        "investment_outlook": "Basso rendimento per capitali stranieri. Rischio operativo alto.",
        "legacy_bridge": "Pondok Wisata tradizionale, ora sotto stretta sorveglianza per proteggere i locali.",
    },
    # --- GASTRONOMY (56xxx) ---
    "56101": {
        "market_sentiment": "Dominio dello 'Smart Luxury' e farm-to-table. Il consumatore esige tracciabilità etica e narrazione.",
        "bali_nuance": "Hurdles logistici per cold chain (Wagyu/Latticini). Chiusura scorciatoie locali impatta tempi consegna.",
        "operational_risks": "Investimento 10 Miliardi applicato PER KABUPATEN. Certificazione sanitaria SLHS obbligatoria.",
        "investment_outlook": "Margini netti 15-20%. Dipende da 'location intelligence' e controllo food cost.",
        "legacy_bridge": "Ristorante fisso (ex 56102). Nel 2025 è Rischio Basso (NIB solo), a differenza del Kedai.",
    },
    "56102": {
        "market_sentiment": "Ascesa di Boutique Food Trucks e chioschi specialty coffee/matcha in centri padel e resort.",
        "bali_nuance": "Logistica flessibile per zone ad alta densità. Flotte di food truck per giustificare l'investimento.",
        "operational_risks": "Necessità di creare catene di chioschi per raggiungere la soglia di 10 Miliardi nel Kabupaten.",
        "investment_outlook": "Scalabilità rapida. Ideale per concept moderni e mobili.",
        "legacy_bridge": "CAMBIO RADICALE: Nel 2025 copre SOLO strutture non-fisse (Food Trucks). Prima era fisso.",
    },
}


async def sync_postgres():
    pool = await asyncpg.create_pool(settings.database_url)
    logger.info("Connecting to PostgreSQL for Section I sync...")
    for code, intel in HOSPITALITY_INTELLIGENCE.items():
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
                        "market_sentiment": intel["market_sentiment"],
                        "bali_nuance": intel["bali_nuance"],
                        "operational_risks": intel["operational_risks"],
                        "investment_outlook": intel["investment_outlook"],
                        "legacy_bridge": intel["legacy_bridge"],
                        "last_updated": int(time.time()),
                        "source": "Gemini 3 PRO Deep Research - Section I",
                    },
                    "is_enriched": True,
                }

                await conn.execute(
                    "UPDATE kg_nodes SET properties = $1, updated_at = NOW() WHERE entity_id = $2",
                    json.dumps(updated_props),
                    entity_id,
                )
                logger.info(f"✅ [Postgres] KBLI {code} enriched.")
        except Exception as e:
            logger.error(f"❌ [Postgres] Failed KBLI {code}: {e}")
    await pool.close()


def sync_json():
    data_path = Path("../../source_documents/KBLI_2025_FINAL_CLEAN.json")
    if not data_path.exists():
        logger.error(f"JSON source not found at {data_path.absolute()}!")
        return

    with open(data_path) as f:
        full_data = json.load(f)

    updated = 0
    for item in full_data["data"]:
        code = item.get("kode_kbli_2025")
        if code in HOSPITALITY_INTELLIGENCE:
            item["intel_2026"] = HOSPITALITY_INTELLIGENCE[code]
            updated += 1

    with open(data_path, "w") as f:
        json.dump(full_data, f, indent=2)
    logger.info(f"✅ [JSON] Updated {updated} codes in KBLI_2025_FINAL_CLEAN.json")


async def main():
    await sync_postgres()
    sync_json()
    logger.info("🏁 SECTION I SYNC COMPLETE.")


if __name__ == "__main__":
    asyncio.run(main())
