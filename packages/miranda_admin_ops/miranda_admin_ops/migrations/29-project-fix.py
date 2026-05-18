# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.table_exists(utilities.admin_sc,"project"):
  with utilities.admin_sc.connect() as con:
    with con.cursor() as cur:
      sql = """
CREATE TABLE `project` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `metadata_id` int NOT NULL,
  `organization_id` int NOT NULL,
  `stripe_sub_id` varchar(255) NOT NULL,
  `last_paid` DATETIME DEFAULT NULL,
  PRIMARY KEY (`ID`,`metadata_id`),
  KEY `metadata_id` (`metadata_id`),
  CONSTRAINT `project_ibfk_1` FOREIGN KEY (`metadata_id`) REFERENCES `metadata` (`ID`) ON DELETE CASCADE
)
"""
      cur.execute(sql)
      con.commit()
if not utilities.has_column(utilities.admin_sc,"project","organization_id"):
  utilities.add_column(utilities.admin_sc,"project","organization_id","INT NOT NULL")
if not utilities.has_column(utilities.admin_sc,"organization","stripe_sub_id"):
  utilities.add_column(utilities.admin_sc,"organization","stripe_sub_id","VARCHAR(32)")
if not utilities.has_column(utilities.admin_sc,"organization","is_free"):
  utilities.add_column(utilities.admin_sc,"organization","is_free","BOOLEAN NOT NULL DEFAULT FALSE")
if not utilities.has_column(utilities.admin_sc,"project","last_paid"):
  utilities.add_column(utilities.admin_sc,"project","last_paid","DATETIME DEFAULT NULL")

utilities.change_column(utilities.admin_sc,"edges","src_type","enum('CODE','KNOWLEDGE_OBJECT','DOCKER_JOB','DEPLOYMENT','COMPUTE_POLICY','PROJECT')")
utilities.change_column(utilities.admin_sc,"edges","dest_type","enum('CODE','KNOWLEDGE_OBJECT','DOCKER_JOB','DEPLOYMENT','COMPUTE_POLICY','PROJECT')")

utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)
    