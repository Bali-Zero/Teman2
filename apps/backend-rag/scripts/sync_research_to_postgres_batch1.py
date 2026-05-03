import asyncio
import logging

from backend.services.knowledge_graph.kbli_enricher_symmetric import KBLIEnricher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Postgres-Sync")

# Dati estratti dal tuo report per il Batch 1
RESEARCH_DATA = {
    "46100": {
        "market_sentiment_2026": "Infrastruttura ideale per piattaforme B2B e agritech. Capitale circolante basso.",
        "bali_nuance": "Intermediazione tra agricoltori e hotel di lusso. Focus su logistica dati.",
        "operational_hurdles": "Rigida separazione dal possesso fisico (obbligatoria per conformità). Audit CoreTax su commissioni.",
        "strategic_roi": "Scalabilità software elevata. Rischio inventario nullo.",
        "legacy_bridge": "Intermediazione pura 2020, ora più restrittiva nel portale OSS.",
    },
    "46201": {
        "market_sentiment_2026": "Sicurezza alimentare nazionale (Sembako). Margini controllati dal governo (BULOG).",
        "bali_nuance": "Dipendenza totale da Giava per riso e cereali causa erosione Green Zones.",
        "operational_hurdles": "Colli di bottiglia a Gilimanuk. Necessità di silos e stoccaggio pesante.",
        "strategic_roi": "Economie di scala necessarie. Margini unitari minimi.",
        "legacy_bridge": "Mapping diretto dal 2020, ma con requisiti di stoccaggio più severi.",
    },
    "46203": {
        "market_sentiment_2026": "Trend 'Regency Revival'. Domanda esplosiva per piante ornamentali e design scultoreo.",
        "bali_nuance": "Hub mondiale per eventi e matrimoni. Richiede serre climatizzate vicine alle Pink Zones.",
        "operational_hurdles": "Catena del freddo critica. Estrema deperibilità dei fiori premium.",
        "strategic_roi": "ROI Eccezionale per 'Smart Luxury'. Clientela insensibile al prezzo.",
        "legacy_bridge": "Specializzazione del commercio botanico per il settore benessere e lusso.",
    },
    "46206": {
        "market_sentiment_2026": "Leader globale export pesci ornamentali (non per consumo).",
        "bali_nuance": "Centrale operativa a Denpasar vicina a Ngurah Rai per spedizioni aeree.",
        "operational_hurdles": "Mortalità >30% se non si usano stazioni di quarantena hi-tech. Regole BKI 2025.",
        "strategic_roi": "Alto per chi certifica tracciabilità etica richiesta dai mercati occidentali.",
        "legacy_bridge": "Distinzione tassativa: solo vita acquatica ornamentale, escluso il cibo.",
    },
    "46207": {
        "market_sentiment_2026": "Boom del 'Bamboo-Core'. Sostituzione del cemento con materiali bio-sostenibili.",
        "bali_nuance": "Materiali vitali per eco-resort. Domanda inelastica per bambù ingegnerizzato.",
        "operational_hurdles": "Vulnerabilità stagionale durante i monsoni per trasporti Pelni/ASDP.",
        "strategic_roi": "Solidi flussi di cassa garantiti dagli sviluppatori immobiliari di Bali e Lombok.",
        "legacy_bridge": "Punto di unione per l'intera filiera del legname nobile e sostenibile.",
    },
    "46209": {
        "market_sentiment_2026": "Motore dell'economia circolare. Trading di biomassa e scarti agricoli per energia.",
        "bali_nuance": "Export di gusci di palmisto (PKS) verso Giappone/Corea per centrali bioenergetiche.",
        "operational_hurdles": "Logistica degli scarti voluminosi. Requisiti di tracciabilità dell'origine.",
        "strategic_roi": "Margini elevati per contratti pluriennali con utility estere.",
        "legacy_bridge": "Categoria residuale trasformata in pilastro della macroeconomia circolare.",
    },
}


async def main():
    enricher = KBLIEnricher(batch_size=100, concurrency=8)
    await enricher.run_batch(RESEARCH_DATA)


if __name__ == "__main__":
    asyncio.run(main())
