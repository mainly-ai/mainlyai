# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
sc = utilities.admin_sc

if not utilities.has_column(sc, 'compute_resource_group', 'deployment_base_url'):
	utilities.add_column(sc, 'compute_resource_group', 'deployment_base_url', 'VARCHAR(255) DEFAULT NULL')
