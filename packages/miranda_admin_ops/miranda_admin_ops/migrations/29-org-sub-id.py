# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.has_column(utilities.admin_sc,"organization","stripe_sub_id"):
  utilities.add_column(utilities.admin_sc,"organization","stripe_sub_id","VARCHAR(32)")
if not utilities.has_column(utilities.admin_sc,"organization","is_free"):
  utilities.add_column(utilities.admin_sc,"organization","is_free","BOOLEAN NOT NULL DEFAULT FALSE")
if not utilities.has_column(utilities.admin_sc,"organization","trial_end"):
  utilities.add_column(utilities.admin_sc,"organization","trial_end","TIMESTAMP")
utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)