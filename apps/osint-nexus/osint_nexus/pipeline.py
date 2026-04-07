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


class IntelPipeline:
    """Orchestrates the full scrape → NER → resolve → graph pipeline."""

    def __init__(self) -> None:
        self.ner = NERExtractor()
        self.resolver = EntityResolver()
        self.loader = GraphLoader()

    async def process_records(self, records: list[ScrapedRecord]) -> dict[str, int]:
        """Process scraped records through NER → resolve → graph.

        Returns:
            Stats dict with counts.
        """
        stats = {
            "input_records": len(records),
            "entities_extracted": 0,
            "entities_resolved": 0,
            "entities_loaded": 0,
            "relations_created": 0,
        }

        for record in records:
            # Flatten raw_data to text for NER
            text = self._record_to_text(record)
            if not text:
                continue

            # NER extraction
            ner_result = await self.ner.extract(text, source=record.source)

            # Resolve persons
            for person in ner_result.get("persons", []):
                if not person.get("nama"):
                    continue
                stats["entities_extracted"] += 1
                resolved = self.resolver.resolve(person, entity_type="person")
                stats["entities_resolved"] += 1

            # Resolve organizations
            for org in ner_result.get("organizations", []):
                if not org.get("nama"):
                    continue
                stats["entities_extracted"] += 1
                self.resolver.resolve(
                    {"nama": org["nama"], "tipe": org.get("tipe", ""), "instansi": org.get("lokasi", "")},
                    entity_type="organization",
                )
                stats["entities_resolved"] += 1

            # Create relations directly
            for rel in ner_result.get("relations", []):
                if rel.get("subject") and rel.get("object"):
                    try:
                        await self.loader.create_relationship(
                            from_name=rel["subject"],
                            from_label="Official",
                            to_name=rel["object"],
                            to_label="Organization",
                            rel_type=rel.get("predicate", "RELATED_TO"),
                            properties={"context": rel.get("context", ""), "source": record.source},
                        )
                        stats["relations_created"] += 1
                    except Exception as e:
                        logger.warning("Failed to create relation: %s", e)

        # Load all resolved entities to graph
        all_entities = self.resolver.get_all()
        loaded = await self.loader.load_resolved_entities(all_entities)
        stats["entities_loaded"] = loaded

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
        sources: List of source names ['lhkpn', 'lpse', 'putusan']
        query: Search query
    """
    from osint_nexus.scrapers.lhkpn import LHKPNScraper
    from osint_nexus.scrapers.lpse import LPSEScraper
    from osint_nexus.scrapers.putusan import PutusanMAScraper

    scraper_map = {
        "lhkpn": LHKPNScraper,
        "lpse": LPSEScraper,
        "putusan": PutusanMAScraper,
    }

    # Scrape all sources
    all_records: list[ScrapedRecord] = []
    for source in sources:
        if source not in scraper_map:
            logger.warning("Unknown source: %s", source)
            continue
        scraper = scraper_map[source]()
        records = await scraper.scrape(query, **kwargs)
        all_records.extend(records)

    logger.info("Total records scraped: %d", len(all_records))

    # Process through pipeline
    pipeline = IntelPipeline()
    try:
        stats = await pipeline.process_records(all_records)
        return stats
    finally:
        await pipeline.close()
