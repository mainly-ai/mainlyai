# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.has_column(utilities.admin_sc, 'code', 'update_policy'):
	utilities.add_column(utilities.admin_sc, 'code', 'update_policy', "ENUM ('NEVER', 'NOTIFY', 'SUBSCRIBE') DEFAULT 'NOTIFY'")
if not utilities.has_column(utilities.admin_sc, 'code', 'diffs'):
	utilities.add_column(utilities.admin_sc, 'code', 'diffs', "JSON")

