import asyncio
import json

import asyncpg


async def run():
    conn = await asyncpg.connect(
        "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
    )

    # 1. ZONA ROSSA (Moratoria Bali INGUB 6/2025)
    red_zone = ["47111", "47112", "47191", "47192", "47221", "47711", "56102"]

    # 2. TRAPPOLA UMKM (Vietati PMA)
    umkm_trap = ["55201", "13133", "47811", "47812", "47813", "01131", "96210", "10792", "56306"]

    # 3. HIGH STAKES (PMA > 10B IDR)
    high_stakes = [
        "55101",
        "55203",
        "56101",
        "56301",
        "56302",
        "56303",
        "68111",
        "68112",
        "68210",
        "41011",
        "41017",
        "96101",
        "86103",
        "85491",
        "85492",
    ]

    # 4. TECH & NEW ECONOMY (Virtual Office Allowed)
    tech_economy = ["62019", "62194", "63122", "70209", "74201", "64995", "66123"]

    # 5. TERTUTUP (Closed / Blacklist)
    closed_sectors = ["92000", "11031", "01285", "32401"]

    async def update_group(codes, group_name, alert_msg, pma_status_override=None):
        for code in codes:
            entity_id = f"kbli:{code}"
            row = await conn.fetchrow(
                "SELECT properties FROM kg_nodes WHERE entity_id = $1", entity_id
            )
            if row:
                props = (
                    json.loads(row["properties"])
                    if isinstance(row["properties"], str)
                    else row["properties"]
                )
                if "expert_legal" not in props:
                    props["expert_legal"] = {}

                props["expert_legal"]["strategic_group"] = group_name
                props["expert_legal"]["bali_alert"] = alert_msg
                if pma_status_override:
                    props["pma_status"] = pma_status_override

                await conn.execute(
                    "UPDATE kg_nodes SET properties = $1 WHERE entity_id = $2",
                    json.dumps(props),
                    entity_id,
                )
                print(f"✅ Intelligence Iniettata per {entity_id} ({group_name})")
            else:
                # Se il codice non esiste ancora, lo creiamo con i dati minimi
                await conn.execute(
                    "INSERT INTO kg_nodes (entity_id, entity_type, name, properties) VALUES ($1, $2, $3, $4)",
                    entity_id,
                    "kbli",
                    f"KBLI {code}",
                    json.dumps(
                        {
                            "kode": code,
                            "expert_legal": {
                                "strategic_group": group_name,
                                "bali_alert": alert_msg,
                            },
                            "pma_status": pma_status_override or "UNKNOWN",
                        }
                    ),
                )
                print(f"🆕 Creato e Iniettato {entity_id} ({group_name})")

    # Esecuzione aggiornamenti
    await update_group(
        red_zone,
        "Zona Rossa Bali",
        "⚠️ MORATORIA ATTIVA (INGUB 6/2025): Nuove licenze per retail/catene sospese a Bali.",
    )
    await update_group(
        umkm_trap,
        "Trappola UMKM",
        "🚫 RISERVATO LOCALI: Questo codice è limitato alle Micro/Piccole imprese. Vietato alle PMA stranieri.",
        "RESERVAT_LOCALS",
    )
    await update_group(
        high_stakes,
        "High Stakes PMA",
        "💰 INVESTIMENTO MASSICCIO: Richiesto capitale versato min. 10 Miliardi IDR per investitori stranieri.",
    )
    await update_group(
        tech_economy,
        "Tech & Consulting",
        "🌐 VIRTUAL OFFICE ALLOWED: Ideale per startup digitali e consulenti. Possibilità di registrazione presso uffici virtuali accreditati.",
    )
    await update_group(
        closed_sectors,
        "Settore Chiuso",
        "❌ BLACKLIST TOTALE: Attività proibita in Indonesia o completamente chiusa agli investimenti privati/stranieri.",
        "TERTUTUP",
    )

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
