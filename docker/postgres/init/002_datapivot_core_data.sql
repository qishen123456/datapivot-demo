CREATE TABLE IF NOT EXISTS datapivot_core_data (
    id BIGSERIAL PRIMARY KEY,
    record_id TEXT UNIQUE,
    fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_datapivot_core_data_fields
    ON datapivot_core_data USING GIN (fields);
