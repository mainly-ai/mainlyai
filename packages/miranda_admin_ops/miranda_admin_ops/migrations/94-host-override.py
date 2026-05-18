# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

from utilities import *

if not has_column(admin_sc, "compute_policy", "host_override"):
    print("Adding host_override to compute_policy table")
    add_column(admin_sc, "compute_policy", "host_override", "VARCHAR(255) DEFAULT NULL")
