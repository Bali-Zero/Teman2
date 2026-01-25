-- Golden Answers System - PostgreSQL Schema
-- Created: 2025-10-16
-- Purpose: Cache pre-generated answers for frequent queries

-- ============================================
-- Table: golden_answers
-- ============================================
CREATE TABLE IF NOT EXISTS golden_answers (
    id SERIAL PRIMARY KEY,

    -- Cluster identification
    cluster_id VARCHAR(100) UNIQUE NOT NULL,
    canonical_question TEXT NOT NULL,
    variations TEXT[] DEFAULT '{}',  -- Array of similar questions

    -- Generated content
    answer TEXT NOT NULL,
    sources JSONB DEFAULT '[]',  -- [{title, url, score}]

    -- Metadata
    generated_by VARCHAR(50) NOT NULL,  -- 'llama-3.1-zantara' or 'zantara-ai'
    generation_method VARCHAR(50) DEFAULT 'llama_rag',  -- 'llama_rag', 'zantara_rag' (legacy: was claude_rag)
    confidence FLOAT DEFAULT 0.0,

    -- Analytics
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_golden_cluster ON golden_answers(cluster_id);
CREATE INDEX IF NOT EXISTS idx_golden_usage ON golden_answers(usage_count DESC);
CREATE INDEX IF NOT EXISTS idx_golden_updated ON golden_answers(updated_at DESC);

-- ============================================
-- Table: query_clusters
-- ============================================
-- Tracks which queries belong to which clusters
CREATE TABLE IF NOT EXISTS query_clusters (
    id SERIAL PRIMARY KEY,

    cluster_id VARCHAR(100) NOT NULL,
    query_text TEXT NOT NULL,
    query_hash VARCHAR(64) UNIQUE,  -- MD5 hash for deduplication

    -- Cluster assignment
    similarity_score FLOAT,  -- How similar to canonical question
    assigned_at TIMESTAMP DEFAULT NOW(),

    -- Query metadata
    frequency INTEGER DEFAULT 1,  -- How many times this exact query appeared
    ai_used VARCHAR(20),  -- 'sonnet', 'haiku', 'llama'

    FOREIGN KEY (cluster_id) REFERENCES golden_answers(cluster_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cluster_query ON query_clusters(cluster_id);
CREATE INDEX IF NOT EXISTS idx_query_hash ON query_clusters(query_hash);
CREATE INDEX IF NOT EXISTS idx_query_frequency ON query_clusters(frequency DESC);

-- ============================================
-- Table: cultural_knowledge
-- ============================================
-- Stores cultural knowledge chunks for Haiku
CREATE TABLE IF NOT EXISTS cultural_knowledge (
    id SERIAL PRIMARY KEY,

    topic VARCHAR(100) NOT NULL,  -- 'indonesian_greetings', 'bureaucracy_patience', etc.
    content TEXT NOT NULL,

    -- Usage triggers
    when_to_use TEXT[] DEFAULT '{}',  -- ['first_contact', 'casual_chat', 'frustration']
    tone VARCHAR(50),  -- 'friendly_welcoming', 'empathetic_reassuring'

    -- Metadata
    generated_by VARCHAR(50) DEFAULT 'llama-3.1-zantara',
    quality_score FLOAT DEFAULT 0.0,

    -- Analytics
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cultural_topic ON cultural_knowledge(topic);
CREATE INDEX IF NOT EXISTS idx_cultural_usage ON cultural_knowledge(usage_count DESC);

-- ============================================
-- Table: nightly_worker_runs
-- ============================================
-- Tracks LLAMA nightly worker execution
CREATE TABLE IF NOT EXISTS nightly_worker_runs (
    id SERIAL PRIMARY KEY,

    run_date DATE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,

    -- Task completion
    intel_classification_count INTEGER DEFAULT 0,
    golden_answers_generated INTEGER DEFAULT 0,
    golden_answers_updated INTEGER DEFAULT 0,
    cultural_chunks_generated INTEGER DEFAULT 0,

    -- AI usage
    llama_tokens_used INTEGER DEFAULT 0,
    zantara_fallback_tokens INTEGER DEFAULT 0,  -- LEGACY: was claude_fallback_tokens

    -- Status
    status VARCHAR(20) DEFAULT 'running',  -- 'running', 'completed', 'failed'
    error_message TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_worker_date ON nightly_worker_runs(run_date DESC);

-- ============================================
-- Function: Update updated_at timestamp
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for auto-updating updated_at
CREATE TRIGGER update_golden_answers_updated_at
    BEFORE UPDATE ON golden_answers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cultural_knowledge_updated_at
    BEFORE UPDATE ON cultural_knowledge
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Initial Data: Cultural Knowledge Seeds
-- ============================================
-- Pre-populate with essential cultural knowledge
INSERT INTO cultural_knowledge (topic, content, when_to_use, tone) VALUES
    (
        'indonesian_greetings',
        'Indonesians value warm, personal greetings. "Selamat pagi" (good morning), "Apa kabar?" (how are you) are essential. Business relationships start with small talk, not abrupt transactions. Taking time to connect personally shows respect.',
        ARRAY['first_contact', 'casual_chat', 'greeting'],
        'friendly_welcoming'
    ),
    (
        'bureaucracy_patience',
        'Indonesian bureaucracy operates at its own pace. Rushing officials is counterproductive and culturally insensitive. BALI ZERO acts as your cultural bridge - we know when to gently push and when to patiently wait. This isn''t inefficiency; it''s the Indonesian way of ensuring thoroughness.',
        ARRAY['timeline_questions', 'frustration_handling', 'delay_response'],
        'empathetic_reassuring'
    ),
    (
        'face_saving_culture',
        'Indonesians avoid direct confrontation to preserve "muka" (face). When an official says something is "sulit" (difficult), it doesn''t mean impossible - it means negotiation is needed. BALI ZERO navigates these subtle communications on your behalf.',
        ARRAY['rejection_handling', 'difficult_cases', 'negotiation'],
        'diplomatic_wise'
    ),
    (
        'tri_hita_karana',
        'Bali''s philosophy "Tri Hita Karana" means harmony with God, people, and nature. This isn''t just spirituality - it affects business decisions, timelines, and relationships. Understanding this helps you work with Bali, not against it.',
        ARRAY['cultural_question', 'philosophy_interest', 'bali_lifestyle'],
        'educational_warm'
    )
ON CONFLICT DO NOTHING;

-- ============================================
-- Views: Analytics
-- ============================================

-- View: Golden Answers Performance
CREATE OR REPLACE VIEW golden_answers_performance AS
SELECT
    cluster_id,
    canonical_question,
    usage_count,
    confidence,
    generated_by,
    DATE(created_at) as created_date,
    DATE(last_used_at) as last_used_date,
    EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400 as age_days
FROM golden_answers
ORDER BY usage_count DESC;

-- View: Query Clustering Summary
CREATE OR REPLACE VIEW query_clustering_summary AS
SELECT
    qc.cluster_id,
    ga.canonical_question,
    COUNT(*) as query_count,
    SUM(qc.frequency) as total_frequency,
    AVG(qc.similarity_score) as avg_similarity,
    ga.usage_count as golden_answer_hits
FROM query_clusters qc
JOIN golden_answers ga ON qc.cluster_id = ga.cluster_id
GROUP BY qc.cluster_id, ga.canonical_question, ga.usage_count
ORDER BY total_frequency DESC;

-- View: Cultural Knowledge Usage
CREATE OR REPLACE VIEW cultural_knowledge_usage AS
SELECT
    topic,
    usage_count,
    tone,
    DATE(last_used_at) as last_used_date,
    EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400 as age_days
FROM cultural_knowledge
ORDER BY usage_count DESC;

-- ============================================
-- Grant Permissions (if needed)
-- ============================================
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO railway_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO railway_user;

COMMENT ON TABLE golden_answers IS 'Pre-generated answers for frequent queries (Golden Answers System)';
COMMENT ON TABLE query_clusters IS 'Maps user queries to golden answer clusters';
COMMENT ON TABLE cultural_knowledge IS 'Cultural knowledge chunks for Haiku warmth/elegance';
COMMENT ON TABLE nightly_worker_runs IS 'LLAMA nightly worker execution logs';
