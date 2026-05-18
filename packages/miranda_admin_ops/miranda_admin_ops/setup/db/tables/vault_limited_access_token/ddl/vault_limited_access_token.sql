-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS vault_limited_access_token (
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
	expires_at TIMESTAMP NOT NULL, 
	token CHAR(64) NOT NULL PRIMARY KEY,
	vault_id BIGINT UNSIGNED NOT NULL,
	object_id BIGINT UNSIGNED,
	permissions SET('ReadObject', 'UploadObject', 'DeleteObject') NOT NULL,
	FOREIGN KEY (vault_id) REFERENCES vault(id) ON DELETE CASCADE,
	FOREIGN KEY (object_id) REFERENCES vault_object(id) ON DELETE CASCADE
)