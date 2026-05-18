-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS miranda.deployment (
    ID              INTEGER auto_increment primary key,
    metadata_id     INTEGER NOT NULL,
    public          boolean DEFAULT FALSE,
    workflow_state  ENUM ('UNDEPLOYED', 'DEPLOYING', 'FAILED', 'DEPLOYED', 'STOPPING', 'STOPPED') DEFAULT 'UNDEPLOYED',
    deployed_at     DATETIME DEFAULT NULL,
    deployed_by     INTEGER NOT NULL,
    pod_id          VARCHAR(26),
    FOREIGN KEY (metadata_id)
        REFERENCES metadata(id)
        ON DELETE CASCADE
)