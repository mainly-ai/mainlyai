-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS `model` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `metadata_id` int NOT NULL,
  `model_type` enum('SKLEARN','HUGGINGFACE','TENSORFLOW','KERAS','PYTORCH','JAX','OTHER') DEFAULT NULL,
  `miranda_version` varchar(40) DEFAULT 'v1.0',
  `hardware` json DEFAULT NULL,
  `load_url` varchar(255) DEFAULT NULL,
  `save_url` varchar(255) DEFAULT NULL,
  `files` json DEFAULT NULL,
  `authors` varchar(255) DEFAULT NULL,
  `license` varchar(80) DEFAULT NULL,
  `feature_labels` json DEFAULT NULL,
  `prediction_labels` json DEFAULT NULL,
  `feature_units` json DEFAULT NULL,
  `prediction_units` json DEFAULT NULL,
  `loss` FLOAT DEFAULT 0.0,
  `accuracy` FLOAT DEFAULT 0.0,
  `precision` FLOAT DEFAULT 0.0,
  `recall` FLOAT DEFAULT 0.0,
  `knowledge_object_id` int DEFAULT -1,
  `workflow_state` enum("UNINITIALIZED","INITIALIZED","TRAINING","TRAINED","TESTING","TESTED","DEPLOYED") DEFAULT "UNINITIALIZED",
  PRIMARY KEY (`ID`,`metadata_id`),
  KEY `metadata_id` (`metadata_id`),
  CONSTRAINT `model_ibfk_1` FOREIGN KEY (`metadata_id`) REFERENCES `metadata` (`ID`) ON DELETE CASCADE
)