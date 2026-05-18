# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
import miranda_admin_ops as admin

utilities.recreate_views(utilities.admin_sc)
utilities.setup_sps(utilities.admin_sc)

admin.ensure_userspace_view_grants(utilities.admin_sc)
