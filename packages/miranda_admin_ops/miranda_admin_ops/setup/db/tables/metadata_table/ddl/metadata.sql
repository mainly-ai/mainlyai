-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS metadata (
        ID              INTEGER AUTO_INCREMENT PRIMARY KEY,
        Created_by_id   INTEGER DEFAULT -1,
        Last_used       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        Last_updated    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        Time_created    DATETIME DEFAULT CURRENT_TIMESTAMP,
        Deleted         BOOLEAN DEFAULT FALSE,
        Name            VARCHAR(255),
        Description     TEXT,
        status          JSON DEFAULT NULL,
        cloned_from_id  INTEGER DEFAULT -1,
        FULLTEXT (Name, Description),
        INDEX idx_metadata_deleted_id (Deleted, ID),
        INDEX idx_metadata_last_updated (Last_updated),
        INDEX idx_metadata_cloned_from_id (cloned_from_id),
        INDEX idx_metadata_created_by_id (Created_by_id)
)