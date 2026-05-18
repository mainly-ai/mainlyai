# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

with utilities.admin_sc.connect() as con:
  with con.cursor() as cur:
    cur.execute("""
                  alter table miranda.user_groups add icon varchar(255) not null default 'https://mainly-web-assets.s3.eu-north-1.amazonaws.com/avatars/group_default.png';"
                """)
    con.commit()

utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)
