"""
Migration 096: KG Communities — Community detection support for GraphRAG 2.0

Creates tables for storing detected communities (Louvain/Leiden clusters)
and node-community memberships. Community summaries are embedded for
hybrid retrieval.

Tables:
  - kg_communities: detected community clusters with summaries + embeddings
  - kg_node_community: many-to-many mapping of nodes to communities
"""

MIGRATION_ID = "096_kg_communities"

UP_SQL = """
-- Community clusters detected by graph algorithms (Louvain)
CREATE TABLE IF NOT EXISTS kg_communities (
    community_id    TEXT PRIMARY KEY,
    level           INT NOT NULL DEFAULT 0,
    parent_id       TEXT REFERENCES kg_communities(community_id) ON DELETE SET NULL,
    name            TEXT,
    summary         TEXT,
    member_count    INT NOT NULL DEFAULT 0,
    top_entities    TEXT[] DEFAULT '{}',
    top_relations   TEXT[] DEFAULT '{}',
    properties      JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Node-to-community membership (many-to-many: node can be in multiple communities at different levels)
CREATE TABLE IF NOT EXISTS kg_node_community (
    entity_id       TEXT NOT NULL REFERENCES kg_nodes(entity_id) ON DELETE CASCADE,
    community_id    TEXT NOT NULL REFERENCES kg_communities(community_id) ON DELETE CASCADE,
    membership_score FLOAT NOT NULL DEFAULT 1.0,
    PRIMARY KEY (entity_id, community_id)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_kg_communities_level ON kg_communities(level);
CREATE INDEX IF NOT EXISTS idx_kg_communities_parent ON kg_communities(parent_id);
CREATE INDEX IF NOT EXISTS idx_kg_node_community_entity ON kg_node_community(entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_node_community_community ON kg_node_community(community_id);
CREATE INDEX IF NOT EXISTS idx_kg_node_community_score ON kg_node_community(membership_score)
    WHERE membership_score >= 0.5;
"""

DOWN_SQL = """
DROP TABLE IF EXISTS kg_node_community;
DROP TABLE IF EXISTS kg_communities;
"""


async def up(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(UP_SQL)


async def down(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(DOWN_SQL)
