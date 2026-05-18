-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS knowledge_object (
    ID              INTEGER auto_increment,
    metadata_id     INTEGER NOT NULL,
    type            INT DEFAULT 0,
    sdg             VARCHAR(20) DEFAULT "",
    origin_project_id INTEGER DEFAULT -1,
    PRIMARY KEY (ID,metadata_id),
    FOREIGN KEY (metadata_id)
        REFERENCES metadata(id)
        ON DELETE CASCADE
)