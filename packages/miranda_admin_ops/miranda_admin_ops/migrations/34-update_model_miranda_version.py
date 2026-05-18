# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
if not utilities.has_column(utilities.admin_sc,"model","miranda_version"):
  utilities.modify_column(utilities.admin_sc,"model","miranda_version","VARCHAR(40) DEFAULT 'v0.0'")
utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)