-- Nuzantara Prime: Update Zoning Layers with Real Tech Codes

ALTER TABLE bali_zoning_layers 
    ADD COLUMN IF NOT EXISTS document_url VARCHAR(255),
    ADD COLUMN IF NOT EXISTS kdb VARCHAR(50),
    ADD COLUMN IF NOT EXISTS klb VARCHAR(50),
    ADD COLUMN IF NOT EXISTS kdh VARCHAR(50),
    ADD COLUMN IF NOT EXISTS kodszn VARCHAR(50);
