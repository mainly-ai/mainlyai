-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS miranda_web.credentials (
  id           INT                      AUTO_INCREMENT,
  kind         ENUM('TOTP', 'WEBAUTHN') NOT NULL,
  belonging_to VARCHAR(32)              NOT NULL,
  secret       VARCHAR(255)             NOT NULL,
  name         VARCHAR(64)              NULL,
  metadata     json                     NULL,
  time_created DATETIME                 DEFAULT CURRENT_TIMESTAMP,
  last_used    DATETIME                 DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT id
    PRIMARY KEY (id)
);