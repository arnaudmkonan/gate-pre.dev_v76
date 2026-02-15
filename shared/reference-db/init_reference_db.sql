-- GATE Shared Reference Database Initialization
-- This creates the centralized reference tables for HTS, NAICS, and SDN data

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy text matching

-- ==================== HTS CODES ====================
CREATE TABLE IF NOT EXISTS hts_codes (
    id SERIAL PRIMARY KEY,
    hts_code VARCHAR(20) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    chapter INTEGER,
    duty_rate VARCHAR(100),
    duty_rate_percent NUMERIC(10, 4),
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_hts_codes_code ON hts_codes(hts_code);
CREATE INDEX idx_hts_codes_chapter ON hts_codes(chapter);
CREATE INDEX idx_hts_codes_description_trgm ON hts_codes USING gin(description gin_trgm_ops);

-- ==================== NAICS CODES ====================
CREATE TABLE IF NOT EXISTS naics_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    sector VARCHAR(200),
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_naics_codes_code ON naics_codes(code);
CREATE INDEX idx_naics_codes_sector ON naics_codes(sector);
CREATE INDEX idx_naics_codes_title_trgm ON naics_codes USING gin(title gin_trgm_ops);

-- ==================== OFAC SDN ====================
CREATE TABLE IF NOT EXISTS ofac_sdn (
    id SERIAL PRIMARY KEY,
    sdn_name VARCHAR(500) NOT NULL,
    sdn_type VARCHAR(50),
    program VARCHAR(500),
    title VARCHAR(200),
    aliases JSONB DEFAULT '[]',
    addresses JSONB DEFAULT '[]',
    nationality VARCHAR(100),
    citizenship VARCHAR(100),
    date_of_birth VARCHAR(100),
    place_of_birth VARCHAR(200),
    id_numbers JSONB DEFAULT '[]',
    remarks TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ofac_sdn_name ON ofac_sdn(sdn_name);
CREATE INDEX idx_ofac_sdn_type ON ofac_sdn(sdn_type);
CREATE INDEX idx_ofac_sdn_program ON ofac_sdn(program);
CREATE INDEX idx_ofac_sdn_active ON ofac_sdn(is_active);
CREATE INDEX idx_ofac_sdn_name_trgm ON ofac_sdn USING gin(sdn_name gin_trgm_ops);

-- ==================== AD/CVD ORDERS ====================
-- Antidumping and Countervailing Duty orders
CREATE TABLE IF NOT EXISTS adcvd_orders (
    id SERIAL PRIMARY KEY,
    case_number VARCHAR(50) NOT NULL UNIQUE,
    order_type VARCHAR(10) NOT NULL,  -- 'AD' or 'CVD'
    country_of_origin VARCHAR(100) NOT NULL,
    product_description TEXT NOT NULL,
    hts_codes TEXT[],  -- Array of applicable HTS codes
    duty_rate_percent NUMERIC(10, 4),
    effective_date DATE,
    status VARCHAR(20) DEFAULT 'active',  -- active, revoked, suspended
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_adcvd_case ON adcvd_orders(case_number);
CREATE INDEX idx_adcvd_country ON adcvd_orders(country_of_origin);
CREATE INDEX idx_adcvd_status ON adcvd_orders(status);

-- ==================== SECTION 301/232 TARIFFS ====================
CREATE TABLE IF NOT EXISTS tariff_exclusions (
    id SERIAL PRIMARY KEY,
    section VARCHAR(10) NOT NULL,  -- '301', '232'
    hts_code VARCHAR(20) NOT NULL,
    country VARCHAR(100),
    product_description TEXT,
    exclusion_type VARCHAR(50),  -- 'excluded', 'subject'
    tariff_rate NUMERIC(10, 4),
    effective_date DATE,
    expiration_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tariff_section ON tariff_exclusions(section);
CREATE INDEX idx_tariff_hts ON tariff_exclusions(hts_code);
CREATE INDEX idx_tariff_country ON tariff_exclusions(country);

-- ==================== CREATE READ-ONLY USER FOR TENANTS ====================
-- This user will be used by tenant databases via FDW
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'reference_reader') THEN
        CREATE ROLE reference_reader WITH LOGIN PASSWORD 'reference_reader_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE gate_reference TO reference_reader;
GRANT USAGE ON SCHEMA public TO reference_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reference_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO reference_reader;

-- ==================== SAMPLE DATA (for testing) ====================
-- Insert some sample HTS codes
INSERT INTO hts_codes (hts_code, description, chapter, duty_rate, duty_rate_percent) VALUES
    ('0101.21.00', 'Live horses, purebred breeding', 1, 'Free', 0),
    ('0201.10.05', 'Bovine carcasses fresh/chilled', 2, '4%', 4.0),
    ('0301.11.00', 'Live ornamental freshwater fish', 3, 'Free', 0),
    ('6110.20.20', 'Cotton sweaters, knit', 61, '16.5%', 16.5),
    ('8471.30.01', 'Portable automatic data processors', 84, 'Free', 0),
    ('8517.12.00', 'Cellular telephones', 85, 'Free', 0),
    ('9401.71.00', 'Upholstered seats with metal frames', 94, 'Free', 0)
ON CONFLICT (hts_code) DO NOTHING;

-- Insert some sample NAICS codes
INSERT INTO naics_codes (code, title, description, sector) VALUES
    ('111110', 'Soybean Farming', 'Growing soybeans', 'Agriculture'),
    ('311511', 'Fluid Milk Manufacturing', 'Processing and bottling fluid milk', 'Manufacturing'),
    ('423110', 'Automobile and Parts Wholesalers', 'Wholesale distribution of motor vehicles', 'Wholesale Trade'),
    ('481111', 'Scheduled Passenger Air Transportation', 'Scheduled air passenger transportation', 'Transportation'),
    ('541511', 'Custom Computer Programming Services', 'Writing, modifying computer software', 'Professional Services')
ON CONFLICT (code) DO NOTHING;

-- Insert some sample OFAC SDN entries (fictional for testing)
INSERT INTO ofac_sdn (sdn_name, sdn_type, program, is_active) VALUES
    ('TEST ENTITY ONE', 'Entity', 'SDGT', FALSE),
    ('TEST PERSON TWO', 'Individual', 'CUBA', FALSE)
ON CONFLICT DO NOTHING;

SELECT 'Reference database initialized successfully' as status;
