-- SQL Migration to add ai_quality_label to the sensor_readings table.
-- Please run this block of SQL exactly once in your Railway Database Query tab.

ALTER TABLE sensor_readings ADD COLUMN IF NOT EXISTS ai_quality_label VARCHAR(20);
COMMENT ON COLUMN sensor_readings.ai_quality_label IS 'Water quality AI-assessed label based on core metrics';
