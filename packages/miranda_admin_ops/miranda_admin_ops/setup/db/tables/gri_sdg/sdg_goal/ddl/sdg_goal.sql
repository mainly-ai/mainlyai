-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS sdg_goal (
    ID                  INTEGER AUTO_INCREMENT PRIMARY KEY,
    identifier          VARCHAR(20),
    title               VARCHAR(50),
    color               VARCHAR(7),
    description         TEXT,
    targets             VARCHAR(200)
);