ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS google_id VARCHAR(100) UNIQUE;

-- Enforce 10-digit phone number check (Uganda format 07XXXXXXXX)
ALTER TABLE users
    DROP CONSTRAINT IF EXISTS user_phone_check;
ALTER TABLE users
    ADD CONSTRAINT user_phone_check
    CHECK (phone IS NULL OR phone ~ '^[0-9]{10}$');

-- OTP Verifications Table
CREATE TABLE IF NOT EXISTS otp_verifications (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    otp_code    VARCHAR(6) NOT NULL,
    purpose     VARCHAR(20) DEFAULT 'password_reset',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP NOT NULL,
    is_used     BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_otp_verifications_user 
    ON otp_verifications(user_id, otp_code, is_used);
