# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.table_exists(utilities.admin_sc, "designer_edge_segments"):
    with utilities.admin_sc.connect() as con:
        with con.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS miranda_web.designer_edge_segments (
                `project_id`  INT NOT NULL,
                `src_id`      INT NOT NULL,
                `src_handle`  VARCHAR(255) NOT NULL,
                `dest_id`     INT NOT NULL,
                `dest_handle` VARCHAR(255) NOT NULL,
                `segments`    TEXT NOT NULL,
                PRIMARY KEY (`project_id`, `src_id`, `src_handle`, `dest_id`, `dest_handle`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
