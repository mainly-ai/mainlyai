-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS `project` (
  `ID` INT NOT NULL AUTO_INCREMENT,
  `metadata_id` INT NOT NULL,
  `organization_id` INT NOT NULL,
  `stripe_sub_id` VARCHAR(255) NOT NULL,
  `last_paid` DATETIME DEFAULT NULL,
  PRIMARY KEY (`ID`,`metadata_id`),
  KEY `metadata_id` (`metadata_id`),
  CONSTRAINT `project_ibfk_1` FOREIGN KEY (`metadata_id`) REFERENCES `metadata` (`ID`) ON DELETE CASCADE
)