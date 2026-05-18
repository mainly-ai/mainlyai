# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

from utilities import *

with admin_sc.connect() as conn:
  with conn.cursor() as cur:
    sql = "CREATE TABLE IF NOT EXISTS proxy_account_claims (name VARCHAR(32) NOT NULL, belonging_to VARCHAR(32) NOT NULL, at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, by_application VARCHAR(255))"
    print(sql)
    cur.execute(sql)
    conn.commit()

    sql = "DROP VIEW IF EXISTS v_tokens;"
    print(sql)
    cur.execute(sql)
    conn.commit()

    sql = """CREATE DEFINER = miranda_internal@localhost VIEW v_tokens AS (
  SELECT
    name,
    GROUP_CONCAT(by_application SEPARATOR ',') AS applications,
    DATE_ADD(MAX(at), INTERVAL 7 DAY) AS expires
  FROM proxy_account_claims
  WHERE belonging_to = CURRENT_MIRANDA_USER()
  GROUP BY name, belonging_to
);"""
    print(sql)
    cur.execute(sql)
    cur.close()
  conn.close()

setup_sps(admin_sc)
recreate_views(admin_sc)

with admin_sc.connect() as con:
  print('GRANT SELECT ...')
  for user in get_all_miranda_users(con):
    with con.cursor() as cur:
      sql = "GRANT SELECT ON miranda.v_user TO %s@`%`"
      sql_data = (user[0],)
      cur.execute(sql, sql_data)
      sql = "GRANT SELECT ON miranda.v_tokens TO %s@`%`"
      sql_data = (user[0],)
      cur.execute(sql, sql_data)