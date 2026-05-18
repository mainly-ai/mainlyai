-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS ko_gri (
    ID                  INTEGER AUTO_INCREMENT PRIMARY KEY,
    ko_ID               VARCHAR (80),
    gri_requirement_ID  VARCHAR (80),
    sdg_target_ID       VARCHAR (200)
);