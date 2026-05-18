# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.has_column(utilities.admin_sc, "docker_job", "crg_id"):
  utilities.add_column(utilities.admin_sc, "docker_job", "crg_id", "INT NOT NULL")

if not utilities.has_column(utilities.admin_sc, "docker_job", "gpu_capacity"):
  utilities.add_column(utilities.admin_sc, "docker_job", "gpu_capacity", "FLOAT DEFAULT '0'")

if not utilities.has_column(utilities.admin_sc, "docker_job", "current_cpu"):
  utilities.add_column(utilities.admin_sc, "docker_job", "current_cpu", "FLOAT DEFAULT '0'")

if not utilities.has_column(utilities.admin_sc, "docker_job", "cpu_capacity"):
  utilities.add_column(utilities.admin_sc, "docker_job", "cpu_capacity", "FLOAT DEFAULT '0'")

if not utilities.has_column(utilities.admin_sc, "docker_job", "current_ram_gb"):
  utilities.add_column(utilities.admin_sc, "docker_job", "current_ram_gb", "FLOAT DEFAULT '0'")

if not utilities.has_column(utilities.admin_sc, "docker_job", "ram_gb_capacity"):
  utilities.add_column(utilities.admin_sc, "docker_job", "ram_gb_capacity", "FLOAT DEFAULT '0'")

if not utilities.has_column(utilities.admin_sc, "docker_job", "current_net_rx_gb"):
  utilities.add_column(utilities.admin_sc, "docker_job", "current_net_rx_gb", "FLOAT DEFAULT '0'")

if not utilities.has_column(utilities.admin_sc, "docker_job", "current_net_tx_gb"):
  utilities.add_column(utilities.admin_sc, "docker_job", "current_net_tx_gb", "FLOAT DEFAULT '0'")

if not utilities.has_column(utilities.admin_sc, "docker_job", "total_cost"):
  utilities.add_column(utilities.admin_sc, "docker_job", "total_cost", "FLOAT DEFAULT '0'")

utilities.modify_column(utilities.admin_sc, "docker_image", "hosting_crg_id", "INT DEFAULT -1")