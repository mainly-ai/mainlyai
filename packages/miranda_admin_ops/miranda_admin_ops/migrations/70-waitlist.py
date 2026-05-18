# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.table_exists(utilities.admin_sc, "waitlist"):
    with utilities.admin_sc.connect() as con:
        with con.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS miranda_web.waitlist (
                    email               VARCHAR(255) NOT NULL PRIMARY KEY,
                    first_name          VARCHAR(255) NOT NULL,
                    last_name           VARCHAR(255),
                    referral            VARCHAR(255),
                    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accepted_at         TIMESTAMP,
                    created_username    VARCHAR(40)
                )""")
            con.commit()
