"""Tests for HGT Publisher."""
import pytest

from cell_core.hgt.publisher import HGTPublisher, STREAM_SKILLS


@pytest.mark.asyncio
async def test_publish_eligible_skill(fake_redis):
    pub = HGTPublisher(fake_redis, cell_name="mata-garuda")
    skill = {
        "id": "proxy_detection_v1",
        "procedure": "Use regex for Surat Kuasa detection",
        "precondition": "Indonesian akta text",
        "success_criterion": "Zero false proxies",
        "confidence": 0.85,
        "scope": "Project",
        "type": "skill",
        "domain": "legal",
    }
    result = await pub.publish(skill)
    assert result is True

    stream = fake_redis.get_stream(STREAM_SKILLS)
    assert len(stream) == 1
    _msg_id, data = stream[0]
    assert data["skill_id"] == "proxy_detection_v1"
    assert data["cell_origin"] == "mata-garuda"
    assert data["domain"] == "legal"
    assert data["confidence"] == "0.85"


@pytest.mark.asyncio
async def test_publish_filters_low_confidence(fake_redis):
    pub = HGTPublisher(fake_redis, cell_name="c1")
    skill = {"id": "weak", "procedure": "x", "confidence": 0.5, "scope": "Project"}
    result = await pub.publish(skill)
    assert result is False
    assert len(fake_redis.get_stream(STREAM_SKILLS)) == 0


@pytest.mark.asyncio
async def test_publish_filters_personal_scope(fake_redis):
    pub = HGTPublisher(fake_redis, cell_name="c1")
    skill = {"id": "s1", "procedure": "x", "confidence": 0.9, "scope": "Personal"}
    result = await pub.publish(skill)
    assert result is False


@pytest.mark.asyncio
async def test_publish_filters_scar(fake_redis):
    pub = HGTPublisher(fake_redis, cell_name="c1")
    skill = {"id": "s1", "procedure": "x", "confidence": 0.9, "scope": "Project", "type": "scar"}
    result = await pub.publish(skill)
    assert result is False


@pytest.mark.asyncio
async def test_publish_graceful_degradation_redis_down(broken_redis):
    pub = HGTPublisher(broken_redis, cell_name="c1")
    skill = {"id": "s1", "procedure": "x", "confidence": 0.9, "scope": "Project"}
    result = await pub.publish(skill)
    assert result is False  # no crash, just returns False


@pytest.mark.asyncio
async def test_publish_no_redis():
    pub = HGTPublisher(None, cell_name="c1")
    skill = {"id": "s1", "procedure": "x", "confidence": 0.9, "scope": "Project"}
    result = await pub.publish(skill)
    assert result is False


@pytest.mark.asyncio
async def test_publish_maxlen(fake_redis):
    pub = HGTPublisher(fake_redis, cell_name="c1", maxlen=5)
    for i in range(10):
        await pub.publish({
            "id": f"s{i}", "procedure": f"p{i}",
            "confidence": 0.8, "scope": "Project",
        })
    stream = fake_redis.get_stream(STREAM_SKILLS)
    assert len(stream) == 5  # trimmed to maxlen


@pytest.mark.asyncio
async def test_publish_domain_defaults_generic(fake_redis):
    pub = HGTPublisher(fake_redis, cell_name="c1")
    skill = {"id": "s1", "procedure": "x", "confidence": 0.9, "scope": "Project"}
    await pub.publish(skill)
    _id, data = fake_redis.get_stream(STREAM_SKILLS)[0]
    assert data["domain"] == "generic"
