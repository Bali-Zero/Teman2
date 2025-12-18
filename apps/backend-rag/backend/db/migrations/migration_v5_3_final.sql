-- ========================================
-- ZANTARA v5.3 (Ultra Hybrid) - Final Production Migration
-- Database: PostgreSQL
-- Compatibility: PostgreSQL 13+
-- Author: Senior DevOps Engineer & Database Administrator
-- Idempotency: YES - Safe for multiple runs
-- ========================================

-- Begin Transaction
BEGIN;

-- Create migration tracking table if not exists
CREATE TABLE IF NOT EXISTS migration_log (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64),
    notes TEXT
);

-- Check if migration already executed
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM migration_log WHERE migration_name = 'migration_v5_3_final') THEN
        RAISE NOTICE 'Migration v5.3_final already executed, skipping...';
        RAISE EXCEPTION 'Migration already executed';
    END IF;
END $$;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ========================================
-- 1. UPDATE USERS TABLE WITH ENHANCED PROFILES
-- ========================================

-- Add new columns to users table if they don't exist
DO $$
BEGIN
    -- Check and add meta_json column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'meta_json'
    ) THEN
        ALTER TABLE users ADD COLUMN meta_json JSONB DEFAULT '{}';
        RAISE NOTICE 'Added meta_json column to users table';
    END IF;

    -- Check and add language_preference column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'language_preference'
    ) THEN
        ALTER TABLE users ADD COLUMN language_preference VARCHAR(10) DEFAULT 'en';
        RAISE NOTICE 'Added language_preference column to users table';
    END IF;

    -- Check and add role_level column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'role_level'
    ) THEN
        ALTER TABLE users ADD COLUMN role_level VARCHAR(20) DEFAULT 'member';
        RAISE NOTICE 'Added role_level column to users table';
    END IF;

    -- Check and add timezone column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'timezone'
    ) THEN
        ALTER TABLE users ADD COLUMN timezone VARCHAR(50) DEFAULT 'Asia/Bali';
        RAISE NOTICE 'Added timezone column to users table';
    END IF;
END $$;

-- Create indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_users_meta_json_gin ON users USING GIN (meta_json);
CREATE INDEX IF NOT EXISTS idx_users_language_pref ON users (language_preference);
CREATE INDEX IF NOT EXISTS idx_users_role_level ON users (role_level);
CREATE INDEX IF NOT EXISTS idx_users_status_role ON users (status, role_level);

-- ========================================
-- 2. UPSERT TEAM MEMBERS WITH COMPLETE PROFILES
-- ========================================

-- Executive Leadership
INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'zainal.ceo@zantara.com',
    'Zainal',
    'ceo',
    'active',
    'id',
    '{
        "language": "id",
        "tone": "formal",
        "complexity": "high",
        "notes": "CEO responds in formal Bahasa Indonesia with executive level detail",
        "cultural_context": "indonesian_business_ethics",
        "decision_style": "strategic",
        "communication_preference": "written_reports",
        "expertise_domain": "executive_leadership"
    }',
    'executive',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

-- Senior Management
INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'ruslana.board@zantara.com',
    'Ruslana',
    'board_member',
    'active',
    'en',
    '{
        "language": "en",
        "tone": "executive",
        "complexity": "high",
        "notes": "Board member prefers executive summaries with strategic insights",
        "focus": "strategic_planning",
        "detail_preference": "summary",
        "decision_style": "data_driven",
        "expertise_domain": "corporate_governance"
    }',
    'executive',
    'Europe/London',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

-- Technology Team
INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'antonello.admin@zantara.com',
    'Antonello',
    'admin',
    'active',
    'it',
    '{
        "language": "it",
        "tone": "direct",
        "complexity": "high",
        "notes": "System administrator responds in Italian with direct, no-nonsense approach",
        "technical_preference": "detailed",
        "decision_style": "analytical",
        "communication_preference": "technical_specifications",
        "expertise_domain": "system_administration"
    }',
    'senior',
    'Europe/Rome',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'ari.senior@zantara.com',
    'Ari',
    'senior_developer',
    'active',
    'en',
    '{
        "language": "en",
        "technical_level": "expert",
        "specialization": "backend_systems",
        "notes": "Senior backend architect prefers technical specifications",
        "decision_style": "technical",
        "communication_preference": "code_documentation",
        "expertise_domain": "backend_architecture"
    }',
    'senior',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'vino.junior@zantara.com',
    'Vino',
    'junior_developer',
    'active',
    'id',
    '{
        "language": "id",
        "complexity": "low",
        "notes": "Junior developer with low English proficiency - explain simply in Bahasa",
        "technical_level": "beginner",
        "learning_style": "guided_step_by_step",
        "communication_preference": "visual_examples",
        "expertise_domain": "frontend_development"
    }',
    'junior',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

-- Legal & Compliance Team
INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'adit.legal@zantara.com',
    'Adit',
    'legal_advisor',
    'active',
    'id',
    '{
        "language": "id",
        "specialization": "indonesian_law",
        "notes": "Legal expert in Indonesian corporate law responds in formal Bahasa",
        "precision": "high",
        "attention_to_detail": "very_high",
        "communication_preference": "formal_legal_language",
        "expertise_domain": "indonesian_legal_compliance"
    }',
    'senior',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'faisha.compliance@zantara.com',
    'Faisha',
    'compliance_officer',
    'active',
    'id',
    '{
        "language": "id",
        "specialization": "regulatory_compliance",
        "notes": "Compliance expert for Indonesian regulations with high attention to detail",
        "precision": "very_high",
        "documentation_style": "detailed",
        "expertise_domain": "regulatory_compliance"
    }',
    'senior',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

-- Operations & Management
INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'kadek.operations@zantara.com',
    'Kadek',
    'operations_manager',
    'active',
    'id',
    '{
        "language": "id",
        "specialization": "operational_efficiency",
        "notes": "Operations manager focused on Indonesian business processes",
        "approach": "practical_efficient",
        "decision_style": "process_oriented",
        "expertise_domain": "business_operations"
    }',
    'manager',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'dea.hr@zantara.com',
    'Dea',
    'hr_manager',
    'active',
    'id',
    '{
        "language": "id",
        "specialization": "human_resources",
        "notes": "HR specialist focusing on Indonesian labor law compliance",
        "approach": "empathetic_professional",
        "communication_style": "supportive",
        "expertise_domain": "human_resources"
    }',
    'manager',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

-- Marketing & Analytics
INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'surya.marketing@zantara.com',
    'Surya',
    'marketing_director',
    'active',
    'id',
    '{
        "language": "id",
        "focus": "market_strategy",
        "notes": "Marketing director focused on Indonesian market dynamics",
        "creativity": "high",
        "data_preference": "visual_charts",
        "expertise_domain": "marketing_strategy"
    }',
    'director',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'krishna.analyst@zantara.com',
    'Krishna',
    'data_analyst',
    'active',
    'en',
    '{
        "language": "en",
        "focus": "data_insights",
        "notes": "Data analyst preferring visual explanations and metrics",
        "technical_preference": "data_visualization",
        "communication_style": "data_driven",
        "expertise_domain": "data_analytics"
    }',
    'intermediate',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'sahira.research@zantara.com',
    'Sahira',
    'research_analyst',
    'active',
    'en',
    '{
        "language": "en",
        "specialization": "market_research",
        "notes": "Research analyst with focus on Indonesian market trends",
        "methodology": "systematic_thorough",
        "reporting_style": "academic_standard",
        "expertise_domain": "market_research"
    }',
    'intermediate',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

-- Finance & Client Services
INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'veronika.finance@zantara.com',
    'Veronika',
    'financial_analyst',
    'active',
    'en',
    '{
        "language": "en",
        "specialization": "financial_modeling",
        "notes": "Financial analyst with focus on Southeast Asian markets",
        "precision": "high",
        "reporting_preference": "detailed_financial_statements",
        "expertise_domain": "financial_analysis"
    }',
    'senior',
    'Asia/Singapore',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'angel.relations@zantara.com',
    'Angel',
    'client_relations',
    'active',
    'en',
    '{
        "language": "en",
        "focus": "client_communication",
        "notes": "Client relations specialist with excellent communication skills",
        "approach": "friendly_professional",
        "communication_style": "relationship_focused",
        "expertise_domain": "client_relations"
    }',
    'intermediate',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

-- Training & Development
INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'rina.training@zantara.com',
    'Rina',
    'training_coordinator',
    'active',
    'id',
    '{
        "language": "id",
        "focus": "training_development",
        "notes": "Training specialist skilled in creating educational content",
        "approach": "encouraging_clear",
        "communication_style": "instructional",
        "expertise_domain": "training_development"
    }',
    'intermediate',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

-- Additional Team Members (for completeness)
INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'damar.tech@zantara.com',
    'Damar',
    'developer',
    'active',
    'id',
    '{
        "language": "id",
        "technical_level": "intermediate",
        "specialization": "fullstack_development",
        "notes": "Fullstack developer comfortable with Indonesian and English",
        "communication_preference": "mixed",
        "expertise_domain": "fullstack_development"
    }',
    'intermediate',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'dewaayu.design@zantara.com',
    'Dewa Ayu',
    'ui_designer',
    'active',
    'id',
    '{
        "language": "id",
        "specialization": "user_interface_design",
        "notes": "UI/UX designer focusing on Indonesian user experience",
        "design_approach": "culturally_adapted",
        "communication_preference": "visual",
        "expertise_domain": "ui_ux_design"
    }',
    'intermediate',
    'Asia/Bali',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

-- Terminated Employee (for testing purposes)
INSERT INTO users (
    id, email, name, role, status, language_preference, meta_json, role_level, timezone, created_at, updated_at
) VALUES (
    uuid_generate_v4(),
    'amanda.terminated@zantara.com',
    'Amanda',
    'former_developer',
    'terminated',
    'en',
    '{
        "language": "en",
        "notes": "Former employee - account terminated for testing",
        "status": "inactive",
        "termination_date": "2024-01-01"
    }',
    'junior',
    'Australia/Sydney',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (email) DO UPDATE SET
    language_preference = EXCLUDED.language_preference,
    meta_json = EXCLUDED.meta_json,
    role_level = EXCLUDED.role_level,
    timezone = EXCLUDED.timezone,
    updated_at = CURRENT_TIMESTAMP;

-- ========================================
-- 3. KNOWLEDGE FEEDBACK TABLE CREATION
-- ========================================

CREATE TABLE IF NOT EXISTS knowledge_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    original_answer TEXT,
    user_correction TEXT,
    feedback_type VARCHAR(50) NOT NULL CHECK (feedback_type IN ('factual_error', 'clarification', 'improvement', 'toxicity', 'incomplete', 'outdated')),
    context_documents TEXT[], -- Array of document IDs that were used
    model_used VARCHAR(100),
    response_time_ms INTEGER,
    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
    session_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    admin_notes TEXT,
    resolution_date TIMESTAMP WITH TIME ZONE
);

-- Create indexes for feedback table
CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON knowledge_feedback (user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON knowledge_feedback (feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON knowledge_feedback (created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_resolved ON knowledge_feedback (resolved);
CREATE INDEX IF NOT EXISTS idx_feedback_session_id ON knowledge_feedback (session_id);
CREATE INDEX IF NOT EXISTS idx_feedback_metadata_gin ON knowledge_feedback USING GIN (metadata);

-- ========================================
-- 4. ADDITIONAL ANALYTICS TABLES
-- ========================================

-- Query analytics for performance monitoring
CREATE TABLE IF NOT EXISTS query_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    query_hash VARCHAR(64), -- For duplicate query detection
    query_text TEXT NOT NULL,
    response_text TEXT,
    language_preference VARCHAR(10),
    model_used VARCHAR(100),
    response_time_ms INTEGER,
    document_count INTEGER,
    user_satisfaction INTEGER CHECK (user_satisfaction >= 1 AND user_satisfaction <= 5),
    session_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_analytics_user_id ON query_analytics (user_id);
CREATE INDEX IF NOT EXISTS idx_query_analytics_created_at ON query_analytics (created_at);
CREATE INDEX IF NOT EXISTS idx_query_analytics_lang_pref ON query_analytics (language_preference);
CREATE INDEX IF NOT EXISTS idx_query_analytics_query_hash ON query_analytics (query_hash);

-- Document language mappings
CREATE TABLE IF NOT EXISTS document_language_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(255) NOT NULL,
    source_language VARCHAR(10) DEFAULT 'id',
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN ('law', 'regulation', 'policy', 'contract', 'guideline')),
    jurisdiction VARCHAR(50) DEFAULT 'indonesia',
    effective_date DATE,
    expiry_date DATE,
    translation_available BOOLEAN DEFAULT FALSE,
    quality_score INTEGER CHECK (quality_score >= 1 AND quality_score <= 5),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_doc_mappings_doc_id ON document_language_mappings (document_id);
CREATE INDEX IF NOT EXISTS idx_doc_mappings_type ON document_language_mappings (document_type);
CREATE INDEX IF NOT EXISTS idx_doc_mappings_lang ON document_language_mappings (source_language);
CREATE INDEX IF NOT EXISTS idx_doc_mappings_jurisdiction ON document_language_mappings (jurisdiction);

-- ========================================
-- 5. DATA VALIDATION AND CONSTRAINTS
-- ========================================

-- Add constraints to users table
DO $$
BEGIN
    -- Add check constraint for language_preference
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'chk_users_language_preference'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT chk_users_language_preference
            CHECK (language_preference IN ('en', 'id', 'it', 'es', 'fr', 'de', 'ja', 'zh', 'uk', 'ru'));
    END IF;

    -- Add check constraint for status
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'chk_users_status'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT chk_users_status
            CHECK (status IN ('active', 'inactive', 'suspended', 'terminated'));
    END IF;

    -- Add check constraint for role_level
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'chk_users_role_level'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT chk_users_role_level
            CHECK (role_level IN ('executive', 'director', 'manager', 'senior', 'intermediate', 'junior', 'member'));
    END IF;
END $$;

-- ========================================
-- 6. MIGRATION COMPLETION
-- ========================================

-- Record migration completion
INSERT INTO migration_log (
    migration_name,
    checksum,
    notes
) VALUES (
    'migration_v5_3_final',
    md5('zantara_v5_3_ultra_hybrid_final_migration'),
    'Zantara v5.3 Ultra Hybrid - Complete user profiles, feedback system, and analytics tables'
) ON CONFLICT (migration_name) DO NOTHING;

-- Provide migration summary
DO $$
DECLARE
    user_count INTEGER;
    feedback_table_exists BOOLEAN;
    analytics_table_exists BOOLEAN;
BEGIN
    -- Count users
    SELECT COUNT(*) INTO user_count FROM users WHERE status = 'active';

    -- Check table existence
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'knowledge_feedback'
    ) INTO feedback_table_exists;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'query_analytics'
    ) INTO analytics_table_exists;

    RAISE NOTICE '=== ZANTARA v5.3 MIGRATION SUMMARY ===';
    RAISE NOTICE 'Active Users: %', user_count;
    RAISE NOTICE 'Knowledge Feedback Table: %', CASE WHEN feedback_table_exists THEN '✅ Created' ELSE '❌ Failed' END;
    RAISE NOTICE 'Query Analytics Table: %', CASE WHEN analytics_table_exists THEN '✅ Created' ELSE '❌ Failed' END;
    RAISE NOTICE 'Migration Status: ✅ SUCCESS';
    RAISE NOTICE '========================================';
END $$;

COMMIT;

-- ========================================
-- VERIFICATION QUERIES (Optional)
-- ========================================

-- Uncomment to verify migration success
/*
-- Verify all team members are properly configured
SELECT
    email,
    name,
    role,
    language_preference,
    meta_json->>'language' as meta_language,
    meta_json->>'tone' as meta_tone,
    meta_json->>'notes' as meta_notes
FROM users
WHERE status = 'active'
ORDER BY role_level, name;

-- Verify feedback table structure
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'knowledge_feedback'
ORDER BY ordinal_position;
*/
