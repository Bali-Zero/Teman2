-- CRM System Schema for ZANTARA
-- Run this SQL on the PostgreSQL database to create CRM tables

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create clients table
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    whatsapp VARCHAR(50),
    nationality VARCHAR(100),
    passport_number VARCHAR(100),
    assigned_to VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    tags TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255),
    deleted_at TIMESTAMP WITH TIME ZONE,
    deleted_by VARCHAR(255)
);

-- Create indexes for clients
CREATE INDEX IF NOT EXISTS idx_clients_email ON clients(email);
CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);
CREATE INDEX IF NOT EXISTS idx_clients_assigned_to ON clients(assigned_to);
CREATE INDEX IF NOT EXISTS idx_clients_created_at ON clients(created_at);

-- Create practice_types table
CREATE TABLE IF NOT EXISTS practice_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    base_price DECIMAL(12, 2),
    typical_duration_days INTEGER,
    required_documents TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial practice types
INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, required_documents) VALUES
('kitas_application', 'KITAS Visa Application', 'Indonesian limited stay visa application', 'visa', 1500.00, 30, ARRAY['passport', 'photos', 'sponsor_letter', 'bank_statement']),
('kitap_application', 'KITAP Permanent Permit', 'Indonesian permanent stay permit application', 'visa', 2500.00, 60, ARRAY['passport', 'kitas', 'photos', 'tax_reports']),
('pt_pma_setup', 'PT PMA Company Setup', 'Foreign investment company establishment', 'corporate', 3000.00, 45, ARRAY['passport', 'ktp', 'npwp', 'company_plan']),
('property_purchase', 'Property Purchase', 'Real estate transaction assistance', 'property', 2000.00, 30, ARRAY['passport', 'npwp', 'identity_card']),
('tax_consulting', 'Tax Consulting', 'Tax planning and compliance services', 'tax', 1000.00, 14, ARRAY['financial_documents', 'previous_tax_returns'])
ON CONFLICT (code) DO NOTHING;

-- Create indexes for practice_types
CREATE INDEX IF NOT EXISTS idx_practice_types_code ON practice_types(code);
CREATE INDEX IF NOT EXISTS idx_practice_types_category ON practice_types(category);
CREATE INDEX IF NOT EXISTS idx_practice_types_active ON practice_types(is_active);

-- Create practices table
CREATE TABLE IF NOT EXISTS practices (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    practice_type_code VARCHAR(50) REFERENCES practice_types(code),
    title VARCHAR(255),
    description TEXT,
    status VARCHAR(50) DEFAULT 'inquiry',
    priority VARCHAR(20) DEFAULT 'normal',
    quoted_price DECIMAL(12, 2),
    final_price DECIMAL(12, 2),
    currency VARCHAR(3) DEFAULT 'USD',
    assigned_to VARCHAR(255),
    start_date DATE,
    expected_completion_date DATE,
    actual_completion_date DATE,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255)
);

-- Create indexes for practices
CREATE INDEX IF NOT EXISTS idx_practices_client_id ON practices(client_id);
CREATE INDEX IF NOT EXISTS idx_practices_status ON practices(status);
CREATE INDEX IF NOT EXISTS idx_practices_type_code ON practices(practice_type_code);
CREATE INDEX IF NOT EXISTS idx_practices_assigned_to ON practices(assigned_to);
CREATE INDEX IF NOT EXISTS idx_practices_created_at ON practices(created_at);

-- Create interactions table
CREATE TABLE IF NOT EXISTS interactions (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL,
    type VARCHAR(50) NOT NULL,
    channel VARCHAR(50) DEFAULT 'web_chat',
    title VARCHAR(255),
    content TEXT NOT NULL,
    direction VARCHAR(20) DEFAULT 'inbound',
    sentiment VARCHAR(20),
    priority VARCHAR(20) DEFAULT 'normal',
    duration_minutes INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255)
);

-- Create indexes for interactions
CREATE INDEX IF NOT EXISTS idx_interactions_client_id ON interactions(client_id);
CREATE INDEX IF NOT EXISTS idx_interactions_practice_id ON interactions(practice_id);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions(type);
CREATE INDEX IF NOT EXISTS idx_interactions_channel ON interactions(channel);
CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON interactions(created_at);
CREATE INDEX IF NOT EXISTS idx_interactions_direction ON interactions(direction);

-- Create update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers
DROP TRIGGER IF EXISTS update_clients_updated_at ON clients;
CREATE TRIGGER update_clients_updated_at BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_practices_updated_at ON practices;
CREATE TRIGGER update_practices_updated_at BEFORE UPDATE ON practices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_practice_types_updated_at ON practice_types;
CREATE TRIGGER update_practice_types_updated_at BEFORE UPDATE ON practice_types
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Verify tables created
SELECT 'CRM tables created successfully!' as status;
