import os
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from backend.services.portal import challenge_leaderboard as scoring

pytestmark = pytest.mark.skipif(
    not os.environ.get("CHAMPION_TEST_PG_SOCKET"),
    reason="Requires an explicitly provisioned scratch PostgreSQL Unix socket",
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "valid",
        "duplicate",
        "alias",
        "staff",
        "deleted",
        "test_tag",
        "pilot_tag",
        "previous_activation",
    ],
)
async def test_goal_sql_executes_with_canonical_exclusions(monkeypatch, scenario):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(scoring, "WINDOW_START", now - timedelta(days=2))
    monkeypatch.setattr(scoring, "WINDOW_END", now + timedelta(days=2))
    connection = await asyncpg.connect(
        host=os.environ["CHAMPION_TEST_PG_SOCKET"],
        port=55437,
        user=os.environ["USER"],
        database="postgres",
    )
    try:
        await connection.execute("""
            CREATE TEMP TABLE clients (id bigint, deleted_at timestamptz, tags text[]);
            CREATE TEMP TABLE client_invitations (client_id bigint, created_by text, created_at timestamptz, used_at timestamptz, email text);
            CREATE TEMP TABLE team_members (email text, name text, avatar text, role text, active boolean);
            INSERT INTO team_members VALUES ('contender@balizero.com', 'Contender', '/static/team/sample.jpg', 'member', TRUE);
            INSERT INTO clients VALUES (2, NULL, '{}');
            INSERT INTO client_invitations VALUES (2, 'contender@balizero.com', NOW(), NOW(), 'second@example.test');
        """)
        tags = (
            ["test"]
            if scenario == "test_tag"
            else ["portal-pilot"]
            if scenario == "pilot_tag"
            else []
        )
        email = (
            "client+alias@example.test"
            if scenario == "alias"
            else "internal@balizero.com"
            if scenario == "staff"
            else "client@example.test"
        )
        await connection.execute(
            "INSERT INTO clients VALUES (1, $1, $2)", now if scenario == "deleted" else None, tags
        )
        await connection.execute(
            "INSERT INTO client_invitations VALUES (1, 'CONTENDER@balizero.com', $1, $1, $2)",
            now,
            email,
        )
        if scenario in {"duplicate", "previous_activation"}:
            previous = now if scenario == "duplicate" else now - timedelta(days=3)
            await connection.execute(
                "INSERT INTO client_invitations VALUES (1, 'contender@balizero.com', $1, $1, $2)",
                previous,
                email,
            )
        result = await connection.fetchrow(scoring.build_goal_sql(), 1)
        aggregates = await connection.fetch(scoring.build_aggregates_sql())
        if scenario in {"valid", "duplicate"}:
            assert result["creator_email"] == "contender@balizero.com"
            assert result["activations"] == 2
            assert result["activations"] == aggregates[0]["activations"]
        else:
            assert result is None
            assert aggregates[0]["activations"] == 1
    finally:
        await connection.close()
