# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.table_exists(utilities.admin_sc, "compute_resource_group"):
    if utilities.has_column(
        utilities.admin_sc, "compute_resource_group", "operator_user_id"
    ):
        utilities.change_column(
            utilities.admin_sc,
            "compute_resource_group",
            "operator_user_id",
            "int DEFAULT -1",
        )
