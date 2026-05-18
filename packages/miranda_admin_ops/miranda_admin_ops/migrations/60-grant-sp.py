# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

with utilities.admin_sc.connect() as con:
  for user in utilities.get_all_miranda_users(con):
    with con.cursor() as cur:
      sql_data = (user[0],)
      sql = "GRANT SELECT ON miranda.v_storage_policy TO %s@`%`"
      cur.execute(sql, sql_data)
      con.commit()
