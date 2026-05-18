# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

with utilities.admin_sc.connect() as con:
  with con.cursor() as cur:
    cur.execute("DELETE FROM miranda_web.designer_sizes") # remove all existing sizes so we can add the unique key
    cur.execute("ALTER TABLE miranda_web.designer_sizes ADD UNIQUE KEY (project_id, metadata_id, control_name, user)")
    con.commit()

utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)