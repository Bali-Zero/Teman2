"""Neo4j schema — constraints, indexes, and initialization."""

from __future__ import annotations

SCHEMA_QUERIES = [
    # ── Node Constraints (uniqueness) ──
    "CREATE CONSTRAINT person_name IF NOT EXISTS FOR (n:Person) REQUIRE n.name IS UNIQUE",
    # NIP index (not constraint — many officials have no NIP in our data)
    "CREATE INDEX official_nip IF NOT EXISTS FOR (n:Official) ON (n.nip)",
    "CREATE CONSTRAINT organization_name IF NOT EXISTS FOR (n:Organization) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT kanim_name IF NOT EXISTS FOR (n:Kanim_Office) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT vendor_name IF NOT EXISTS FOR (n:Local_Vendor) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT pma_name IF NOT EXISTS FOR (n:PMA_Company) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT notaris_name IF NOT EXISTS FOR (n:Notaris) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT tender_id IF NOT EXISTS FOR (n:Tender) REQUIRE n.kode IS UNIQUE",
    "CREATE CONSTRAINT asset_id IF NOT EXISTS FOR (n:Asset) REQUIRE n.asset_id IS UNIQUE",
    "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (n:Event) REQUIRE n.event_id IS UNIQUE",
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:Document) REQUIRE n.nomor IS UNIQUE",
    "CREATE CONSTRAINT alumni_id IF NOT EXISTS FOR (n:Alumni_Group) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT banjar_name IF NOT EXISTS FOR (n:Banjar) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT komunitas_name IF NOT EXISTS FOR (n:Komunitas) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT property_id IF NOT EXISTS FOR (n:Property) REQUIRE n.property_id IS UNIQUE",
    "CREATE CONSTRAINT vehicle_id IF NOT EXISTS FOR (n:Vehicle) REQUIRE n.vehicle_id IS UNIQUE",
    "CREATE CONSTRAINT bank_account_id IF NOT EXISTS FOR (n:BankAccount) REQUIRE n.account_id IS UNIQUE",

    # ── Indexes for query performance ──
    "CREATE INDEX official_jabatan IF NOT EXISTS FOR (n:Official) ON (n.jabatan)",
    "CREATE INDEX official_kantor IF NOT EXISTS FOR (n:Official) ON (n.kantor)",
    "CREATE INDEX official_angkatan IF NOT EXISTS FOR (n:Official) ON (n.angkatan)",
    "CREATE INDEX tender_instansi IF NOT EXISTS FOR (n:Tender) ON (n.instansi)",
    "CREATE INDEX tender_tahun IF NOT EXISTS FOR (n:Tender) ON (n.tahun)",
    "CREATE INDEX person_type IF NOT EXISTS FOR (n:Person) ON (n.person_type)",
    "CREATE INDEX property_lokasi IF NOT EXISTS FOR (n:Property) ON (n.lokasi)",
    "CREATE INDEX vehicle_merk IF NOT EXISTS FOR (n:Vehicle) ON (n.merk_model)",

    # ── Full-text search ──
    """CREATE FULLTEXT INDEX ft_person_name IF NOT EXISTS
       FOR (n:Person|Official) ON EACH [n.name]""",
    """CREATE FULLTEXT INDEX ft_org_name IF NOT EXISTS
       FOR (n:Organization|Kanim_Office|Local_Vendor|PMA_Company) ON EACH [n.name]""",
]


async def init_schema(driver) -> None:
    """Apply all schema constraints and indexes."""
    async with driver.session() as session:
        for query in SCHEMA_QUERIES:
            try:
                await session.run(query)
            except Exception as e:
                # Constraint already exists → fine
                if "already exists" not in str(e).lower():
                    raise
