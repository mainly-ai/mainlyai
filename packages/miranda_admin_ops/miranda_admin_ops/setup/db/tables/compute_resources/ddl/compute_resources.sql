-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS compute_resources (
    ID                  INTEGER PRIMARY KEY AUTO_INCREMENT,
    host                VARCHAR(128) NOT NULL,
    last_used           DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_docker_job_id  INTEGER DEFAULT -1,
    hardware_description JSON,
    locked              BOOLEAN DEFAULT FALSE,
    error_count         INTEGER DEFAULT 0,
    last_error          DATETIME DEFAULT NULL,
    is_up               BOOLEAN DEFAULT FALSE,
    last_up             DATETIME DEFAULT NULL,
    base_docker_image   INTEGER
)