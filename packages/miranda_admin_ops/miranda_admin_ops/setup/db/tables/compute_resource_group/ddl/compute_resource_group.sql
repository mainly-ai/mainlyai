-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS `compute_resource_group` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `metadata_id` int NOT NULL,
  `cpu_capacity` int DEFAULT 0,
  `cpu_congestion` float DEFAULT 0.0,
  `gpu_capacity` int DEFAULT 0,
  `gpu_congestion` float DEFAULT 0.0,
  `ram_capacity` int DEFAULT 0,
  `ram_congestion` float DEFAULT 0.0,
  `cost_per_cpu_hour` DECIMAL(10,3) DEFAULT 0.000,
  `cost_per_gpu_hour` DECIMAL(10,3) DEFAULT 0.000,
  `cost_per_gb_hour` DECIMAL(10,3) DEFAULT 0.000,
  `cost_per_net_rx_gb` DECIMAL(10,3) DEFAULT 0.000,
  `cost_per_net_tx_gb` DECIMAL(10,3) DEFAULT 0.000,
  `deployment_base_url` VARCHAR(255) DEFAULT NULL,
  `operator_user_id` int DEFAULT NULL,
  `last_active` DATETIME DEFAULT NULL,
  PRIMARY KEY (`ID`,`metadata_id`),
  KEY `metadata_id` (`metadata_id`),
  FOREIGN KEY (`metadata_id`) REFERENCES `metadata` (`ID`) ON DELETE CASCADE
) 