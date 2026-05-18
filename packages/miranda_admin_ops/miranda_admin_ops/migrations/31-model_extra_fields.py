# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.has_column(utilities.admin_sc,"model","knowledge_object_id"):
  utilities.add_column(utilities.admin_sc,"model","knowledge_object_id","INT DEFAULT -1")
if not utilities.has_column(utilities.admin_sc,"model","workflow_state"):
  utilities.add_column(utilities.admin_sc,"model","workflow_state",'ENUM("UNINITIALIZED","INITIALIZED","TRAINING","TRAINED","TESTING","TESTED","DEPLOYED") DEFAULT "UNINITIALIZED"')
utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)