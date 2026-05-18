# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.has_column(utilities.admin_sc,"code","git_branch") == False:    
  with utilities.admin_sc.connect() as con:
    with con.cursor() as cur:
      cur.execute("ALTER TABLE code ADD COLUMN git_branch VARCHAR(40) AFTER `git`")
      con.commit()

  utilities.setup_sps(utilities.admin_sc)
  utilities.recreate_views(utilities.admin_sc)
else:
  print("Column git_branch already exists in table code.")
