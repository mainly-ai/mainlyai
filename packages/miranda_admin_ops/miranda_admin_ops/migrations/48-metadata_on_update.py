# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

utilities.modify_column(utilities.admin_sc, 'metadata', 'last_updated', 'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP')
utilities.modify_column(utilities.admin_sc, 'metadata', 'last_used', 'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP')