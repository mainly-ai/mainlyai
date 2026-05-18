-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS vault_object (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    vault_id BIGINT UNSIGNED NOT NULL,
    filename VARCHAR(512) NOT NULL,
    size BIGINT UNSIGNED DEFAULT 0 NOT NULL,
  	content_type VARCHAR(256) NOT NULL,
    tag VARCHAR(256),
    PRIMARY KEY (id),
    UNIQUE(`vault_id`,`filename`)
);