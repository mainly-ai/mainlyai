# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.table_exists(utilities.admin_sc, "compute_policy"):
    if not utilities.has_column(
        utilities.admin_sc, "compute_policy", "docker_image_uri_override"
    ):
        print("Adding docker_image_uri_override to compute_policy table")
        utilities.add_column(
            utilities.admin_sc,
            "compute_policy",
            "docker_image_uri_override",
            "VARCHAR(255) DEFAULT NULL",
        )
