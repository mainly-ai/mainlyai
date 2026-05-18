# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

from utilities import *

upgrade = False

print ("Using db config: ", admin_sc.db_config)
if not table_exists(admin_sc, "compute_policy"):
  with admin_sc.connect() as con:
    with con.cursor() as cur:
      cur.execute("""CREATE TABLE `compute_policy` (
                    `ID` int NOT NULL AUTO_INCREMENT,
                    `metadata_id` int NOT NULL,
                    `order` int DEFAULT '0',
                    `cr_group_id` int DEFAULT NULL,
                    `docker_image_id` int DEFAULT NULL,
                    PRIMARY KEY (`ID`,`metadata_id`),
                    KEY `metadata_id` (`metadata_id`),
                    FOREIGN KEY (`metadata_id`) REFERENCES `metadata` (`ID`) ON DELETE CASCADE
                  )""")
      con.commit()
      # add COMPUTE_POLICY to edges table enum
      cur.execute("ALTER TABLE `edges` MODIFY COLUMN `src_type` enum('ETL_PROCESS', 'MODEL', 'STORAGE', 'DATASTREAM', 'CODE', 'SIMULATOR', 'KNOWLEDGE_OBJECT', 'ACTUATOR', 'UIVIEW', 'DASHBOARD', 'DOCKER_JOB', 'DEPLOYMENT', 'COMPUTE_POLICY') DEFAULT NULL")
      cur.execute("ALTER TABLE `edges` MODIFY COLUMN `dest_type` enum('ETL_PROCESS', 'MODEL', 'STORAGE', 'DATASTREAM', 'CODE', 'SIMULATOR', 'KNOWLEDGE_OBJECT', 'ACTUATOR', 'UIVIEW', 'DASHBOARD', 'DOCKER_JOB', 'DEPLOYMENT', 'COMPUTE_POLICY') DEFAULT NULL")
      cur.close()
if not table_exists(admin_sc, "compute_resource_groups"):
  with admin_sc.connect() as con:
    with con.cursor() as cur:
      cur.execute("""CREATE TABLE `compute_resource_groups` (
                    `id` int NOT NULL AUTO_INCREMENT,
                    `name` varchar(40) NOT NULL,
                    `description` varchar(255) DEFAULT '',
                    `creator_user_id` int DEFAULT NULL,
                    `creation_time` datetime DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`id`),
                    KEY `user_id` (`creator_user_id`),
                    CONSTRAINT `compute_resource_group_ibfk_1` FOREIGN KEY (`creator_user_id`) REFERENCES `users` (`ID`) ON DELETE CASCADE
                  )""")
      con.commit()
      cur.close()
if not table_exists(admin_sc, "cr_group_map"):
  with admin_sc.connect() as con:
    with con.cursor() as cur:
      cur.execute("""CREATE TABLE `cr_group_map` (
                    `GROUP_ID` int NOT NULL,
                    `CR_ID` int NOT NULL,
                    PRIMARY KEY (`GROUP_ID`,`CR_ID`)
                  )""")
      con.commit()
      cur.close()
if not table_exists(admin_sc, "docker_images"):
  with admin_sc.connect() as con:
    with con.cursor() as cur:
      cur.execute("""CREATE TABLE `docker_images` (
                    `ID` int AUTO_INCREMENT,
                    `URI` varchar(255) NOT NULL,
                    `properties` json,
                    `image_state` enum('NEW','BUILDING','ERROR','READY') DEFAULT 'NEW',
                    `image_size` int DEFAULT 0,
                    `creator_user_id` int DEFAULT NULL,
                    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`ID`)
                  )""")
      con.commit()
      cur.close()
if not table_exists(admin_sc, "user_to_resource_map"):
  with admin_sc.connect() as con:
    with con.cursor() as cur:
      cur.execute("""CREATE TABLE `user_to_resource_map` (
                    `USER_ID` int NOT NULL,
                    `RES_ID` int NOT NULL,
                    `RES_TYPE` enum('COMPUTE_RESOURCE','COMPUTE_RESOURCE_GROUP','DOCKER_IMAGE') NOT NULL,
                    `ACCESS_LEVEL` enum('READ','WRITE','ADMIN') DEFAULT 'READ',
                    PRIMARY KEY (`USER_ID`,`RES_ID`,`RES_TYPE`)
                    )""")
      con.commit()
      cur.close()

setup_sps(admin_sc)
recreate_views(admin_sc)
with admin_sc.connect() as con:
  for user in [user for user in get_all_miranda_users(con)]:
    with con.cursor() as cur:
      for tbl in ["compute_policy"]:
        sql = "GRANT SELECT ON miranda.v_{} TO %s@`%`".format(tbl)
        sql_data = (user[0],)
        cur.execute(sql, sql_data)
        print ("Granted SELECT on v_{} to {}".format(tbl, user[0]))
        
