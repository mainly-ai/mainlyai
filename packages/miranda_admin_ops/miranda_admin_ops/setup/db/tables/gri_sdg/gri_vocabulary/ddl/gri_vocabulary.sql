-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS gri_vocabulary (
    ID              INTEGER AUTO_INCREMENT PRIMARY KEY,
    Identifier		VARCHAR(80),
    Quality         VARCHAR(80),
    Metric			VARCHAR(20),
    Description     TEXT,
    hasRelativeTerm VARCHAR(10),
    Last_used       DATETIME DEFAULT CURRENT_TIMESTAMP,
    Last_updated    DATETIME DEFAULT CURRENT_TIMESTAMP,
    Time_created    DATETIME DEFAULT CURRENT_TIMESTAMP
);