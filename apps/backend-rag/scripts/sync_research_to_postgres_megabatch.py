import asyncio
import logging

from backend.services.knowledge_graph.kbli_enricher_symmetric import KBLIEnricher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Postgres-Sync-MegaBatch")

# Mappatura dell'Intelligence Strategica estratta dai report di Zero
MEGA_RESEARCH_DATA = {
    # --- TECH & INDUSTRIAL (465xx, 466xx) ---
    "46511": {
        "market_sentiment_2026": "Modello Hardware-as-a-Service (HaaS) in ascesa. Domanda di workstation per creatori e infrastrutture mesh.",
        "bali_nuance": "Focus su coworking spaces e ville di lusso. Esigenza di connettività ininterrotta.",
        "operational_hurdles": "Separazione obbligatoria dai servizi cloud (Cat J). Restrizioni import marchi non registrati.",
        "strategic_roi": "Margini sani su leasing B2B. Trasformazione CAPEX in OPEX per sviluppatori.",
        "legacy_bridge": "Focalizzato solo sull'hardware fisico, scorporato dai servizi IT post-2025.",
    },
    "46512": {
        "market_sentiment_2026": "Boom di Property Management Systems (PMS) e Channel Managers integrati API con Airbnb/Booking.",
        "bali_nuance": "Domanda massiccia da parte di ville e ristoranti per software gestionali e POS.",
        "operational_hurdles": "Gestione IVA (PMSE) per piattaforme estere. Rischio doppia imposizione.",
        "strategic_roi": "Margini elevati (15-25%). ROI guidato da servizi di formazione e supporto in loco.",
        "legacy_bridge": "Software 'off-the-shelf', ora distinto dallo sviluppo custom (Cat K).",
    },
    "46521": {
        "market_sentiment_2026": "Cultura del 'Right to Repair'. Hub di riparazione elettronica a Denpasar estremamente redditizio.",
        "bali_nuance": "Domanda di componenti per smartphone e workstation per la comunità expat.",
        "operational_hurdles": "Monitoraggio stretto Bea Cukai (dogane). Tracciabilità totale tra PIB e vendite domestiche.",
        "strategic_roi": "Opportunità nella creazione di filiere legali per centri riparazione indipendenti.",
        "legacy_bridge": "Affidamento della definizione: focus esclusivo su microchip e semiconduttori.",
    },
    "46523": {
        "market_sentiment_2026": "Esplosione dei ricevitori satellitari (Starlink) e ripetitori enterprise per zone d'ombra.",
        "bali_nuance": "Connettività vitale per le ville a Uluwatu e Nusa Penida.",
        "operational_hurdles": "Blocco IMEI tramite sistema CEIR. Regole TKDN (Contenuto Locale) bloccano apparati 5G stranieri.",
        "strategic_roi": "Alto per chi distribuisce marchi già omologati o nicchie hardware non soggette a TKDN.",
        "legacy_bridge": "Distaccato dal vecchio codice composito per isolare le apparati di trasmissione.",
    },
    "46530": {
        "market_sentiment_2026": "Rivoluzione AgriTech su piccola scala. Droni per irrorazione e sensori IoT.",
        "bali_nuance": "Focus su Bedugul e Kintamani per rifornire la ristorazione 'farm-to-table'.",
        "operational_hurdles": "Costi iniziali elevati e frammentazione dei terreni agricoli balinesi.",
        "strategic_roi": "Modelli B2B diretti con cooperative e catene alberghiere che creano filiere proprie.",
        "legacy_bridge": "Aggiornamento tecnologico: include ora droni agricoli e smart irrigation.",
    },
    "46631": {
        "market_sentiment_2026": "Codice critico per il boom edilizio. Domanda di tondini SNI e legname tropicale (Teak/Ulin).",
        "bali_nuance": "Consumo colossale per ville a Canggu. Estorsioni informali (Banjar fees) erodono i margini.",
        "operational_hurdles": "Applicazione rigorosa SVLK (legalità legno). Sequestri su strada per carichi non tracciabili.",
        "strategic_roi": "Fornitore compliance-first per sviluppatori stranieri. ROI protetto dalla certificazione.",
        "legacy_bridge": "Affinamento della classificazione materiali da costruzione per isolare i metalli.",
    },
    "46632": {
        "market_sentiment_2026": "Trend architettonico di grandi facciate vetrate per fusione indoor-outdoor.",
        "bali_nuance": "Vetrate temperati/laminati ad alto isolamento acustico per il mercato del lusso.",
        "operational_hurdles": "Protezionismo LARTAS contro importazioni EU. Alti tassi di rottura nel trasporto da Giava.",
        "strategic_roi": "Margini (8-11%) legati alla garanzia di consegna integra in cantiere.",
        "legacy_bridge": "Classificazione specifica per vetro piano e temperato per costruzioni.",
    },
    # --- HEALTH, BEAUTY & LUXURY (464xx) ---
    "46441": {
        "market_sentiment_2026": "Forniture istituzionali stabili (BPJS) e farmaci OTC in crescita tramite marketing D2C.",
        "bali_nuance": "Catalizzatore Sanur Health SEZ. Domanda di farmaci per medicina estetica e oncologia.",
        "operational_hurdles": "Licenza CDOB obbligatoria. Richiede farmacista responsabile a tempo pieno.",
        "strategic_roi": "Margini 12-25% per generici, fino al 35% per farmaci da banco.",
        "legacy_bridge": "Consolidamento per prevenire elusione normative tramite preparati chimici.",
    },
    "46443": {
        "market_sentiment_2026": "Settore a crescita esplosiva (K-Beauty e Men's Grooming). Obbligo Halal Ottobre 2026.",
        "bali_nuance": "Mercato premium a Uluwatu/Canggu (skincare vegana, filtri solari etici).",
        "operational_hurdles": "Registrazione BPOM per ogni referenza. Scadenza certificazione Halal BPJPH è il 'muro' del 2026.",
        "strategic_roi": "Ricarico B2B del 20-30% per chi assorbe i costi di compliance.",
        "legacy_bridge": "Include ora il riconoscimento formale dei Factoryless Goods Producers (FGP).",
    },
    "46444": {
        "market_sentiment_2026": "Hub Sanur Health SEZ crea monopolio temporaneo per attrezzature diagnostiche hi-tech.",
        "bali_nuance": "Polo di attrazione per il turismo medico (chirurgia estetica, staminali).",
        "operational_hurdles": "Licenza IPAK (45 giorni). Richiede garanzie di assistenza post-vendita documentate.",
        "strategic_roi": "Margini 20-40% per alta tecnologia medica importata interamente.",
        "legacy_bridge": "Allineamento ISIC Rev 5 per isolare i dispositivi medici dagli strumenti generici.",
    },
    "46492": {
        "market_sentiment_2026": "Trend 'Athleisure' e coscienza salutistica post-pandemia. Wearables IoT.",
        "bali_nuance": "Fornitura surf-gear e yoga-wear per boutique e resort di lusso.",
        "operational_hurdles": "Dazi doganali elevati per abbigliamento tecnico importato.",
        "strategic_roi": "Molto elevato nelle enclave turistiche rispetto al mercato di massa di Jakarta.",
        "legacy_bridge": "Evoluzione verso attrezzature sportive intelligenti e eco-compatibili.",
    },
}


async def main():
    enricher = KBLIEnricher(batch_size=100, concurrency=8)
    await enricher.run_batch(MEGA_RESEARCH_DATA)


if __name__ == "__main__":
    asyncio.run(main())
