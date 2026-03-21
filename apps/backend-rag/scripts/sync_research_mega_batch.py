import asyncio
import json
import logging
import time
from pathlib import Path

import asyncpg

from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Nuzantara-Total-Sync")

# DATA_SOURCE: Intelligence Strategica 2026 fornita da Zero
MEGA_INTELLIGENCE = {
    # --- AGRI & INTERMEDIATION (461, 462) ---
    "46100": {
        "market_sentiment": "Infrastruttura ideale per piattaforme B2B e agritech. Capitale circolante basso. Focus su intermediazione digitale.",
        "bali_nuance": "Intermediazione tra agricoltori e hotel di lusso. Focus su logistica dati e filiera corta.",
        "operational_risks": "Assenza totale di proprietà obbligatoria per conformità. Audit CoreTax su commissioni.",
        "investment_outlook": "Alta scalabilità, rischio inventario zero. ROI guidato da automazione AI.",
        "legacy_bridge": "Intermediazione pura 2020, ora più restrittiva nel portale OSS.",
    },
    "46201": {
        "market_sentiment": "Sicurezza alimentare (Sembako). Margini compressi da prezzi massimi (HET) e intervento BULOG.",
        "bali_nuance": "Dipendenza totale da Giava per riso causa erosione Green Zones in favore del turismo.",
        "operational_risks": "Colli di bottiglia a Gilimanuk. Necessità di vasti silos e infrastrutture di stoccaggio.",
        "investment_outlook": "Margini minimi, profitto basato esclusivamente su volumi astronomici.",
        "legacy_bridge": "Mapping diretto dal 2020, ma con controlli fiscali CoreTax raddoppiati sulle giacenze.",
    },
    "46203": {
        "market_sentiment": "Boom 'Regency Revival' e palette 'Faded Petal'. Domanda esplosiva per design scultoreo botanico.",
        "bali_nuance": "Mercato nuziale ed eventi di Bali 2026. Richiede serre climatizzate vicine ai distretti alberghieri.",
        "operational_risks": "Estrema deperibilità. Necessità di catena del freddo impeccabile per trasporti locali.",
        "investment_outlook": "ROI Eccezionale per 'Smart Luxury'. Clientela insensibile al prezzo.",
        "legacy_bridge": "Specializzazione del commercio botanico per il settore benessere e lusso.",
    },
    "46206": {
        "market_sentiment": "Leader globale export pesci ornamentali. Settore in rapida ascesa mondiale.",
        "bali_nuance": "Hub a Denpasar vicino a Ngurah Rai. Successo legato alla logistica aerea per export.",
        "operational_risks": "Mortalità >30% se non gestiti con stazioni di quarantena hi-tech e bioseurezza BKI 2025.",
        "investment_outlook": "Molto alto per chi certifica tracciabilità etica richiesta dai mercati occidentali.",
        "legacy_bridge": "Solo vita acquatica ornamentale, tassativamente esclusa la destinazione alimentare.",
    },
    "46207": {
        "market_sentiment": "Boom 'Bamboo-Core' e bio-edilizia. Sostituzione cemento con materiali bio-sostenibili.",
        "bali_nuance": "Materiali vitali per eco-resort. Domanda inelastica per bambù ingegnerizzato a Bali e Lombok.",
        "operational_risks": "Interruzioni logistiche stagionali (Pelni/ASDP). SVLK obbligatorio per commercio interno.",
        "investment_outlook": "Redditività solida garantita dai contractor immobiliari di lusso (KBLI 41013).",
        "legacy_bridge": "Punto di unione per l'intera filiera del legname nobile e sostenibile.",
    },
    "46209": {
        "market_sentiment": "Motore economia circolare. Trading di biomassa (PKS) per centrali bioenergetiche.",
        "bali_nuance": "Export di gusci di palmisto verso Giappone/Corea per utility bioenergetiche.",
        "operational_risks": "Logistica scarti voluminosi. Requisiti di tracciabilità dell'origine.",
        "investment_outlook": "Margini elevati per contratti pluriennali con partner esteri.",
        "legacy_bridge": "Categoria residuale trasformata in pilastro della macroeconomia circolare.",
    },
    # --- TECH & INDUSTRIAL (465, 466) ---
    "46511": {
        "market_sentiment": "Modello Hardware-as-a-Service (HaaS) in ascesa. Workstation per creatori e infrastrutture mesh.",
        "bali_nuance": "Focus su coworking spaces e ville di lusso. Esigenza connettività ininterrotta.",
        "operational_risks": "Separazione obbligatoria dai servizi cloud (Cat J). Restrizioni import marchi non registrati.",
        "investment_outlook": "Margini sani su leasing B2B. Trasformazione CAPEX in OPEX per sviluppatori.",
        "legacy_bridge": "Focalizzato solo hardware fisico, scorporato dai servizi IT post-2025.",
    },
    "46512": {
        "market_sentiment": "Boom sistemi PMS e Channel Managers integrati API con Airbnb/Booking.",
        "bali_nuance": "Domanda massiccia da ville e ristoranti per software gestionali e POS.",
        "operational_risks": "Gestione IVA (PMSE) per piattaforme estere. Rischio doppia imposizione sotto CoreTax.",
        "investment_outlook": "Margini elevati (15-25%). ROI guidato da formazione e supporto tecnico.",
        "legacy_bridge": "Software 'off-the-shelf', ora distinto dallo sviluppo custom (Cat K).",
    },
    "46523": {
        "market_sentiment": "Esplosione ricevitori satellitari (Starlink) e ripetitori enterprise per zone d'ombra.",
        "bali_nuance": "Connettività vitale per ville a Uluwatu e Nusa Penida.",
        "operational_risks": "Blocco IMEI tramite sistema CEIR. Regole TKDN bloccano apparati 5G stranieri.",
        "investment_outlook": "Alto per chi distribuisce marchi già omologati o nicchie hardware esenti TKDN.",
        "legacy_bridge": "Distaccato dal vecchio codice composito per isolare le apparati di trasmissione.",
    },
    "46631": {
        "market_sentiment": "Codice critico boom edilizio. Domanda tondini SNI e legname Teak/Ulin.",
        "bali_nuance": "Consumo colossale per ville a Canggu. Estorsioni informali (Banjar fees) da gestire.",
        "operational_risks": "Applicazione rigorosa SVLK. Sequestri su strada per carichi non tracciabili.",
        "investment_outlook": "Fornitore compliance-first per sviluppatori stranieri. ROI protetto da certificazioni.",
        "legacy_bridge": "Affinamento classificazione materiali per isolare i metalli strutturali.",
    },
    # --- HEALTH & BEAUTY (464xx) ---
    "46443": {
        "market_sentiment": "Settore 'Smarter Spending'. Boom Men's Grooming e skincare vegana. Obbligo Halal 2026.",
        "bali_nuance": "Mercato premium Uluwatu/Canggu. Domanda di cosmeceutici professionali per cliniche boutique.",
        "operational_risks": "Muro dell'Halal Ottobre 2026. Registrazione BPOM per ogni referenza obbligatoria.",
        "investment_outlook": "Ricarico B2B del 20-30% per chi assorbe i costi di compliance e certificazione.",
        "legacy_bridge": "Include ora il riconoscimento formale dei Factoryless Goods Producers (FGP).",
    },
    "46444": {
        "market_sentiment": "Hub Sanur Health SEZ crea polo di attrazione per attrezzature diagnostiche hi-tech.",
        "bali_nuance": "Polo attrazione turismo medico (chirurgia estetica, staminali). Regulatory sandbox a Sanur.",
        "operational_risks": "Licenza IPAK (45 giorni). Garanzie assistenza post-vendita documentate richieste.",
        "investment_outlook": "Margini 20-40% per alta tecnologia medica importata interamente.",
        "legacy_bridge": "Allineamento ISIC Rev 5 per isolare i dispositivi medici dagli strumenti generici.",
    },
}


async def sync_postgres():
    pool = await asyncpg.create_pool(settings.database_url)
    logger.info("Connecting to PostgreSQL for symmetric enrichment...")
    for code, intel in MEGA_INTELLIGENCE.items():
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
                        "source": "Gemini 3 PRO Deep Research",
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
        if code in MEGA_INTELLIGENCE:
            item["intel_2026"] = MEGA_INTELLIGENCE[code]
            updated += 1

    with open(data_path, "w") as f:
        json.dump(full_data, f, indent=2)
    logger.info(f"✅ [JSON] Updated {updated} codes in KBLI_2025_FINAL_CLEAN.json")


async def main():
    await sync_postgres()
    sync_json()
    logger.info("🏁 TOTAL SYNC COMPLETE.")


if __name__ == "__main__":
    asyncio.run(main())
