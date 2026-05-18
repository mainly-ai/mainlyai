# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
has_column = utilities.has_column(utilities.admin_sc, 'code', 'API')
with utilities.admin_sc.connect() as con:
  if has_column:
    with con.cursor() as cur:
      sql = "UPDATE code SET API='{}'"
      cur.execute(sql)
      con.commit()
    utilities.modify_column(utilities.admin_sc, 'code', 'API', 'JSON')
  if utilities.has_column(utilities.admin_sc, 'metadata', 'name'):
    utilities.modify_column(utilities.admin_sc, 'metadata', 'name', 'VARCHAR(255)')
  if utilities.has_column(utilities.admin_sc, 'edges', 'properties'):
    utilities.remove_column(utilities.admin_sc, 'edges', 'properties')
  if not utilities.has_column(utilities.admin_sc, 'edges', 'attributes'):
      utilities.add_column(utilities.admin_sc, 'edges', 'attributes', 'JSON')
utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)