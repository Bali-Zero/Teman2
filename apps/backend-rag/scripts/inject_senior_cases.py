import asyncio
import json

import asyncpg


async def run():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    case_studies = [
        {
            "id": "case:restaurant_alcohol_online",
            "title": "Ristorante con E-commerce di Alcolici",
            "codes": ["56101", "47221"],
            "solution": "Rischio Alto. Richiede KBLI 47221 aggiuntivo. A Bali, moratoria INGUB 6/2025 blocca nuove licenze retail per catene. Obbligo SKP e distanze da scuole/templi.",
        },
        {
            "id": "case:coffee_shop_roasting",
            "title": "Coffee Shop con Torrefazione Industriale",
            "codes": ["56303", "10761", "46314"],
            "solution": "Separazione obbligatoria tra servizio (56303) e industria (10761). Per PMA straniera: investimento 10B IDR PER OGNI CODICE (Totale 20B+). Richiede BPOM e Halal.",
        },
        {
            "id": "case:villa_booking_platform",
            "title": "Piattaforma App Prenotazione Ville",
            "codes": ["55400", "62191"],
            "solution": "Usa KBLI 55400 (Intermediazione). Obbligatoria registrazione PSE Lingkup Privat (PP 28/2025 Pasal 186). Capitale PMA 10B IDR.",
        },
        {
            "id": "case:construction_material_wholesale",
            "title": "Costruttore che Vende Materiali Edili",
            "codes": ["41011", "46631"],
            "solution": "Capitale doppio (20B IDR) richiesto per PMA. Il 41011 richiede SBU (Sertifikat Badan Usaha). L'importazione acciaio richiede API integrato nel NIB.",
        },
        {
            "id": "case:aesthetic_clinic_cosmetics",
            "title": "Clinica Estetica con Vendita Creme",
            "codes": ["86201", "47723"],
            "solution": "La vendita di cosmetici propri richiede Notifica BPOM. Se aperta al pubblico consumer, serve KBLI retail 477xx separato.",
        },
        {
            "id": "case:glamping_forest",
            "title": "Glamping nella Foresta",
            "codes": ["55209"],
            "solution": "Usa 55209, non Hotel. Controllo KKPR (Pasal 6 PP 28/2025) è bloccante in zone forestali. Obbligo UKL-UPL ambientale.",
        },
        {
            "id": "case:crypto_trading_exchange",
            "title": "Trading e Exchange Criptovalute",
            "codes": ["66113", "66123"],
            "solution": "Rischio Alto. Richiede licenza Bappebti, PSE e certificazione ISO 27001 (Cybersecurity).",
        },
        {
            "id": "case:street_food_chain_bali",
            "title": "Catena di Street Food a Bali",
            "codes": ["56102"],
            "solution": "Bloccata a Bali da INGUB 6/2025 se operata come 'Toko Modern Berjejaring' (franchising/catena) per proteggere UMKM locali.",
        },
        {
            "id": "case:travel_agency_umrah",
            "title": "Agenzia Viaggi con Servizi Umrah",
            "codes": ["79110", "79122"],
            "solution": "Richiede codice 79122 specifico (Rischio Alto). Izin dal Ministero della Religione obbligatoria. Richiesta operatività pregressa di 1 anno.",
        },
        {
            "id": "case:furniture_factory_showroom",
            "title": "Fabbrica Mobili con Showroom Retail",
            "codes": ["31011", "47591"],
            "solution": "Possibile nello stesso edificio solo se la zonizzazione (RDTR) è 'Mista' o 'Commerciale'. Rischio rifiuto NIB se zona è solo 'Industriale Pura'.",
        },
    ]

    for case in case_studies:
        entity_id = case["id"]
        sql = """
            INSERT INTO kg_nodes (entity_id, entity_type, name, description, properties)
            VALUES ($1, 'case_study', $2, $3, $4)
            ON CONFLICT (entity_id) DO UPDATE SET properties = EXCLUDED.properties
        """
        props = {
            "related_kbli": case["codes"],
            "legal_solution": case["solution"],
            "source": "Zantara Senior Legal Analysis 2025",
            "regulations": ["PP 28/2025", "BPS 7/2025", "INGUB 6/2025"],
        }
        await conn.execute(sql, entity_id, case["title"], case["solution"], json.dumps(props))
        print(f"✅ Caso Studio Iniettato: {case['title']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
