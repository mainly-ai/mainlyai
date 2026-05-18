-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS gri_topic (
    ID              INTEGER AUTO_INCREMENT PRIMARY KEY,
    Codename        VARCHAR(80),
    Last_used       DATETIME DEFAULT CURRENT_TIMESTAMP,
    Last_updated    DATETIME DEFAULT CURRENT_TIMESTAMP,
    Time_created    DATETIME DEFAULT CURRENT_TIMESTAMP,
    Type            VARCHAR(80),
    Description     TEXT,
    Year			INTEGER
);