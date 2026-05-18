# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
if not utilities.has_column(utilities.admin_sc,"docker_images","is_base_image"):
  utilities.add_column(utilities.admin_sc,"docker_images","is_base_image","boolean DEFAULT TRUE")
if not utilities.has_column(utilities.admin_sc,"docker_images","base_image_id"):
  utilities.add_column(utilities.admin_sc,"docker_images","base_image_id","int DEFAULT NULL")
#utilities.setup_sps(utilities.admin_sc)
#utilities.recreate_views(utilities.admin_sc)