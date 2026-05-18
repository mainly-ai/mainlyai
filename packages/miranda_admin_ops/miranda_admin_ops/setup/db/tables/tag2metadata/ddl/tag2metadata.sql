-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS tag2metadata (
    ID INTEGER AUTO_INCREMENT,
    user_id         INT,
    tag             VARCHAR(24) NOT NULL,
    wob_type        VARCHAR(24) NOT NULL,
    metadata_id     INTEGER NOT NULL,
    PRIMARY KEY (ID,user_id),
    UNIQUE (user_id, tag, metadata_id),
    FOREIGN KEY (metadata_id) REFERENCES metadata(ID) ON DELETE CASCADE
)