# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.table_exists(utilities.admin_sc, "compute_resource_groups"):
	with utilities.admin_sc.connect() as con:
		with con.cursor() as cur:
			cur.execute("DROP TABLE IF EXISTS compute_resource_groups")
			con.commit()

if not utilities.table_exists(utilities.admin_sc, "compute_resource_group"):
	with utilities.admin_sc.connect() as con:
		with con.cursor() as cur:
			cur.execute("""
				CREATE TABLE IF NOT EXISTS `compute_resource_group` (
					`ID` int NOT NULL AUTO_INCREMENT,
					`metadata_id` int NOT NULL,
					`cpu_capacity` int DEFAULT 0,
					`gpu_capacity` int DEFAULT 0,
					`ram_capacity` int DEFAULT 0,
					`cost_per_cpu_hour` DECIMAL(10,3) DEFAULT 0.000,
					`cost_per_gpu_hour` DECIMAL(10,3) DEFAULT 0.000,
					`cost_per_gb_hour` DECIMAL(10,3) DEFAULT 0.000,
					`cost_per_net_rx_gb` DECIMAL(10,3) DEFAULT 0.000,
					`cost_per_net_tx_gb` DECIMAL(10,3) DEFAULT 0.000,
					PRIMARY KEY (`ID`,`metadata_id`),
					KEY `metadata_id` (`metadata_id`),
					FOREIGN KEY (`metadata_id`) REFERENCES `metadata` (`ID`) ON DELETE CASCADE
				)""")
			con.commit()

utilities.modify_column(utilities.admin_sc,"edges","src_type","ENUM('CODE', 'KNOWLEDGE_OBJECT', 'DOCKER_JOB','DEPLOYMENT', 'COMPUTE_POLICY', 'PROJECT', 'STORAGE_POLICY', 'COMPUTE_RESOURCE_GROUP')")
utilities.modify_column(utilities.admin_sc,"edges","dest_type","ENUM('CODE', 'KNOWLEDGE_OBJECT', 'DOCKER_JOB','DEPLOYMENT', 'COMPUTE_POLICY', 'PROJECT', 'STORAGE_POLICY', 'COMPUTE_RESOURCE_GROUP')")
