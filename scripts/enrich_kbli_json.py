import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JSON-Enricher")

DATA_PATH = Path("source_documents/KBLI_2025_FINAL_CLEAN.json")

# Dati di ricerca consolidati per il Batch 1 & 2
RESEARCH_DATA = {
    "46100": {
        "market_sentiment": "Ideale per l'economia digitale B2B. Bassi requisiti di capitale circolante operativo. Focus su piattaforme agritech e drop-shipping industriale.",
        "bali_nuance": "Intermediazione digitale tra coltivatori rurali e hotel di lusso. Gestione flussi dati filiera corta.",
        "operational_risks": "Assenza totale di proprietà necessaria per evitare sanzioni OSS. Riconciliazione commissioni sotto CoreTax.",
        "investment_outlook": "Alta scalabilità, rischio inventario zero. ROI guidato dall'automazione AI del matching domanda-offerta.",
        "legacy_bridge": "Corrisponde alla logica di intermediazione pura del 2020, ora più rigida nella separazione dal possesso fisico."
    },
    "46201": {
        "market_sentiment": "Settore strategico per sicurezza alimentare (Sembako). Margini compressi da prezzi massimi (HET) e intervento BULOG.",
        "bali_nuance": "Dipendenza totale da Giava per riso e cereali causa erosione Green Zones.",
        "operational_risks": "Colli di bottiglia a Gilimanuk. Necessità di silos e stoccaggio pesante.",
        "investment_outlook": "Bassi margini unitari, profitto basato esclusivamente su economie di scala astronomiche e volumi.",
        "legacy_bridge": "Migrazione stabile dal 2020, ma con controlli fiscali CoreTax raddoppiati sulle giacenze."
    },
    "46203": {
        "market_sentiment": "Esplosione della domanda per design scultoreo botanico. Trend 'Regency Revival' e palette 'Faded Petal'.",
        "bali_nuance": "Mercato nuziale ed eventi di Bali 2026. Richiede serre climatizzate vicine alle Pink Zones.",
        "operational_risks": "Estrema deperibilità. Necessità di catena del freddo impeccabile.",
        "investment_outlook": "ROI Eccezionale per 'Smart Luxury'. Clientela insensibile al prezzo.",
        "legacy_bridge": "Evoluzione del vecchio commercio fiori, ora iper-specializzato."
    },
    "46511": {
        "market_sentiment": "Modello Hardware-as-a-Service (HaaS) in ascesa. Domanda di workstation per creatori e infrastrutture mesh.",
        "bali_nuance": "Focus su coworking spaces e ville di lusso. Esigenza di connettività ininterrotta.",
        "operational_risks": "Separazione obbligatoria dai servizi cloud (Cat J). Restrizioni import marchi non registrati.",
        "investment_outlook": "Margini sani su leasing B2B. Trasformazione CAPEX in OPEX per sviluppatori.",
        "legacy_bridge": "Focalizzato solo sull'hardware fisico, scorporato dai servizi IT post-2025."
    },
    "46512": {
        "market_sentiment": "Boom di Property Management Systems (PMS) e Channel Managers integrati API con Airbnb/Booking.",
        "bali_nuance": "Domanda massiccia da parte di ville e ristoranti per software gestionali e POS.",
        "operational_risks": "Gestione IVA (PMSE) per piattaforme estere. Rischio doppia imposizione.",
        "investment_outlook": "Margini elevati (15-25%). ROI guidato da servizi di formazione e supporto in loco.",
        "legacy_bridge": "Software 'off-the-shelf', ora distinto dallo sviluppo custom (Cat K)."
    }
}

def enrich_json():
    if not DATA_PATH.exists():
        logger.error(f"File not found: {DATA_PATH}")
        return

    with open(DATA_PATH, 'r') as f:
        full_data = json.load(f)

    updated_count = 0
    for item in full_data['data']:
        code = item.get('kode_kbli_2025')
        if code in RESEARCH_DATA:
            item['intel_2026'] = RESEARCH_DATA[code]
            updated_count += 1
            logger.info(f"✅ Enriched KBLI {code} in JSON")

    if updated_count > 0:
        with open(DATA_PATH, 'w') as f:
            json.dump(full_data, f, indent=2)
        logger.info(f"🏁 JSON enrichment complete. Updated {updated_count} codes.")
    else:
        logger.warning("No matches found to update.")

if __name__ == "__main__":
    enrich_json()
