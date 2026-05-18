# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
import miranda_admin_ops as ma

ma.create_user_role_if_not_exists()

# Make sure the new role is granted and set as default to all users.
with utilities.admin_sc.connect() as con:
    with con.cursor() as cur:
        sql = "SELECT user FROM mysql.user WHERE user LIKE 'miranda_%'"
        cur.execute(sql)
        users = cur.fetchall()
        for rs in users:
            if rs[0] == "miranda_internal":
                continue
            sql = f"GRANT mainlyai_user_role TO '{rs[0]}'"
            print(sql)
            cur.execute(sql)
            con.commit()
            cur.fetchall()
            sql = "SET DEFAULT ROLE mainlyai_user_role TO '{}'@'%'".format(rs[0])
            print(sql)
            cur.execute(sql)
            con.commit()
            try:
                sql = "REVOKE SELECT ON miranda.users FROM '{}'@'%'".format(rs[0])
                print(sql)
                cur.execute(sql)
                con.commit()
            except Exception as e:
                print(e)
            try:
                sql = "REVOKE SELECT ON miranda.users_details FROM '{}'@'%'".format(
                    rs[0]
                )
                print(sql)
                cur.execute(sql)
                con.commit()
            except Exception as e:
                print(e)
                pass

# force a recreation of the views in case it was modified by a previous migration in the same run
utilities.recreate_views(utilities.admin_sc)
utilities.setup_sps(utilities.admin_sc)
