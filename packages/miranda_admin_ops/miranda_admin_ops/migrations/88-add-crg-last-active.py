# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.table_exists(utilities.admin_sc, "compute_resource_group"):
    if not utilities.has_column(
        utilities.admin_sc, "compute_resource_group", "last_active"
    ):
        print("Adding last_active to compute_resource_group table")
        utilities.add_column(
            utilities.admin_sc,
            "compute_resource_group",
            "last_active",
            "DATETIME DEFAULT NULL",
        )
