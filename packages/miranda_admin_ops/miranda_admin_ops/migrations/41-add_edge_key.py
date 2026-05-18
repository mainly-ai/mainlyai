# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
if not utilities.has_column(utilities.admin_sc,"edges","edge_key"):
  utilities.add_column(utilities.admin_sc,"edges","edge_key","VARCHAR(255) GENERATED ALWAYS AS (CONCAT(src_id, '-', dest_id)) VIRTUAL")
  utilities.add_index(utilities.admin_sc,"edges","edge_key")
