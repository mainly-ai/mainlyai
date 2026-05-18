-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS dashboard (
    ID                          INTEGER auto_increment,
    metadata_id                 INTEGER NOT NULL,
    `order`                     INTEGER DEFAULT 0,
    layout                      JSON,
    workflow_state              VARCHAR(80) DEFAULT 'ONLINE',
    `type`                      VARCHAR(40) DEFAULT 'DASHBOARD',
    PRIMARY KEY (ID, metadata_id),
    FOREIGN KEY (metadata_id)
        REFERENCES metadata(id)
        ON DELETE CASCADE
)