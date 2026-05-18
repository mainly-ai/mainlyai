# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.has_column(utilities.admin_sc, 'compute_policy', 'requested_gpus'):
	utilities.add_column(utilities.admin_sc, 'compute_policy', 'requested_gpus', "int DEFAULT '0'")

if not utilities.has_column(utilities.admin_sc, 'compute_policy', 'requested_cpus'):
	utilities.add_column(utilities.admin_sc, 'compute_policy', 'requested_cpus', "float(2,1) DEFAULT '1.0'")

if not utilities.has_column(utilities.admin_sc, 'compute_policy', 'requested_memory'):
	utilities.add_column(utilities.admin_sc, 'compute_policy', 'requested_memory', "float(3,1) DEFAULT '2.0'")
