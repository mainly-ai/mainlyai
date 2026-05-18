-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS miranda_logs (
        ID              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        User_id         INTEGER NOT NULL,
        Created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        Tag             SMALLINT DEFAULT 0,
        Class_id        SMALLINT NOT NULL,
        Instance_id     INTEGER NOT NULL,
        Message         TEXT
)