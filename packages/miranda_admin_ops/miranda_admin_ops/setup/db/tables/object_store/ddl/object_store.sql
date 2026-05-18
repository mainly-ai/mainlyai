-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS object_store (
    ID INTEGER NOT NULL AUTO_INCREMENT,
    storage_id INTEGER DEFAULT NULL,
    file_path varchar(255) DEFAULT NULL,
    content longblob,
    PRIMARY KEY (ID), UNIQUE(`storage_id`,`file_path`)
)