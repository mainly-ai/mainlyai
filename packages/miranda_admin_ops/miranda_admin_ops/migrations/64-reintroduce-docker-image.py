# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.table_exists(utilities.admin_sc, "docker_image"):
	with utilities.admin_sc.connect() as con:
		with con.cursor() as cur:
			cur.execute("DROP TABLE IF EXISTS docker_image")
			con.commit()

with utilities.admin_sc.connect() as con:
	with con.cursor() as cur:
		cur.execute("""
			CREATE TABLE `docker_image` (
				`id` int NOT NULL AUTO_INCREMENT,
				`uri` varchar(255) DEFAULT NULL,
				`properties` text,
				`image_state` enum('NEW','BUILDING','PUSHING','MODIFIED','ERROR','READY') DEFAULT NULL,
				`image_size` int DEFAULT NULL,
				`base_image_uri` varchar(255) DEFAULT NULL,
				`is_base_image` tinyint(1) DEFAULT NULL,
				`base_image_id` int DEFAULT NULL,
				`hosting_crg_id` int DEFAULT NULL,
				`metadata_id` int DEFAULT NULL,
				PRIMARY KEY (`id`),
				KEY `metadata_id` (`metadata_id`),
				CONSTRAINT `docker_image_ibfk_1` FOREIGN KEY (`metadata_id`) REFERENCES `metadata` (`ID`)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""")
		con.commit()

if utilities.table_exists(utilities.admin_sc, "docker_images"):
	with utilities.admin_sc.connect() as con:
		with con.cursor() as cur:
			cur.execute("DROP TABLE IF EXISTS docker_images")
			con.commit()


utilities.modify_column(utilities.admin_sc,"edges","src_type","ENUM('CODE', 'KNOWLEDGE_OBJECT', 'DOCKER_JOB','DEPLOYMENT', 'COMPUTE_POLICY', 'PROJECT', 'STORAGE_POLICY', 'COMPUTE_RESOURCE_GROUP', 'DOCKER_IMAGE')")
utilities.modify_column(utilities.admin_sc,"edges","dest_type","ENUM('CODE', 'KNOWLEDGE_OBJECT', 'DOCKER_JOB','DEPLOYMENT', 'COMPUTE_POLICY', 'PROJECT', 'STORAGE_POLICY', 'COMPUTE_RESOURCE_GROUP', 'DOCKER_IMAGE')")
