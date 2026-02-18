INSERT INTO organizations (name) VALUES ('Fish Co');
INSERT INTO users (email, password_hash, organization_id) VALUES ('admin@fishco.com', 'hashed_secret', 1);
INSERT INTO devices (name, user_id) VALUES ('Pond 1 Sensor', 1);
