# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

utilities.modify_column(utilities.admin_sc,"edges","src_type","ENUM('CODE', 'KNOWLEDGE_OBJECT', 'DOCKER_JOB','DEPLOYMENT', 'COMPUTE_POLICY', 'PROJECT', 'STORAGE_POLICY')")
utilities.modify_column(utilities.admin_sc,"edges","dest_type","ENUM('CODE', 'KNOWLEDGE_OBJECT', 'DOCKER_JOB','DEPLOYMENT', 'COMPUTE_POLICY', 'PROJECT', 'STORAGE_POLICY')")
