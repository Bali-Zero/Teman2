"""Full pipeline: scrape → NER → resolve → load graph."""

from __future__ import annotations

import asyncio
from typing import Any

from osint_nexus.graph.loader import GraphLoader
from osint_nexus.ner.extractor import NERExtractor
from osint_nexus.resolver.entity_resolver import EntityResolver
from osint_nexus.scrapers.base import ScrapedRecord
from osint_nexus.utils.logging import get_logger

logger = get_logger("pipeline")

# Predicate → (from_label, to_label, canonical_rel_type)
# Maps NER predicates to typed graph edges. Unmapped predicates are dropped.
RELATION_SCHEMA: dict[str, tuple[str, str, str]] = {
    "JABATAN_DI":    ("Official", "Organization",  "WORKS_AT"),
    "BERTEMU":       ("Official", "Official",      "MET_WITH"),
    "MENANG_TENDER": ("Local_Vendor", "Tender",    "WON_CONTRACT"),
    "HADIR_DI":      ("Official", "Event",         "ATTENDED"),
    "KELUARGA":      ("Official", "Person",        "FAMILY_OF"),
    "ANGKATAN":      ("Official", "Alumni_Group",  "ALUMNI"),
    "MEMILIKI":      ("Official", "Asset",         "OWNS"),
    "DILAPORKAN":    ("Official", "Document",      "REPORTED_IN"),
}

# Substrings that mark a name as an organization, never a person.
ORG_KEYWORDS = (
    "kementerian", "kementrian", "direktorat", "ditjen", "badan",
    "kabinet", "kantor", "kanim", "lembaga", "institusi", "komisi",
    "polri", "kepolisian", "pemerintah",
    "ministry", "directorate", "bureau", "commission", "agency",
    "cabinet", "polytechnic",
)

# Substrings that mark a name as specifically a Kanim_Office.
KANIM_KEYWORDS = ("kanim", "kantor imigrasi", "imigrasi kelas")


def _looks_like_org(name: str) -> bool:
    low = name.lower()
    return any(kw in low for kw in ORG_KEYWORDS)


def _looks_like_kanim(name: str) -> bool:
    low = name.lower()
    return any(kw in low for kw in KANIM_KEYWORDS)


class IntelPipeline:
    """Orchestrates the full scrape → NER → resolve → graph pipeline."""

    def __init__(self) -> None:
        self.ner = NERExtractor()
        self.resolver = EntityResolver()
        self.loader = GraphLoader()

    async def process_records(self, records: list[ScrapedRecord]) -> dict[str, int]:
        """Process scraped records: NER → resolve → load entities → create edges.

        Two-phase: load all nodes first, then relations (so target nodes exist).
        Uses RELATION_SCHEMA to give each NER predicate the right edge labels.
        """
        stats = {
            "input_records": len(records),
            "entities_extracted": 0,
            "entities_resolved": 0,
            "entities_loaded": 0,
            "relations_created": 0,
            "relations_dropped": 0,
        }

        pending_relations: list[tuple[dict, str]] = []

        for record in records:
            text = self._record_to_text(record)
            if not text:
                continue

            ner_result = await self.ner.extract(text, source=record.source)

            for person in ner_result.get("persons", []):
                if not person.get("nama"):
                    continue
                stats["entities_extracted"] += 1
                self.resolver.resolve(person, entity_type="person")
                stats["entities_resolved"] += 1

            for org in ner_result.get("organizations", []):
                if not org.get("nama"):
                    continue
                stats["entities_extracted"] += 1
                self.resolver.resolve(
                    {
                        "nama": org["nama"],
                        "tipe": org.get("tipe", ""),
                        "instansi": org.get("lokasi", ""),
                    },
                    entity_type="organization",
                )
                stats["entities_resolved"] += 1

            for rel in ner_result.get("relations", []):
                if rel.get("subject") and rel.get("object"):
                    pending_relations.append((rel, record.source))

        # Phase 1: load all entities to graph
        all_entities = self.resolver.get_all()
        loaded = await self.loader.load_resolved_entities(all_entities)
        stats["entities_loaded"] = loaded

        # Phase 2: create relations using the schema mapper
        for rel, source in pending_relations:
            predicate = rel.get("predicate", "")
            mapping = RELATION_SCHEMA.get(predicate)
            if not mapping:
                stats["relations_dropped"] += 1
                continue

            from_label, to_label, canonical_rel = mapping
            subject = rel["subject"]
            obj = rel["object"]

            # Drop org-as-person noise (orgs don't WORKS_AT/ATTENDED things)
            if from_label == "Official" and _looks_like_org(subject):
                stats["relations_dropped"] += 1
                continue

            # Drop self-loops
            if subject.strip().lower() == obj.strip().lower():
                stats["relations_dropped"] += 1
                continue

            try:
                # Auto-create target node with the proper type
                if to_label == "Person":
                    if _looks_like_org(obj):
                        to_label = "Organization"
                        await self.loader.upsert_organization({"name": obj})
                    else:
                        await self.loader.upsert_person(
                            {"name": obj, "person_type": "family"}
                        )
                elif to_label == "Organization":
                    if _looks_like_kanim(obj):
                        to_label = "Kanim_Office"
                        await self.loader.upsert_office({"name": obj})
                    else:
                        await self.loader.upsert_organization({"name": obj})
                elif to_label == "Official":
                    if _looks_like_org(obj):
                        to_label = "Organization"
                        await self.loader.upsert_organization({"name": obj})
                    else:
                        await self.loader.upsert_official({"name": obj})

                await self.loader.create_relationship(
                    from_name=subject,
                    from_label=from_label,
                    to_name=obj,
                    to_label=to_label,
                    rel_type=canonical_rel,
                    properties={
                        "context": rel.get("context", ""),
                        "source": source,
                        "raw_predicate": predicate,
                    },
                )
                stats["relations_created"] += 1
            except Exception as e:
                stats["relations_dropped"] += 1
                logger.warning(
                    "Failed relation %s -[%s]-> %s: %s",
                    subject, predicate, obj, str(e)[:100],
                )

        logger.info("Pipeline stats: %s", stats)
        return stats

    def _record_to_text(self, record: ScrapedRecord) -> str:
        """Convert a ScrapedRecord to text for NER."""
        parts = []
        for key, val in record.raw_data.items():
            if isinstance(val, str) and val.strip():
                parts.append(f"{key}: {val}")
        return "\n".join(parts)

    async def close(self) -> None:
        await self.ner.close()
        await self.loader.close()


async def run_full_pipeline(
    sources: list[str], query: str, **kwargs: Any
) -> dict[str, int]:
    """Convenience function to run full pipeline.

    Args:
        sources: List of source names ['ahu', 'lhkpn', 'lpse', 'putusan', 'news', 'wiki']
        query: Search query
    """
    from osint_nexus.scrapers.ahu import AHUScraper
    from osint_nexus.scrapers.lhkpn import LHKPNScraper
    from osint_nexus.scrapers.lpse import LPSEScraper
    from osint_nexus.scrapers.news import NewsScraper
    from osint_nexus.scrapers.putusan import PutusanMAScraper
    from osint_nexus.scrapers.wiki import WikiScraper

    scraper_map = {
        "ahu": AHUScraper,
        "lhkpn": LHKPNScraper,
        "lpse": LPSEScraper,
        "putusan": PutusanMAScraper,
        "news": NewsScraper,
        "wiki": WikiScraper,
    }

    # Scrape all sources — isolate failures so one broken source doesn't kill the batch
    all_records: list[ScrapedRecord] = []
    failed_sources: list[str] = []
    for source in sources:
        if source not in scraper_map:
            logger.warning("Unknown source: %s", source)
            continue
        scraper = scraper_map[source]()
        try:
            records = await scraper.scrape(query, **kwargs)
            all_records.extend(records)
        except Exception as exc:
            logger.error("Source '%s' failed, skipping: %s", source, exc)
            failed_sources.append(source)

    logger.info("Total records scraped: %d", len(all_records))

    # Process through pipeline
    pipeline = IntelPipeline()
    try:
        stats = await pipeline.process_records(all_records)
        return stats
    finally:
        await pipeline.close()
