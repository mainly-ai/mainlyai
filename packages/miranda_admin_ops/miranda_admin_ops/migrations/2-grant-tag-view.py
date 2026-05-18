# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

from utilities import *

with admin_sc.connect() as con:
  for user in get_all_miranda_users(con):
    with con.cursor() as cur:
      sql = "GRANT SELECT ON miranda.v_tags_per_ko TO %s@`%`"
      sql_data = (user[0],)
      cur.execute(sql, sql_data)
      sql = "GRANT SELECT ON miranda.v_tags_per_wob TO %s@`%`"
      sql_data = (user[0],)
      cur.execute(sql, sql_data)
      sql = "GRANT SELECT ON miranda.vtag2metadata TO %s@`%`"
      sql_data = (user[0],)
      cur.execute(sql, sql_data)

