"""Test PG_CHANNEL_MAP registration for cell_pulse_observed."""


def test_cell_pulse_observed_channel_registered():
    from backend.services.events.event_bus import PG_CHANNEL_MAP
    assert "cell_pulse_observed" in PG_CHANNEL_MAP
    # Event type must follow dotted convention
    event_type = PG_CHANNEL_MAP["cell_pulse_observed"]
    assert "." in event_type, f"event_type {event_type!r} must use dotted notation"


def test_cell_pulse_observed_channel_name_matches_outbox_validation():
    """The channel name must satisfy outbox.validate_channel regex."""
    from backend.services.events.outbox import validate_channel
    validate_channel("cell_pulse_observed")  # raises if invalid
