# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

from utilities import *

with admin_sc.connect() as con:
  with con.cursor() as cur:
    sql = """CREATE TABLE IF NOT EXISTS miranda_web.credentials (
  id           INT                      AUTO_INCREMENT,
  kind         ENUM('TOTP', 'WEBAUTHN') NOT NULL,
  belonging_to VARCHAR(32)              NOT NULL,
  secret       VARCHAR(255)             NOT NULL,
  name         VARCHAR(64)              NULL,
  metadata     json                     NULL,
  time_created DATETIME                 DEFAULT CURRENT_TIMESTAMP,
  last_used    DATETIME                 DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT id
    PRIMARY KEY (id)
);"""
    print(sql)
    cur.execute(sql)
    con.commit()
  
  for user in get_all_miranda_web_users(con):
    with con.cursor() as cur:
      sql = "SELECT mfa_secret FROM miranda_web.web_users WHERE username = %s"
      sql_data = (user[0],)
      cur.execute(sql, sql_data)
      mfa_secret = cur.fetchall()[0][0]
      if mfa_secret:
        print(f"Migrating MFA secret for user {user[0]}")
        sql = "INSERT INTO miranda_web.credentials (kind, belonging_to, secret, name) VALUES ('TOTP', %s, %s, 'Migrated Authenticator')"
        sql_data = (user[0], mfa_secret)
        cur.execute(sql, sql_data)
        con.commit()
  
  with con.cursor() as cur:
    sql = "ALTER TABLE miranda_web.web_users DROP COLUMN mfa_secret"
    print(sql)
    cur.execute(sql)
    con.commit()

setup_sps(admin_sc)
recreate_views(admin_sc)
