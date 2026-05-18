# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

with utilities.admin_sc.connect() as con:
  for user in utilities.get_all_miranda_users(con):
    with con.cursor() as cur:
      sql_data = (user[0],)
      sql = "GRANT SELECT ON miranda.v_gid_from_read_acls TO %s@`%`"
      cur.execute(sql, sql_data)
      con.commit()
      
      sql = "GRANT SELECT ON miranda.v_gid_from_write_acls TO %s@`%`"
      cur.execute(sql, sql_data)
      con.commit()

      sql = "GRANT SELECT ON miranda.v_realtime_message_queue TO %s@`%`"
      cur.execute(sql, sql_data)
      con.commit()

utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)
