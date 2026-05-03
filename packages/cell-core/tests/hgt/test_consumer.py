"""Tests for HGT Consumer."""
import pytest

from cell_core.hgt.consumer import HGTConsumer
from cell_core.hgt.publisher import HGTPublisher, STREAM_SKILLS


@pytest.mark.asyncio
async def test_consume_integrates_skill(fake_redis, genome):
    """Published skill is consumed and recorded in genome with decay."""
    pub = HGTPublisher(fake_redis, cell_name="mata-garuda")
    await pub.publish({
        "id": "proxy_v1", "procedure": "Use regex for proxies",
        "confidence": 0.8, "scope": "Project", "domain": "legal",
    })

    consumer = HGTConsumer(
        fake_redis, genome, cell_name="kontrak_parser",
        interested_domains={"legal", "generic"},
    )
    await consumer.ensure_group()
    count = await consumer.consume_once()

    assert count == 1
    skills = genome.get_active(cell="kontrak_parser")
    assert len(skills) == 1
    assert skills[0]["id"] == "hgt_proxy_v1"
    assert skills[0]["inherited_from"] == "proxy_v1"
    # 0.8 * 0.9 decay = 0.72
    assert abs(skills[0]["confidence"] - 0.72) < 0.01
    assert skills[0]["domain"] == "legal"


@pytest.mark.asyncio
async def test_consume_filters_own_skills(fake_redis, genome):
    """Consumer skips skills it published itself."""
    pub = HGTPublisher(fake_redis, cell_name="c1")
    await pub.publish({
        "id": "s1", "procedure": "p1", "confidence": 0.8,
        "scope": "Project", "domain": "generic",
    })

    consumer = HGTConsumer(
        fake_redis, genome, cell_name="c1",  # same cell!
        interested_domains={"generic"},
    )
    await consumer.ensure_group()
    count = await consumer.consume_once()
    assert count == 0


@pytest.mark.asyncio
async def test_consume_filters_irrelevant_domain(fake_redis, genome):
    """Consumer ignores skills from domains it doesn't care about."""
    pub = HGTPublisher(fake_redis, cell_name="mata-garuda")
    await pub.publish({
        "id": "s1", "procedure": "tax technique", "confidence": 0.8,
        "scope": "Project", "domain": "tax",
    })

    consumer = HGTConsumer(
        fake_redis, genome, cell_name="kontrak_parser",
        interested_domains={"legal"},  # not interested in "tax"
    )
    await consumer.ensure_group()
    count = await consumer.consume_once()
    assert count == 0


@pytest.mark.asyncio
async def test_consume_generic_always_accepted(fake_redis, genome):
    """'generic' domain skills are always accepted."""
    pub = HGTPublisher(fake_redis, cell_name="mata-garuda")
    await pub.publish({
        "id": "s1", "procedure": "universal technique", "confidence": 0.8,
        "scope": "Project", "domain": "generic",
    })

    consumer = HGTConsumer(
        fake_redis, genome, cell_name="kontrak_parser",
        interested_domains={"legal"},  # doesn't include "generic" explicitly
    )
    await consumer.ensure_group()
    count = await consumer.consume_once()
    assert count == 1  # generic is always accepted


@pytest.mark.asyncio
async def test_consume_graceful_degradation(broken_redis, genome):
    """Redis down doesn't crash the consumer."""
    consumer = HGTConsumer(
        broken_redis, genome, cell_name="c1",
        interested_domains={"generic"},
    )
    count = await consumer.consume_once()
    assert count == 0  # no crash


@pytest.mark.asyncio
async def test_consume_no_redis(genome):
    """None redis client is handled gracefully."""
    consumer = HGTConsumer(
        None, genome, cell_name="c1",
        interested_domains={"generic"},
    )
    count = await consumer.consume_once()
    assert count == 0


@pytest.mark.asyncio
async def test_consume_multiple_messages(fake_redis, genome):
    """Multiple skills consumed in one batch."""
    pub = HGTPublisher(fake_redis, cell_name="producer")
    for i in range(5):
        await pub.publish({
            "id": f"s{i}", "procedure": f"technique {i}", "confidence": 0.8,
            "scope": "Project", "domain": "legal",
        })

    consumer = HGTConsumer(
        fake_redis, genome, cell_name="consumer",
        interested_domains={"legal"},
    )
    await consumer.ensure_group()
    count = await consumer.consume_once()
    assert count == 5
    assert len(genome.get_active(cell="consumer")) == 5


@pytest.mark.asyncio
async def test_consume_xack_prevents_redelivery(fake_redis, genome):
    """After consumption, messages are ACK'd and not redelivered."""
    pub = HGTPublisher(fake_redis, cell_name="producer")
    await pub.publish({
        "id": "s1", "procedure": "p1", "confidence": 0.8,
        "scope": "Project", "domain": "generic",
    })

    consumer = HGTConsumer(
        fake_redis, genome, cell_name="consumer",
        interested_domains={"generic"},
    )
    await consumer.ensure_group()

    count1 = await consumer.consume_once()
    assert count1 == 1

    count2 = await consumer.consume_once()
    assert count2 == 0  # already consumed


@pytest.mark.asyncio
async def test_two_consumers_different_domains(fake_redis, tmp_path):
    """Two consumers with different domain interests get different skills."""
    from cell_core.genome import Genome

    genome_a = Genome(db_path=str(tmp_path / "a.db"))
    genome_b = Genome(db_path=str(tmp_path / "b.db"))

    pub = HGTPublisher(fake_redis, cell_name="producer")
    await pub.publish({
        "id": "legal_skill", "procedure": "contract parsing",
        "confidence": 0.8, "scope": "Project", "domain": "legal",
    })
    await pub.publish({
        "id": "tax_skill", "procedure": "PPh21 calc",
        "confidence": 0.8, "scope": "Project", "domain": "tax",
    })

    consumer_legal = HGTConsumer(
        fake_redis, genome_a, cell_name="legal_cell",
        interested_domains={"legal"},
    )
    consumer_tax = HGTConsumer(
        fake_redis, genome_b, cell_name="tax_cell",
        interested_domains={"tax"},
    )

    await consumer_legal.ensure_group()
    await consumer_tax.ensure_group()

    count_legal = await consumer_legal.consume_once()
    count_tax = await consumer_tax.consume_once()

    assert count_legal == 1
    assert count_tax == 1

    legal_skills = genome_a.get_active(cell="legal_cell")
    tax_skills = genome_b.get_active(cell="tax_cell")

    assert len(legal_skills) == 1
    assert legal_skills[0]["domain"] == "legal"
    assert len(tax_skills) == 1
    assert tax_skills[0]["domain"] == "tax"
