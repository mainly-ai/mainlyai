-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS proxy_account_claims (
    name                VARCHAR(32) NOT NULL,
    belonging_to        VARCHAR(32) NOT NULL,
    at                  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    by_application      VARCHAR(255)
)