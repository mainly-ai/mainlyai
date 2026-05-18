# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

from utilities import *

upgrade = False

print ("Using db config: ", admin_sc.db_config)
if not table_exists(admin_sc, "miranda_logs"):
  with admin_sc.connect() as con:
    with con.cursor() as cur:
      sql = """CREATE TABLE IF NOT EXISTS miranda_logs (
                ID              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                User_id         INTEGER NOT NULL,
                Created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                Tag             SMALLINT DEFAULT 0,
                Class_id        SMALLINT NOT NULL,
                Instance_id     INTEGER NOT NULL,
                Message         TEXT
              )"""
      cur.execute(sql)
      con.commit()
      print ("Created table miranda_logs")
  setup_sps(admin_sc)
  recreate_views(admin_sc)
  with admin_sc.connect() as con:
    for user in [user for user in get_all_miranda_users(con)]:
      with con.cursor() as cur:
        sql = "GRANT SELECT ON miranda.v_miranda_logs TO %s@`%`"
        sql_data = (user[0],)
        cur.execute(sql, sql_data)
        print ("Granted SELECT on v_miranda_logs to ", user[0])
