-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS edges (
    src_type        ENUM ('CODE', 'KNOWLEDGE_OBJECT', 'DOCKER_JOB','DEPLOYMENT', 'COMPUTE_POLICY', 'PROJECT', 'STORAGE_POLICY', 'COMPUTE_RESOURCE_GROUP', 'DOCKER_IMAGE') DEFAULT 'KNOWLEDGE_OBJECT',
    dest_type       ENUM ('CODE', 'KNOWLEDGE_OBJECT', 'DOCKER_JOB','DEPLOYMENT', 'COMPUTE_POLICY', 'PROJECT', 'STORAGE_POLICY', 'COMPUTE_RESOURCE_GROUP', 'DOCKER_IMAGE') DEFAULT 'KNOWLEDGE_OBJECT',
    src_id          INTEGER NOT NULL,
    dest_id         INTEGER NOT NULL,
    etl_id          INTEGER DEFAULT NULL,
    attributes      JSON,
    edge_key        VARCHAR(255)  GENERATED ALWAYS AS (CONCAT(src_id, '-', dest_id)) VIRTUAL,
    PRIMARY KEY(src_id,dest_id),
    KEY(dest_type),
    KEY(edge_key),
    FOREIGN KEY (src_id)
        REFERENCES metadata(id)
        ON DELETE CASCADE,
    FOREIGN KEY (dest_id)
        REFERENCES metadata(id)
        ON DELETE CASCADE
)
