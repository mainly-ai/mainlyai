-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS file_chunks (
    ID              INTEGER primary key auto_increment,
    file_id         INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL,
    chunk_size      INTEGER NOT NULL,
    chunk           BLOB
)