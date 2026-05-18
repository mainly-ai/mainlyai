# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.table_exists(utilities.admin_sc, 'docker_job'):
    if not utilities.has_column(utilities.admin_sc, 'docker_job', 'is_deployed'):
        print ("Adding is_deployed column to docker_job table.")
        utilities.add_column(utilities.admin_sc, 'docker_job', 'is_deployed', 'tinyint(1) NOT NULL DEFAULT 0')