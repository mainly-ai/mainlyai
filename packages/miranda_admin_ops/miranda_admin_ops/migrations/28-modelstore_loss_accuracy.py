# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.has_column(utilities.admin_sc,"model","loss"):
  utilities.add_column(utilities.admin_sc,"model","loss","FLOAT")
if not utilities.has_column(utilities.admin_sc,"model","accuracy"):
  utilities.add_column(utilities.admin_sc,"model","accuracy","FLOAT")
if not utilities.has_column(utilities.admin_sc,"model","precision"):
  utilities.add_column(utilities.admin_sc,"model","precision","FLOAT")
if not utilities.has_column(utilities.admin_sc,"model","recall"):
  utilities.add_column(utilities.admin_sc,"model","recall","FLOAT")

utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)