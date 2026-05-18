# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.has_column(utilities.admin_sc, "waitlist", "invite_email_id", "miranda_web"):
  utilities.add_column(utilities.admin_sc, "waitlist", "invite_email_id", "VARCHAR(255) DEFAULT NULL", "miranda_web")

if not utilities.has_column(utilities.admin_sc, "waitlist", "initial_login_token", "miranda_web"):
  utilities.add_column(utilities.admin_sc, "waitlist", "initial_login_token", "VARCHAR(255) DEFAULT NULL", "miranda_web")
