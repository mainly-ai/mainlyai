-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS miranda_web.web_users (
    username    VARCHAR(40) primary key,
    auth        VARCHAR(64),
    salt        VARCHAR(64),
    jwt_secret  VARCHAR(64),
    db_secret   VARCHAR(64),
    login_time  DATETIME DEFAULT NULL,
    logout_time DATETIME DEFAULT NULL,
    is_admin    boolean DEFAULT FALSE
)