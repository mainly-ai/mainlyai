# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
sc = utilities.admin_sc

if not utilities.has_column(sc, 'compute_resource_group', 'cpu_congestion'):
	utilities.add_column(sc, 'compute_resource_group', 'cpu_congestion', 'float DEFAULT 0.0')

if not utilities.has_column(sc, 'compute_resource_group', 'gpu_congestion'):
	utilities.add_column(sc, 'compute_resource_group', 'gpu_congestion', 'float DEFAULT 0.0')

if not utilities.has_column(sc, 'compute_resource_group', 'ram_congestion'):
	utilities.add_column(sc, 'compute_resource_group', 'ram_congestion', 'float DEFAULT 0.0')
