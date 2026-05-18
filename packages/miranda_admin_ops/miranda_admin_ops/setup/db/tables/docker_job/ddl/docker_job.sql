-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS `docker_job` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `metadata_id` int NOT NULL,
  `host` varchar(255) DEFAULT NULL,
  `port` int DEFAULT '0',
  `ssh_user` varchar(40) DEFAULT NULL,
  `docker_env_vars` varchar(512) DEFAULT '',
  `docker_network` varchar(255) DEFAULT '--network=host',
  `user_id` int DEFAULT '-1',
  `crg_id` int NOT NULL,
  `container_id` varchar(255) DEFAULT NULL,
  `message_id` int DEFAULT '-1',
  `tag` int DEFAULT '-1',
  `workflow_state` enum('UNINITIALIZED','STARTING','READY','RUNNING','ERROR','EXITED','RESUMEREADY','KILLING','RESTARTING') DEFAULT NULL,
  `notes` longtext,
  `logs` longtext,
  `gpu_capacity` float DEFAULT '0',
  `cpu_seconds` float(12, 3) DEFAULT '0',
  `current_cpu` float DEFAULT '0',
  `cpu_capacity` float DEFAULT '0',
  `ram_gb_seconds` float(12, 5) DEFAULT '0',
  `current_ram_gb` float DEFAULT '0',
  `ram_gb_capacity` float DEFAULT '0',
  `net_rx_gb` float(12, 5) DEFAULT '0',
  `current_net_rx_gb` float DEFAULT '0',
  `net_tx_gb` float(12, 5) DEFAULT '0',
  `current_net_tx_gb` float DEFAULT '0',
  `total_cost` float DEFAULT '0',
  `is_deployed` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`ID`,`metadata_id`),
  KEY `metadata_id` (`metadata_id`),
  FOREIGN KEY (crg_id) REFERENCES compute_resource_group (id),
  FOREIGN KEY (`metadata_id`) REFERENCES `metadata` (`ID`) ON DELETE CASCADE
)
