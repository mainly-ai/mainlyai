# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

#if utilities.table_exists(utilities.admin_sc, "billing"):
  #exit(0)

with utilities.admin_sc.connect() as con:
  with con.cursor() as cur:
    cur.execute("""
              CREATE TABLE IF NOT EXISTS billing (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                cents DECIMAL(10,3) NOT NULL,
                subject ENUM('PROCESSOR_DEBUG', 'PROCESSOR_DEPLOYMENT', 'VAULT', 'PROJECT') NOT NULL,
                subject_id INTEGER NOT NULL,
                billing_period INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                billed_at TIMESTAMP,
                paid_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
              )""")
    cur.execute("ALTER TABLE miranda.billing ADD INDEX (user_id, billing_period)")
    cur.execute("""
      CREATE TABLE IF NOT EXISTS `organization` (
        id 							INTEGER NOT NULL AUTO_INCREMENT,
        name 						VARCHAR(64) NOT NULL,
        created_at 			TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at 			TIMESTAMP NOT NULL DEFAULT NOW(),
        creator_user_id INTEGER NOT NULL,
        stripe_cus_id 	VARCHAR(32),
        subscribed      BOOLEAN NOT NULL DEFAULT FALSE,
        trial           BOOLEAN NOT NULL DEFAULT FALSE,
        PRIMARY KEY (id),
        FOREIGN KEY (creator_user_id) REFERENCES users (id)
      )""")
    
    if not utilities.has_column(utilities.admin_sc, "users", "organization_id"):
      cur.execute("ALTER TABLE miranda.users ADD COLUMN `organization_id` INTEGER NOT NULL DEFAULT -1")
    if not utilities.has_column(utilities.admin_sc, "compute_resource_groups", "cost_per_cpu_hour"):
      cur.execute("ALTER TABLE miranda.compute_resource_groups ADD COLUMN `cost_per_cpu_hour` DECIMAL(10,3) DEFAULT 0.000")
      cur.execute("ALTER TABLE miranda.compute_resource_groups ADD COLUMN `cost_per_gb_hour` DECIMAL(10,3) DEFAULT 0.000")
      cur.execute("ALTER TABLE miranda.compute_resource_groups ADD COLUMN `cost_per_net_rx_gb` DECIMAL(10,3) DEFAULT 0.000")
      cur.execute("ALTER TABLE miranda.compute_resource_groups ADD COLUMN `cost_per_net_tx_gb` DECIMAL(10,3) DEFAULT 0.000")

    con.commit()

utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)