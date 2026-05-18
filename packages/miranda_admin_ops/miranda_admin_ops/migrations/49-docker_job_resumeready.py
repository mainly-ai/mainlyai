# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
utilities.change_column(utilities.admin_sc,"docker_job","workflow_state","enum('UNINITIALIZED','STARTING','READY','RUNNING','ERROR','EXITED','RESUMEREADY','KILLING') DEFAULT 'UNINITIALIZED'")
