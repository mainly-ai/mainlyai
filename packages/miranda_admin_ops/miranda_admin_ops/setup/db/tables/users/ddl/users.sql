-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS users (
    ID              INTEGER primary key auto_increment,
    username        VARCHAR(40) UNIQUE,
    organization_id INTEGER NOT NULL,
    auth            VARCHAR(255),
    salt            VARCHAR(64)
)