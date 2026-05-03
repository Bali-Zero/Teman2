-- Nuzantara Prime: Geospatial Zoning Layer

-- 1. Enable PostGIS extension for Geospatial queries
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Create the Zoning table
CREATE TABLE IF NOT EXISTS bali_zoning_layers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    district_name VARCHAR(255) NOT NULL,
    subdistrict_name VARCHAR(255),
    zoning_type VARCHAR(100) NOT NULL, -- e.g., 'Green Zone', 'Tourism', 'Commercial'
    allowed_kbli JSONB,                -- List of flat KBLI codes permitted here
    boundary GEOMETRY(Geometry, 4326),  -- 4326 = WGS 84 (Standard Google Maps Lat/Lng) - supports Polygon + MultiPolygon
    avg_price_per_are DECIMAL,         -- Contextual data for Prime
    risk_score FLOAT,                  -- AI calculated risk score
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Add spatial index for fast intersection queries
CREATE INDEX IF NOT EXISTS bali_zoning_boundary_idx 
ON bali_zoning_layers USING GIST (boundary);

-- 4. Add index for KBLI lookups
CREATE INDEX IF NOT EXISTS bali_zoning_kbli_idx 
ON bali_zoning_layers USING GIN (allowed_kbli);
