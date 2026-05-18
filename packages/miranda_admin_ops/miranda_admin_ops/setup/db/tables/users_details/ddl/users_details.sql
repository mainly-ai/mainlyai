-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS users_details (
    ID              INTEGER AUTO_INCREMENT,
    user_id         INTEGER,
    first_name      VARCHAR(40),
    last_name       VARCHAR(40),
    email           VARCHAR(80),
    phone           VARCHAR(40),
    industry        VARCHAR(40),
    role            VARCHAR(40),
    account_status  VARCHAR(40),
    consented       BOOLEAN NOT NULL DEFAULT FALSE,
    avatar          VARCHAR(255) NOT NULL DEFAULT "https://mainly-web-assets.s3.eu-north-1.amazonaws.com/avatars/default.png",
    PRIMARY KEY (ID),
    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
)