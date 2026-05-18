# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

with utilities.admin_sc.connect() as con:
  with con.cursor() as cur:
    cur.execute("""
                  alter table miranda_web.realtime_room_chat add column metadata json default null;
                """)
    con.commit()

utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)
