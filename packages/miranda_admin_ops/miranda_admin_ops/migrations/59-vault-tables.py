# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.table_exists(utilities.admin_sc, "vault") == False:
  with utilities.admin_sc.connect() as con:
    with con.cursor() as cur:
      cur.execute("""
  CREATE TABLE IF NOT EXISTS vault (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    name VARCHAR(255) NOT NULL,
    owner_org_id INT NOT NULL,
    max_storage FLOAT NOT NULL,
    storage_used FLOAT NOT NULL,
    access_key_id VARCHAR(64) NOT NULL,
    secret_access_key VARCHAR(64) NOT NULL,
    FOREIGN KEY (owner_org_id) REFERENCES organization(id)
  )""")

if utilities.table_exists(utilities.admin_sc, "vault_object") == False:
  with utilities.admin_sc.connect() as con:
    with con.cursor() as cur:
      cur.execute("""
  CREATE TABLE IF NOT EXISTS vault_object (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    vault_id BIGINT UNSIGNED NOT NULL,
    filename VARCHAR(512) NOT NULL,
    size BIGINT UNSIGNED DEFAULT 0 NOT NULL,
    content_type VARCHAR(256) NOT NULL,
    tag VARCHAR(256),
    PRIMARY KEY (id),
    UNIQUE(`vault_id`,`filename`)
  )""")