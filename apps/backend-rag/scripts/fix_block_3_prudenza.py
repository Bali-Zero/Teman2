import asyncio
import json

import asyncpg


async def run():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    corrections = [
        {
            "code": "70209",
            "pma_note": "TERBUKA (100%). ALLERTA OPERATIVA: Forte monitoraggio a Bali su 'fake consulting'. L'attività deve essere puramente strategica/gestionale. Vietato svolgere lavori operativi (es. vendite, gestione sito web diretta, ecc.) riservati a personale locale.",
        },
        {
            "code": "82110",
            "pma_note": "TERBUKA (100%). NOTA VIRTUAL OFFICE: L'indirizzo deve essere registrato in un edificio commerciale approvato. Le autorità di Bali verificano periodicamente l'effettiva presenza dell'azienda per il rilascio di visti aziendali.",
        },
        {
            "code": "79121",
            "pma_note": "TERBUKA (100%). REQUISITO GUIDE: È obbligatorio l'impiego di guide turistiche locali certificate indonesiane. Gli stranieri non possono operare come guide sul campo sotto questo codice.",
        },
    ]

    for item in corrections:
        entity_id = f"kbli:{item['code']}"
        row = await conn.fetchrow("SELECT properties FROM kg_nodes WHERE entity_id = $1", entity_id)
        if row:
            props = (
                json.loads(row["properties"])
                if isinstance(row["properties"], str)
                else row["properties"]
            )
            props["expert_legal"]["pma_implications"] = item["pma_note"]
            props["expert_legal"]["special_alerts"] = [
                "ZANTARA ADVISORY: Elevato rischio di ispezione a Bali per questo settore."
            ]
            await conn.execute(
                "UPDATE kg_nodes SET properties = $1 WHERE entity_id = $2",
                json.dumps(props),
                entity_id,
            )
            print(f"✅ Corretto e reso 'Prudente': {entity_id}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
