# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.table_exists(utilities.admin_sc, "compute_policy"):
    if not utilities.has_column(utilities.admin_sc, "compute_policy", "idle_timeout"):
        print("Adding idle_timeout to compute_policy table")
        utilities.add_column(
            utilities.admin_sc,
            "compute_policy",
            "idle_timeout",
            "INT DEFAULT 3600",
        )
