import asyncio
import json
import logging
import time
from pathlib import Path

import asyncpg

from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Nuzantara-Hospitality-Final")

# DATA_SOURCE: Intelligence Strategica Sezione I (Report Finale)
HOSPITALITY_DATA = {
    "55101": {
        "market_sentiment": "Mercato Sud saturo. Trend 2026: Wellness & Eco-Resort nel Nord/Est (Lovina/Amed).",
        "bali_nuance": "Pressione massima Pink Zones. Necessità di allineamento RDTR e gestione colli di bottiglia logistici da Giava.",
        "operational_risks": "Standard ambientali PBG/SLF più stringenti per hotel. Logistica approvvigionamento critica.",
        "investment_outlook": "ROI 8-12%. Valore aggiunto: infrastruttura integrata per massimizzare il TRevPAR.",
        "legacy_bridge": "Mapping stabile dal 2020, ma con controlli ambientali raddoppiati.",
    },
    "55203": {
        "market_sentiment": "Core business Bali. Trend: Branded Villas gestite da management professionali. Oversupply a Canggu.",
        "bali_nuance": "Rischio Green Zone (Pertanian) letale. Il Banjar impone tasse informali e regole di vicinato.",
        "operational_risks": "Impossibile ottenere licenze turistiche in zone non corrette. Necessità di marketing algoritmico.",
        "investment_outlook": "ROI 12-18%. Terreni e fabbricati inclusi nei 10 Miliardi di investimento (BKPM 5/2025).",
        "legacy_bridge": "Codice definitivo 2025 per Vila. Sostituisce i vecchi codici residenziali usati impropriamente.",
    },
    "55204": {
        "market_sentiment": "Golden Asset Class 2026. Perfetto per 'Glowmads' (Global Nomads) con affitti medio-lungo termine.",
        "bali_nuance": "Risolve la mancanza di spazio a Canggu/Uluwatu tramite verticalizzazione (max 15 metri).",
        "operational_risks": "Opex ridotti rispetto a hotel. Gestione servizi centralizzati obbligatoria.",
        "investment_outlook": "ROI Eccellente. Occupazione >80%. Asset molto liquido per investitori esteri.",
        "legacy_bridge": "Nuova categoria specifica per Aparthotel, distinta dalle ville e dagli hotel tradizionali.",
    },
    "56101": {
        "market_sentiment": "Dominio 'Smart Luxury' e farm-to-table. Consumatori esigono tracciabilità etica.",
        "bali_nuance": "Sfida titanica per cold chain fuori Denpasar. Chiusura shortcut impatta tempi di consegna.",
        "operational_risks": "Regola 10 Miliardi PER KABUPATEN. Obbligo certificato sanitario SLHS e Halal/Non-Halal declaration.",
        "investment_outlook": "Margini 15-20%. Dipende da 'Location Intelligence' e controllo food cost.",
        "legacy_bridge": "Ristorante fisso. Nel 2025 è Rischio Basso, preferibile al Kedai per le PMA.",
    },
    "56102": {
        "market_sentiment": "Ascesa Boutique Food Trucks e chioschi premium in centri sportivi (Padel) e residenziali.",
        "bali_nuance": "Flessibilità logistica. Ideale per zone turistiche pedonali o mercati gourmet.",
        "operational_risks": "La PT PMA deve creare flotte di truck per giustificare i 10 Miliardi nel Kabupaten.",
        "investment_outlook": "Scalabilità rapida. Investimento meno oneroso in termini di strutture fisse.",
        "legacy_bridge": "CAMBIO TOTALE: Ora copre SOLO strutture non-fisse. Prima era il codice per i ristoranti fisici.",
    },
    "56301": {
        "market_sentiment": "Trend 'Listening Bars' e format ibridi. Richiesta di bevande premium e sicurezza.",
        "bali_nuance": "Gestione del vicinato (Banjar) critica per rumore e orari. Licenze musica obbligatorie.",
        "operational_risks": "Licenza alcolici NPBBKC (A, B, C) obbligatoria. Rischio penale per vendita senza licenza.",
        "investment_outlook": "Margini elevati sugli alcolici. ROI rapido se la location è in trend.",
        "legacy_bridge": "Mapping stabile, ma con controlli fiscali CoreTax molto più serrati sulle accise.",
    },
    "56302": {
        "market_sentiment": "Beach Clubs a Uluwatu e Nuanu dominano la scena. Esperienza immersiva obbligatoria.",
        "bali_nuance": "Necessità di coordinamento con le autorità locali per grandi eventi. Gestione flussi traffico.",
        "operational_risks": "Tassa intrattenimento (Pajak Hiburan) 40-75% - impatto massiccio sui margini netti.",
        "investment_outlook": "ROI potenziale altissimo, ma rischio politico e normativo elevato.",
        "legacy_bridge": "Nightclub/Discoteca. Ora integrato con le nuove regole regionali sulla tassazione del divertimento.",
    },
}


async def sync_postgres():
    pool = await asyncpg.create_pool(settings.database_url)
    for code, intel in HOSPITALITY_DATA.items():
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
                        "source": "Gemini 3 PRO Deep Research - Section I Final",
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
        if code in HOSPITALITY_DATA:
            item["intel_2026"] = HOSPITALITY_DATA[code]
            updated += 1
    with open(data_path, "w") as f:
        json.dump(full_data, f, indent=2)
    logger.info(f"✅ [JSON] Updated {updated} codes in KBLI_2025_FINAL_CLEAN.json")


async def main():
    await sync_postgres()
    sync_json()
    logger.info("🏁 HOSPITALITY SYNC COMPLETE.")


if __name__ == "__main__":
    asyncio.run(main())
