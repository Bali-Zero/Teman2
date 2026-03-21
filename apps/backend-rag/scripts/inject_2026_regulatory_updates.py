import asyncio
import json
import os

import asyncpg

# Database connection from environment or default local
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://nuzantara:nuzantara_local_2024@localhost:5432/nuzantara"
)


async def run():
    print("🚀 Injecting March 2026 Regulatory Intelligence into Knowledge Graph...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    # 1. PERDA 4/2026 - Rice Field Criminalization (LP2B)
    # Impacted sectors: Villa accommodation, Real estate, Construction
    lp2b_sectors = ["55111", "55112", "55113", "55191", "68111", "68112", "41011", "41012"]

    # 2. REGULATION 49/2025 - Corporate Reporting Mandate
    # Impacted sectors: All PT PMAs (we target core ones)
    compliance_sectors = ["70209", "62019", "63122", "47911", "74902", "70201"]

    async def inject_intelligence(codes, group_name, alert_msg, risk_level="high"):
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

                # Update with 2026 Intelligence
                props["expert_legal"]["regulatory_update_2026"] = {
                    "source": group_name,
                    "alert": alert_msg,
                    "risk_level": risk_level,
                    "last_sync": "2026-03-15",
                }

                # Append to existing alerts if any
                existing_alert = props["expert_legal"].get("bali_alert", "")
                if alert_msg not in existing_alert:
                    combined = f"{existing_alert} | [MARCH 2026 UPDATE]: {alert_msg}"
                    props["expert_legal"]["bali_alert"] = combined.lstrip(" | ").rstrip(" | ")

                await conn.execute(
                    "UPDATE kg_nodes SET properties = $1 WHERE entity_id = $2",
                    json.dumps(props),
                    entity_id,
                )
                print(f"✅ 2026 Intelligence injected for {entity_id}")
            else:
                # Create node if missing
                await conn.execute(
                    "INSERT INTO kg_nodes (entity_id, entity_type, name, properties) VALUES ($1, $2, $3, $4)",
                    entity_id,
                    "kbli",
                    f"KBLI {code}",
                    json.dumps(
                        {
                            "kode": code,
                            "expert_legal": {
                                "regulatory_update_2026": {
                                    "source": group_name,
                                    "alert": alert_msg,
                                    "risk_level": risk_level,
                                    "last_sync": "2026-03-15",
                                },
                                "bali_alert": f"[MARCH 2026 UPDATE]: {alert_msg}",
                            },
                        }
                    ),
                )
                print(f"🆕 Created and injected 2026 data for {entity_id}")

    # Perda 4/2026 Alert
    await inject_intelligence(
        lp2b_sectors,
        "Perda 4/2026 (Bali LP2B)",
        "CRITICAL: Building on protected rice fields (LP2B) is now a criminal offense with jail time. Strict zoning audit mandatory before purchase.",
        "critical",
    )

    # Regulation 49/2025 Alert
    await inject_intelligence(
        compliance_sectors,
        "Regulation 49/2025 (Annual Reporting)",
        "COMPLIANCE ALERT: Notarized Annual Reports (GMS) are now mandatory via SABH. Failure to file triggers NIB suspension.",
        "high",
    )

    await conn.close()
    print("✨ Sync complete. Zantara RAG is now aware of March 2026 regulatory shifts.")


if __name__ == "__main__":
    asyncio.run(run())
