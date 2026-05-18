# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

from utilities import *

with admin_sc.connect() as con:
  with con.cursor() as cur:
    sql = "ALTER TABLE miranda_web.web_users DROP COLUMN email"
    print(sql)
    cur.execute(sql)
    con.commit()

setup_sps(admin_sc)
recreate_views(admin_sc)
