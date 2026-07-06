from datetime import UTC, datetime, timedelta

from backend.services.compliance.compliance_tracker import ComplianceTrackerService


def _deadline(days: int) -> str:
    return (datetime.now(tz=UTC) + timedelta(days=days)).isoformat()


def test_add_compliance_item_stores_item_and_updates_stats() -> None:
    service = ComplianceTrackerService()

    item = service.add_compliance_item(
        client_id="client-1",
        compliance_type="lkpm",
        title="LKPM Q1",
        deadline=_deadline(30),
        description="Submit quarterly LKPM",
        estimated_cost=1500000.0,
        required_documents=["NIB", "OSS report"],
        metadata={"quarter": "Q1"},
    )

    assert service.get_compliance_item(item.item_id) == item
    assert item.requirement_details == "Submit quarterly LKPM"
    assert item.required_documents == ["NIB", "OSS report"]
    assert service.get_stats()["total_items_tracked"] == 1
    assert service.get_stats()["active_items"] == 1
    assert service.get_stats()["compliance_type_distribution"] == {"lkpm": 1}


def test_get_upcoming_deadlines_filters_by_client_and_sorts_by_deadline() -> None:
    service = ComplianceTrackerService()
    later = service.add_compliance_item("client-1", "visa", "Later", _deadline(20))
    earlier = service.add_compliance_item("client-1", "tax", "Earlier", _deadline(5))
    service.add_compliance_item("client-2", "lkpm", "Other Client", _deadline(1))
    service.add_compliance_item("client-1", "future", "Too Far", _deadline(120))

    upcoming = service.get_upcoming_deadlines(client_id="client-1", days_ahead=30)

    assert upcoming == [earlier, later]


def test_resolve_compliance_item_removes_active_item() -> None:
    service = ComplianceTrackerService()
    item = service.add_compliance_item("client-1", "visa", "Renew KITAS", _deadline(10))

    assert service.resolve_compliance_item(item.item_id) is True
    assert service.get_compliance_item(item.item_id) is None
    assert service.get_stats()["active_items"] == 0
    assert service.resolve_compliance_item("missing") is False


def test_get_all_items_can_filter_by_client() -> None:
    service = ComplianceTrackerService()
    client_one = service.add_compliance_item("client-1", "visa", "Renew KITAS", _deadline(10))
    service.add_compliance_item("client-2", "tax", "Annual SPT", _deadline(20))

    assert service.get_all_items(client_id="client-1") == [client_one]
    assert len(service.get_all_items()) == 2
