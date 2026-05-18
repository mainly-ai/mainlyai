-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS gri_requirement (
    ID              INTEGER AUTO_INCREMENT PRIMARY KEY,
    Identifier		VARCHAR(20),
    Description     TEXT,
    Last_used       DATETIME DEFAULT CURRENT_TIMESTAMP,
    Last_updated    DATETIME DEFAULT CURRENT_TIMESTAMP,
    Time_created    DATETIME DEFAULT CURRENT_TIMESTAMP,
    Terms           VARCHAR(300),
    ValueRange      VARCHAR(80),
    Cardinality	    VARCHAR(20),
    Category_ID     VARCHAR(10),
    Disclosure_ID   VARCHAR(20),
    Requirement_Dependency VARCHAR(1000)
);