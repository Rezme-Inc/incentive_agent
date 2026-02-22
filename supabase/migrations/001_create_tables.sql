-- Incentive Agent Schema — 4 core tables
-- Run this in Supabase SQL Editor

-- 1. Jurisdictions: hierarchical location tree
CREATE TABLE jurisdictions (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('federal', 'state', 'county', 'city')),
    parent_id INTEGER REFERENCES jurisdictions(id),
    state_code CHAR(2),          -- e.g. 'AZ', NULL for federal
    fips_code TEXT,               -- census FIPS code (optional, useful later)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, level, parent_id)
);

CREATE INDEX idx_jurisdictions_level ON jurisdictions(level);
CREATE INDEX idx_jurisdictions_state_code ON jurisdictions(state_code);
CREATE INDEX idx_jurisdictions_parent ON jurisdictions(parent_id);

-- 2. Target populations: canonical list
CREATE TABLE target_populations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT               -- e.g. 'military', 'justice-involved', 'economic'
);

-- Seed the standard populations
INSERT INTO target_populations (name, category) VALUES
    ('veterans', 'military'),
    ('people with disabilities', 'disability'),
    ('ex-offenders', 'justice-involved'),
    ('returning citizens', 'justice-involved'),
    ('TANF recipients', 'economic'),
    ('SNAP recipients', 'economic'),
    ('SSI recipients', 'economic'),
    ('youth (18-24)', 'age'),
    ('long-term unemployed', 'economic'),
    ('dislocated workers', 'economic'),
    ('people in recovery', 'health'),
    ('those with poor credit', 'economic'),
    ('low-income adults', 'economic');

-- 3. Programs: the core data
CREATE TABLE programs (
    id TEXT PRIMARY KEY,          -- deterministic SHA-256 hash
    jurisdiction_id INTEGER NOT NULL REFERENCES jurisdictions(id),
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    agency TEXT DEFAULT '',
    benefit_type TEXT DEFAULT 'unknown' CHECK (benefit_type IN ('tax_credit', 'wage_subsidy', 'training_grant', 'bonding', 'other', 'unknown')),
    max_value TEXT DEFAULT '',
    description TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'expired', 'unknown')),
    confidence TEXT DEFAULT 'low' CHECK (confidence IN ('high', 'medium', 'low')),
    first_discovered_at TIMESTAMPTZ DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ DEFAULT NOW(),
    discovery_count INTEGER DEFAULT 1,
    miss_count INTEGER DEFAULT 0,
    UNIQUE(name_normalized, jurisdiction_id)
);

CREATE INDEX idx_programs_jurisdiction ON programs(jurisdiction_id);
CREATE INDEX idx_programs_benefit_type ON programs(benefit_type);
CREATE INDEX idx_programs_status ON programs(status);
CREATE INDEX idx_programs_confidence ON programs(confidence);
CREATE INDEX idx_programs_name_normalized ON programs(name_normalized);

-- 4. Program populations: many-to-many
CREATE TABLE program_populations (
    program_id TEXT NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    population_id INTEGER NOT NULL REFERENCES target_populations(id) ON DELETE CASCADE,
    PRIMARY KEY (program_id, population_id)
);

CREATE INDEX idx_program_populations_population ON program_populations(population_id);

-- Seed federal jurisdiction
INSERT INTO jurisdictions (name, level, state_code) VALUES ('United States', 'federal', NULL);

-- Seed all 50 states + DC
INSERT INTO jurisdictions (name, level, state_code, parent_id) VALUES
    ('Alabama', 'state', 'AL', 1),
    ('Alaska', 'state', 'AK', 1),
    ('Arizona', 'state', 'AZ', 1),
    ('Arkansas', 'state', 'AR', 1),
    ('California', 'state', 'CA', 1),
    ('Colorado', 'state', 'CO', 1),
    ('Connecticut', 'state', 'CT', 1),
    ('Delaware', 'state', 'DE', 1),
    ('Florida', 'state', 'FL', 1),
    ('Georgia', 'state', 'GA', 1),
    ('Hawaii', 'state', 'HI', 1),
    ('Idaho', 'state', 'ID', 1),
    ('Illinois', 'state', 'IL', 1),
    ('Indiana', 'state', 'IN', 1),
    ('Iowa', 'state', 'IA', 1),
    ('Kansas', 'state', 'KS', 1),
    ('Kentucky', 'state', 'KY', 1),
    ('Louisiana', 'state', 'LA', 1),
    ('Maine', 'state', 'ME', 1),
    ('Maryland', 'state', 'MD', 1),
    ('Massachusetts', 'state', 'MA', 1),
    ('Michigan', 'state', 'MI', 1),
    ('Minnesota', 'state', 'MN', 1),
    ('Mississippi', 'state', 'MS', 1),
    ('Missouri', 'state', 'MO', 1),
    ('Montana', 'state', 'MT', 1),
    ('Nebraska', 'state', 'NE', 1),
    ('Nevada', 'state', 'NV', 1),
    ('New Hampshire', 'state', 'NH', 1),
    ('New Jersey', 'state', 'NJ', 1),
    ('New Mexico', 'state', 'NM', 1),
    ('New York', 'state', 'NY', 1),
    ('North Carolina', 'state', 'NC', 1),
    ('North Dakota', 'state', 'ND', 1),
    ('Ohio', 'state', 'OH', 1),
    ('Oklahoma', 'state', 'OK', 1),
    ('Oregon', 'state', 'OR', 1),
    ('Pennsylvania', 'state', 'PA', 1),
    ('Rhode Island', 'state', 'RI', 1),
    ('South Carolina', 'state', 'SC', 1),
    ('South Dakota', 'state', 'SD', 1),
    ('Tennessee', 'state', 'TN', 1),
    ('Texas', 'state', 'TX', 1),
    ('Utah', 'state', 'UT', 1),
    ('Vermont', 'state', 'VT', 1),
    ('Virginia', 'state', 'VA', 1),
    ('Washington', 'state', 'WA', 1),
    ('West Virginia', 'state', 'WV', 1),
    ('Wisconsin', 'state', 'WI', 1),
    ('Wyoming', 'state', 'WY', 1),
    ('District of Columbia', 'state', 'DC', 1);
