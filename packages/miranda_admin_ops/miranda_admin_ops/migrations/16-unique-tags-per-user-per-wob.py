# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

with utilities.admin_sc.connect() as con:
  for user in utilities.get_all_miranda_users(con):
    with con.cursor() as cur:
      cur.execute("ALTER TABLE miranda.tag2metadata ADD UNIQUE (user_id, tag, metadata_id)")
      con.commit()

utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)
