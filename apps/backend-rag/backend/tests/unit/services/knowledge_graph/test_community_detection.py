"""Unit tests for backend/services/knowledge_graph/community_detection.py"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.knowledge_graph.community_detection import (
    Community,
    CommunityDetector,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _AsyncCM:
    """Reusable async context manager returning a fixed connection mock."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()

    pool.acquire.return_value = _AsyncCM(conn)

    return pool, conn


@pytest.fixture
def detector(mock_pool):
    pool, _ = mock_pool
    return CommunityDetector(db_pool=pool)


# ---------------------------------------------------------------------------
# Community dataclass
# ---------------------------------------------------------------------------


class TestCommunityDataclass:
    def test_defaults(self):
        c = Community(community_id="c1")
        assert c.community_id == "c1"
        assert c.level == 0
        assert c.members == []
        assert c.member_count == 0
        assert c.modularity_contribution == 0.0

    def test_with_members(self):
        c = Community(
            community_id="c2",
            members=["a", "b", "c"],
            member_count=3,
            top_entities=["a"],
            top_relations=["RELATED"],
        )
        assert len(c.members) == 3
        assert c.top_entities == ["a"]


# ---------------------------------------------------------------------------
# load_graph
# ---------------------------------------------------------------------------


class TestLoadGraph:
    @pytest.mark.asyncio
    async def test_empty_graph(self, detector, mock_pool):
        _, conn = mock_pool
        conn.fetch.side_effect = [
            [],  # edges
            [],  # nodes
        ]

        adj, weights, edge_types = await detector.load_graph()
        assert adj == {}
        assert weights == {}

    @pytest.mark.asyncio
    async def test_simple_graph(self, detector, mock_pool):
        _, conn = mock_pool
        conn.fetch.side_effect = [
            # edges
            [
                {
                    "source_entity_id": "A",
                    "target_entity_id": "B",
                    "confidence": 0.9,
                    "relationship_type": "REQUIRES",
                },
                {
                    "source_entity_id": "B",
                    "target_entity_id": "C",
                    "confidence": 0.8,
                    "relationship_type": "RELATED",
                },
            ],
            # nodes
            [
                {"entity_id": "A"},
                {"entity_id": "B"},
                {"entity_id": "C"},
                {"entity_id": "D"},  # isolated node
            ],
        ]

        adj, weights, edge_types = await detector.load_graph()

        assert "A" in adj
        assert "B" in adj["A"]
        assert "A" in adj["B"]  # undirected
        assert "D" in adj  # isolated but included
        assert adj["D"] == set()
        assert weights[("A", "B")] == 0.9
        assert edge_types[("A", "B")] == "REQUIRES"


# ---------------------------------------------------------------------------
# _louvain
# ---------------------------------------------------------------------------


class TestLouvain:
    def test_empty_graph(self, detector):
        result = detector._louvain({}, {})
        assert result == {}

    def test_single_node(self, detector):
        adj = {"A": set()}
        weights = {}
        result = detector._louvain(adj, weights)
        assert "A" in result

    def test_two_connected_nodes(self, detector):
        adj = {"A": {"B"}, "B": {"A"}}
        weights = {("A", "B"): 1.0, ("B", "A"): 1.0}
        result = detector._louvain(adj, weights)
        # Two tightly connected nodes should be in same community
        assert result["A"] == result["B"]

    def test_two_disconnected_components(self, detector):
        adj = {
            "A": {"B"},
            "B": {"A"},
            "C": {"D"},
            "D": {"C"},
        }
        weights = {
            ("A", "B"): 1.0,
            ("B", "A"): 1.0,
            ("C", "D"): 1.0,
            ("D", "C"): 1.0,
        }
        result = detector._louvain(adj, weights)
        # Disconnected components should be in different communities
        assert result["A"] == result["B"]
        assert result["C"] == result["D"]
        assert result["A"] != result["C"]

    def test_triangle_cluster(self, detector):
        adj = {
            "A": {"B", "C"},
            "B": {"A", "C"},
            "C": {"A", "B"},
        }
        weights = {
            ("A", "B"): 1.0, ("B", "A"): 1.0,
            ("A", "C"): 1.0, ("C", "A"): 1.0,
            ("B", "C"): 1.0, ("C", "B"): 1.0,
        }
        result = detector._louvain(adj, weights)
        # All in same community
        assert result["A"] == result["B"] == result["C"]

    def test_zero_weight_graph(self, detector):
        adj = {"A": {"B"}, "B": {"A"}}
        weights = {("A", "B"): 0.0, ("B", "A"): 0.0}
        # m=0 -> early return
        result = detector._louvain(adj, weights)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# detect
# ---------------------------------------------------------------------------


class TestDetect:
    @pytest.mark.asyncio
    async def test_empty_graph_returns_empty(self, detector, mock_pool):
        _, conn = mock_pool
        conn.fetch.side_effect = [[], []]

        communities = await detector.detect()
        assert communities == []

    @pytest.mark.asyncio
    async def test_detects_communities(self, detector, mock_pool):
        _, conn = mock_pool

        # Build a graph with 2 clear clusters
        edges = []
        nodes = []
        # Cluster 1: A-B-C-D-E (fully connected)
        for _, src in enumerate(["A", "B", "C", "D", "E"]):
            nodes.append({"entity_id": src})
            for tgt in ["A", "B", "C", "D", "E"]:
                if src != tgt:
                    edges.append({
                        "source_entity_id": src,
                        "target_entity_id": tgt,
                        "confidence": 1.0,
                        "relationship_type": "CLUSTER1",
                    })
        # Cluster 2: X-Y-Z-W (fully connected)
        for src in ["X", "Y", "Z", "W"]:
            nodes.append({"entity_id": src})
            for tgt in ["X", "Y", "Z", "W"]:
                if src != tgt:
                    edges.append({
                        "source_entity_id": src,
                        "target_entity_id": tgt,
                        "confidence": 1.0,
                        "relationship_type": "CLUSTER2",
                    })

        conn.fetch.side_effect = [edges, nodes]

        communities = await detector.detect(min_community_size=3)
        assert len(communities) >= 2

        # Check community properties
        for c in communities:
            assert c.member_count >= 3
            assert len(c.members) >= 3
            assert c.community_id.startswith("comm_L0_")

    @pytest.mark.asyncio
    async def test_min_community_size_filters(self, detector, mock_pool):
        _, conn = mock_pool

        # Small graph: A-B (only 2 nodes)
        edges = [
            {"source_entity_id": "A", "target_entity_id": "B", "confidence": 1.0, "relationship_type": "R"},
        ]
        nodes = [{"entity_id": "A"}, {"entity_id": "B"}]
        conn.fetch.side_effect = [edges, nodes]

        communities = await detector.detect(min_community_size=3)
        assert communities == []  # Filtered out


# ---------------------------------------------------------------------------
# persist
# ---------------------------------------------------------------------------


class TestPersist:
    @pytest.mark.asyncio
    async def test_empty_list_returns_zero(self, detector, mock_pool):
        count = await detector.persist([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_persists_communities(self, detector, mock_pool):
        _, conn = mock_pool

        # conn.transaction() must return a sync object with async CM protocol
        class _TxCM:
            async def __aenter__(self):
                return None
            async def __aexit__(self, *exc):
                return False

        conn.transaction = MagicMock(return_value=_TxCM())

        communities = [
            Community(
                community_id="c1",
                level=0,
                members=["A", "B", "C"],
                member_count=3,
                top_entities=["A"],
                top_relations=["R"],
            ),
            Community(
                community_id="c2",
                level=0,
                members=["X", "Y", "Z"],
                member_count=3,
                top_entities=["X"],
                top_relations=["S"],
            ),
        ]

        count = await detector.persist(communities)
        assert count == 2

        # Verify batch operations were called
        assert conn.executemany.called
        assert conn.execute.called

    @pytest.mark.asyncio
    async def test_persist_with_batching(self, detector, mock_pool):
        _, conn = mock_pool

        class _TxCM:
            async def __aenter__(self):
                return None
            async def __aexit__(self, *exc):
                return False

        conn.transaction = MagicMock(return_value=_TxCM())

        # Create community with many members to test batch_size
        members = [f"node_{i}" for i in range(600)]
        communities = [
            Community(
                community_id="big",
                level=0,
                members=members,
                member_count=600,
            )
        ]

        count = await detector.persist(communities, batch_size=200)
        assert count == 1

        # Should have made multiple executemany calls for memberships
        executemany_calls = conn.executemany.call_count
        assert executemany_calls >= 3  # 600 / 200 = 3 batches (+ community insert)


# ---------------------------------------------------------------------------
# generate_summaries
# ---------------------------------------------------------------------------


class TestGenerateSummaries:
    @pytest.mark.asyncio
    async def test_no_communities_to_summarize(self, detector, mock_pool):
        _, conn = mock_pool
        conn.fetch.return_value = []

        mock_llm = AsyncMock()
        count = await detector.generate_summaries(mock_llm)
        assert count == 0

    @pytest.mark.asyncio
    async def test_generates_summary(self, detector, mock_pool):
        _, conn = mock_pool

        # First fetch: communities needing summaries
        conn.fetch.side_effect = [
            [
                {
                    "community_id": "c1",
                    "top_entities": ["e1", "e2"],
                    "top_relations": ["R1"],
                    "member_count": 10,
                }
            ],
            # Entity details
            [
                {
                    "entity_id": "e1",
                    "name": "KITAS",
                    "entity_type": "PERMIT",
                    "description": "Stay permit",
                }
            ],
            # Relationship details
            [
                {
                    "source_entity_id": "e1",
                    "relationship_type": "REQUIRES",
                    "target_name": "Passport",
                }
            ],
        ]

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Community about visa permits."

        count = await detector.generate_summaries(mock_llm)
        assert count == 1
        mock_llm.generate.assert_called_once()
        conn.execute.assert_called()  # UPDATE summary

    @pytest.mark.asyncio
    async def test_llm_failure_skips(self, detector, mock_pool):
        _, conn = mock_pool
        conn.fetch.side_effect = [
            [
                {
                    "community_id": "c1",
                    "top_entities": ["e1"],
                    "top_relations": [],
                    "member_count": 5,
                }
            ],
            [{"entity_id": "e1", "name": "Test", "entity_type": "X", "description": ""}],
            [],  # no rels
        ]

        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = Exception("API error")

        count = await detector.generate_summaries(mock_llm)
        assert count == 0

    @pytest.mark.asyncio
    async def test_uses_separate_pool(self, detector, mock_pool):
        _, conn = mock_pool

        separate_pool = MagicMock()
        sep_conn = AsyncMock()
        sep_conn.fetch.return_value = []
        separate_pool.acquire.return_value = _AsyncCM(sep_conn)

        mock_llm = AsyncMock()
        count = await detector.generate_summaries(mock_llm, db_pool=separate_pool)
        assert count == 0
        separate_pool.acquire.assert_called()
