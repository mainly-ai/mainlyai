# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.table_exists(utilities.admin_sc, "storage_policy"):
  with utilities.admin_sc.connect() as con:
    with con.cursor() as cur:
      cur.execute("DROP TABLE IF EXISTS storage_policy")

with utilities.admin_sc.connect() as con:
  with con.cursor() as cur:
    cur.execute("""
    CREATE TABLE IF NOT EXISTS `storage_policy` (
      `id` int NOT NULL AUTO_INCREMENT,
      `metadata_id` int NOT NULL,
      `storage_type` enum('VAULT', 'SSH') DEFAULT NULL,
      `mount_point` varchar(255) DEFAULT NULL,
      `details` json DEFAULT NULL,
      `workflow_state` enum('UNPROVISIONED', 'UNUSABLE', 'READY') DEFAULT 'UNPROVISIONED',
      PRIMARY KEY (`ID`,`metadata_id`),
      KEY `metadata_id` (`metadata_id`),
      FOREIGN KEY (`metadata_id`) REFERENCES `metadata` (`ID`) ON DELETE CASCADE
    )""")