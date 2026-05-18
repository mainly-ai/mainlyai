-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS `compute_policy` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `metadata_id` int NOT NULL,
  `order` int DEFAULT '0',
  `cr_group_id` int DEFAULT NULL,
  `docker_image_id` int DEFAULT NULL,
  `docker_image_uri_override` varchar(255) DEFAULT NULL,
  `host_override` varchar(255) DEFAULT NULL,
  `bind_http` TINYINT(1) DEFAULT '1',
  `requested_gpus` int DEFAULT '0',
  `requested_cpus` float(2,1) DEFAULT '1.0',
  `requested_memory` float(3,1) DEFAULT '2.0',
  `idle_timeout` int DEFAULT 3600,
  PRIMARY KEY (`ID`,`metadata_id`),
  KEY `metadata_id` (`metadata_id`),
  FOREIGN KEY (`metadata_id`) REFERENCES `metadata` (`ID`) ON DELETE CASCADE
)
