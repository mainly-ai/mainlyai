# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

from utilities import *

if has_column(admin_sc,"model","produce_artefacts"):
  rename_column(admin_sc,"model","produce_artefacts","produce_artifacts")
  drop_view_if_exists(admin_sc,"v_model")
if has_column(admin_sc,"actuator","produce_artefacts"):
  rename_column(admin_sc,"actuator","produce_artefacts","produce_artifacts")
  drop_view_if_exists(admin_sc,"v_actuator")

recreate_views(admin_sc)
