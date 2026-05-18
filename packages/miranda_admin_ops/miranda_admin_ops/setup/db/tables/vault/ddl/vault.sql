-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS vault (
	id SERIAL PRIMARY KEY,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
	deleted_at TIMESTAMP,
	name VARCHAR(255) NOT NULL,
	owner_org_id INT NOT NULL,
	max_storage FLOAT NOT NULL,
	storage_used FLOAT NOT NULL,
	access_key_id VARCHAR(64) NOT NULL,
	INDEX (access_key_id),
	secret_access_key VARCHAR(64) NOT NULL,
	FOREIGN KEY (owner_org_id) REFERENCES organization(id)
)