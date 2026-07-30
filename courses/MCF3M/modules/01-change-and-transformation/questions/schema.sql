-- MCF3M Module 1 question bank schema
-- Links async examples / formatives / practice to curriculum expectations
-- and Module 1 assessment artifact types (Rate-of-Change, Turning Point, Transformation).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sections (
    section_key TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    student_title TEXT NOT NULL,
    weight_percent INTEGER NOT NULL,
    sort_order INTEGER NOT NULL,
    intro_html TEXT NOT NULL,
    hook_html TEXT NOT NULL,
    hook_kind TEXT NOT NULL DEFAULT 'reflection'
);

-- Optional within-section beats (e.g. Expanding / Factoring / CTS).
-- When present, learning + examples + formatives render interleaved per subsection.
CREATE TABLE IF NOT EXISTS subsections (
    subsection_key TEXT PRIMARY KEY,
    section_key TEXT NOT NULL REFERENCES sections(section_key),
    title TEXT NOT NULL,
    intro_html TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_key TEXT NOT NULL REFERENCES sections(section_key),
    kind TEXT NOT NULL CHECK (kind IN ('khan','youtube','desmos','other')),
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    embed_url TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    -- For Desmos: overall activity ask shown up front. For KA/YouTube: author notes only (not chrome).
    notes TEXT,
    -- Required for kind=desmos: calculator how-to steps (HTML), shown in expandable <details>.
    interaction_steps_html TEXT,
    -- Same non-empty content_group → tabbed alternate modalities of one idea.
    -- Different / empty groups → separate sequential Explore blocks.
    content_group TEXT,
    block_title TEXT,
    -- Optional link to subsections.subsection_key (nullable for flat sections).
    subsection_key TEXT REFERENCES subsections(subsection_key)
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    smart_id TEXT NOT NULL UNIQUE,
    module_id TEXT NOT NULL DEFAULT 'M1',
    section_key TEXT NOT NULL REFERENCES sections(section_key),
    item_type TEXT NOT NULL CHECK (item_type IN ('example','formative','practice')),
    subtype TEXT NOT NULL DEFAULT 'conceptual',
    title TEXT NOT NULL,
    stem_html TEXT NOT NULL,
    solution_html TEXT,
    formative_json TEXT,
    difficulty INTEGER NOT NULL DEFAULT 2 CHECK (difficulty BETWEEN 1 AND 5),
    source TEXT,
    artifact_tags_json TEXT NOT NULL DEFAULT '[]',
    -- Similar-topic practice cluster label for accordion presentation (nullable).
    cluster_title TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    -- Optional link to subsections.subsection_key (nullable for flat sections).
    subsection_key TEXT REFERENCES subsections(subsection_key)
);

CREATE TABLE IF NOT EXISTS item_expectations (
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    expectation_code TEXT NOT NULL,
    PRIMARY KEY (item_id, expectation_code)
);

CREATE INDEX IF NOT EXISTS idx_items_section ON items(section_key, item_type, sort_order);
CREATE INDEX IF NOT EXISTS idx_items_smart_id ON items(smart_id);
CREATE INDEX IF NOT EXISTS idx_item_expectations_code ON item_expectations(expectation_code);
