# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.table_exists(utilities.admin_sc, "credit_transactions"):
  with utilities.admin_sc.connect() as con:
    with con.cursor() as cur:
      cur.execute("""
        CREATE TABLE IF NOT EXISTS `credit_transactions` (
          id 										INTEGER NOT NULL AUTO_INCREMENT,
          created_at 						TIMESTAMP NOT NULL DEFAULT NOW(),
          initiator_user_id 		INTEGER,
          from_organization_id 	INTEGER,
          to_organization_id		INTEGER,
          amount 								DECIMAL(36,18) NOT NULL,
          statement 						VARCHAR(255) NOT NULL,
          PRIMARY KEY (id),
          FOREIGN KEY (initiator_user_id) REFERENCES users (id),
          FOREIGN KEY (from_organization_id) REFERENCES organization (id),
          FOREIGN KEY (to_organization_id) REFERENCES organization (id)
        )""")

if not utilities.has_column(utilities.admin_sc, "organization", "credits"):
  utilities.add_column(utilities.admin_sc, "organization", "credits", "DECIMAL(36,18) NOT NULL DEFAULT 0.0")
else:
  utilities.modify_column(utilities.admin_sc, "organization", "credits", "DECIMAL(36,18) NOT NULL DEFAULT 0.0")