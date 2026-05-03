#!/usr/bin/env python3
"""Seed Neo4j with 18 Kanim Ngurah Rai officials + structure."""

import asyncio
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from osint_nexus.graph.loader import GraphLoader
from osint_nexus.graph.schema import init_schema


# ── Kantor Imigrasi ──
OFFICES = [
    {"name": "Kanim Kelas I Khusus TPI Ngurah Rai", "kota": "Badung", "tipe": "Kelas I Khusus TPI",
     "alamat": "Jl. Perum Taman Jimbaran No. 1, Kuta Selatan, Badung, Bali 80361"},
    {"name": "Kanwil Ditjen Imigrasi Bali", "kota": "Denpasar", "tipe": "Kanwil"},
    {"name": "Kanwil Kemenkum Bali", "kota": "Denpasar", "tipe": "Kanwil"},
]

# ── Officials ──
OFFICIALS = [
    # Superiori
    {
        "name": "Felucia Sengky Ratna",
        "jabatan": "Kakanwil Ditjen Imigrasi Bali",
        "kantor": "Kanwil Ditjen Imigrasi Bali",
        "source": "manual_seed",
    },
    {
        "name": "Eem Nurmanah",
        "jabatan": "Kakanwil Kemenkum Bali",
        "kantor": "Kanwil Kemenkum Bali",
        "source": "manual_seed",
    },
    # Kepala Kantor
    {
        "name": "Bugie Kurniawan",
        "nip": "197911252000021001",
        "jabatan": "Kepala Kantor",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "pangkat": "Pembina IV/a",
        "ttl": "Selat Panjang, 25/11/1979",
        "angkatan": "2000",
        "source": "manual_seed",
    },
    # Bagian Tata Usaha
    {
        "name": "Rachmad Akbar",
        "jabatan": "Kabag Tata Usaha",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    {
        "name": "Angga Ingward Lyman Allagan",
        "jabatan": "Kasubbag Kepegawaian & Umum",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    {
        "name": "Ni Ketut Nuriatini",
        "jabatan": "Kasubbag Keuangan",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    # Bidang Inteldakim (TARGET PRIMARIO)
    {
        "name": "Raja Ulul Azmi Syahwali",
        "nip": "198003122000021001",
        "jabatan": "Kabid Inteldakim",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "asal": "Melayu Riau (Kerajaan Indragiri)",
        "angkatan": "2000",
        "source": "manual_seed",
    },
    {
        "name": "Iman Warih Wijaya Waskito",
        "nip": "199004252017121001",
        "jabatan": "Kasi Intelijen",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    {
        "name": "Andy Oki Wijaya",
        "jabatan": "Kasi Penindakan",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    # Bidang Dokulintalkim
    {
        "name": "Bernardus Khrisna Septa Febrian",
        "jabatan": "Kabid Dokulintalkim",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    {
        "name": "Ni Made Putri Kartika Jati",
        "jabatan": "Kasi Dokumen Perjalanan",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    {
        "name": "Fajar Yulianto",
        "jabatan": "Kasi Izin Tinggal",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    # Bidang TIK
    {
        "name": "Ferry Tri Ardhiansyah",
        "jabatan": "Kabid TIK",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    {
        "name": "Saiful Basyir",
        "jabatan": "Kasi TI",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    {
        "name": "Husnan Handano",
        "jabatan": "Kasi Infokom",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    # Bidang TPI
    {
        "name": "Gde Oki Rizky Aryadhika Heris",
        "jabatan": "Kabid TPI",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    {
        "name": "Andre Wilson",
        "jabatan": "Kasi Pemeriksaan I",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    {
        "name": "Ferdian Ade Cecar Tarigan",
        "jabatan": "Kasi Pemeriksaan II",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    {
        "name": "Muhammad Teguh Santoso",
        "jabatan": "Kasi Pemeriksaan III",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
    {
        "name": "Ardyansah",
        "jabatan": "Kasi Pemeriksaan IV",
        "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai",
        "source": "manual_seed",
    },
]

# ── Relationships ──
RELATIONSHIPS = [
    # Officials → Offices (WORKS_AT)
    *[
        {"from": o["name"], "from_label": "Official", "to": o["kantor"],
         "to_label": "Kanim_Office", "rel": "WORKS_AT", "props": {"jabatan": o["jabatan"]}}
        for o in OFFICIALS if o.get("kantor")
    ],
    # Angkatan link: Bugie + Raja both 2000
    {
        "from": "Bugie Kurniawan", "from_label": "Official",
        "to": "Raja Ulul Azmi Syahwali", "to_label": "Official",
        "rel": "ALUMNI", "props": {"angkatan": "2000", "confidence": "suspected"},
    },
    # Hierarchy: Kakanwil → Kakanim
    {
        "from": "Felucia Sengky Ratna", "from_label": "Official",
        "to": "Bugie Kurniawan", "to_label": "Official",
        "rel": "SUPERVISES", "props": {},
    },
    # Possible family link: Raja → Ahmad Juan Syahwali
    {
        "from": "Raja Ulul Azmi Syahwali", "from_label": "Official",
        "to": "Ahmad Juan Syahwali", "to_label": "Person",
        "rel": "PARENT_OF", "props": {"confidence": "suspected", "source": "social_media"},
    },
]

# Person nodes needed for relationships
PERSONS = [
    {"name": "Ahmad Juan Syahwali", "person_type": "family", "notes": "Possible son of Raja. UBD Palembang, IG @juanssssy, esport PUBG"},
]

# Historical Kakanim
HISTORICAL = [
    {"name": "Winarko", "jabatan": "Kepala Kantor (2025-2026)", "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai", "source": "historical"},
    {"name": "Suhendra", "jabatan": "Kepala Kantor (2023-2025)", "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai", "source": "historical"},
    {"name": "Gilang Danurdara", "jabatan": "Kabid Inteldakim (2022-2024)", "kantor": "Kanim Kelas I Khusus TPI Ngurah Rai", "source": "historical"},
]


async def main():
    loader = GraphLoader()

    if not await loader.verify_connectivity():
        print("❌ Cannot connect to Neo4j. Start it first:")
        print("   docker compose -f apps/osint-nexus/docker-compose.yml up -d")
        return

    # Init schema
    from neo4j import AsyncGraphDatabase
    from osint_nexus.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    await init_schema(driver)
    await driver.close()
    print("✅ Schema initialized")

    # Load offices
    for office in OFFICES:
        await loader.upsert_office(office)
    print(f"✅ {len(OFFICES)} offices loaded")

    # Load officials
    for official in OFFICIALS:
        await loader.upsert_official(official)
    print(f"✅ {len(OFFICIALS)} officials loaded")

    # Load persons
    for person in PERSONS:
        await loader.upsert_person(person)
    print(f"✅ {len(PERSONS)} persons loaded")

    # Load historical
    for hist in HISTORICAL:
        await loader.upsert_official(hist)
    print(f"✅ {len(HISTORICAL)} historical officials loaded")

    # Create relationships
    for rel in RELATIONSHIPS:
        # Ensure target person exists
        if rel["to_label"] == "Person":
            await loader.upsert_person({"name": rel["to"], "person_type": "unknown"})
        await loader.create_relationship(
            from_name=rel["from"],
            from_label=rel["from_label"],
            to_name=rel["to"],
            to_label=rel["to_label"],
            rel_type=rel["rel"],
            properties=rel.get("props"),
        )
    print(f"✅ {len(RELATIONSHIPS)} relationships created")

    # Stats
    counts = await loader.get_node_count()
    print("\n📊 Graph stats:")
    total = 0
    for label, count in counts.items():
        print(f"   {label}: {count}")
        total += count
    print(f"   TOTAL: {total}")

    await loader.close()
    print("\n✅ Seed complete!")


if __name__ == "__main__":
    asyncio.run(main())
