# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
utilities.change_column(utilities.admin_sc,"object_store","file_path","VARCHAR(255) NOT NULL")
if utilities.has_column(utilities.admin_sc,"object_store","content"):
	utilities.drop_column(utilities.admin_sc,"object_store","content")
if utilities.has_column(utilities.admin_sc,"object_store","storage_id"):
	utilities.drop_column(utilities.admin_sc,"object_store","storage_id")
if not utilities.has_column(utilities.admin_sc,"object_store","file_size"):
	utilities.add_column(utilities.admin_sc,"object_store","file_size","BIGINT DEFAULT 0 NOT NULL")
if not utilities.has_column(utilities.admin_sc,"object_store","vault_id"):
	utilities.add_column(utilities.admin_sc,"object_store","vault_id","INTEGER NOT NULL")