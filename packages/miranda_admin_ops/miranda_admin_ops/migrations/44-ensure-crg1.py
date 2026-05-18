# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
import miranda_admin_ops

crg = miranda_admin_ops.get_compute_resource_group_by_id(utilities.admin_sc, 1)
webadmin_user = miranda_admin_ops.get_user(utilities.admin_sc, "webadmin")

if crg is None:
    print("No CRG with id 1 found. Creating")
    miranda_admin_ops.create_compute_resource_groups(
        utilities.admin_sc, "cpu.mainly.cloud", "", webadmin_user["id"]
    )
else:
    print("Hooray, CRG already exists")
