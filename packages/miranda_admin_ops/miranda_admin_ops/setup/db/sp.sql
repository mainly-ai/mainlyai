-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

DROP FUNCTION IF EXISTS CURRENT_MIRANDA_USER;
---
CREATE FUNCTION CURRENT_MIRANDA_USER() RETURNS CHAR(128)
DETERMINISTIC
BEGIN
  DECLARE miranda_user CHAR(128);
  SELECT role_name INTO miranda_user FROM information_schema.APPLICABLE_ROLES where IS_DEFAULT = 'YES' AND role_name LIKE 'miranda_%' limit 1;
  IF miranda_user IS NULL THEN
    SET miranda_user = USER();
  END IF;
  RETURN TRIM('`' from REGEXP_REPLACE(miranda_user,'@.*',''));
END;
---
DROP FUNCTION IF EXISTS CURRENT_MIRANDA_USER_UNPREFIXED;
---
CREATE FUNCTION CURRENT_MIRANDA_USER_UNPREFIXED() RETURNS CHAR(128)
DETERMINISTIC
BEGIN
  DECLARE miranda_user CHAR(128);
  SELECT role_name INTO miranda_user FROM information_schema.APPLICABLE_ROLES where IS_DEFAULT = 'YES' AND role_name LIKE 'miranda_%' limit 1;
  IF miranda_user IS NULL THEN
    SET miranda_user = USER();
  END IF;
  SET miranda_user = TRIM('`' from REGEXP_REPLACE(miranda_user,'@.*',''));
  RETURN SUBSTRING(miranda_user, 9); -- remove 'miranda_' prefix
END;
---
CREATE USER IF NOT EXISTS miranda_internal@localhost IDENTIFIED BY RANDOM PASSWORD
---
DROP VIEW IF EXISTS v_edges
---
CREATE DEFINER=`miranda_internal`@`localhost` VIEW v_edges AS (
          WITH userid (uid) AS (SELECT id FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED()),
              owned (mid) AS (SELECT m.id FROM metadata m
                                    INNER JOIN users u ON m.created_by_id=u.id
                                    INNER JOIN userid ON userid.uid = u.id
                                  ),
              acl_groups (mid) AS (SELECT m.id FROM metadata m
                                    INNER JOIN read_acl a ON a.wob_mid=m.id
                                    INNER JOIN group_maps g ON g.gid = a.gid
                                    INNER JOIN users u ON u.id = g.uid
                                    INNER JOIN userid ON userid.uid = u.id)
              SELECT DISTINCT e.src_type,e.src_id,e.dest_type,e.dest_id,e.etl_id, e.attributes, e.edge_key
                FROM (SELECT owned.mid AS mid FROM owned
                      UNION
                      SELECT acl_groups.mid AS mid FROM acl_groups
                      ) AS mt
                INNER JOIN edges e ON mt.mid = e.src_id
                INNER JOIN metadata m ON m.id = mt.mid WHERE m.Deleted=0)
---
DROP VIEW IF EXISTS v_metadata
---
CREATE DEFINER=`miranda_internal`@`localhost` VIEW v_metadata AS (
          WITH userid (uid) AS (SELECT id FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED()),
              owned (mid) AS (SELECT m.id FROM metadata m
                                    INNER JOIN users u ON m.created_by_id=u.id
                                    INNER JOIN userid ON userid.uid = u.id
                                  ),
              acl_groups (mid) AS (SELECT m.id FROM metadata m
                                    INNER JOIN read_acl a ON a.wob_mid=m.id
                                    INNER JOIN group_maps g ON g.gid = a.gid
                                    INNER JOIN users u ON u.id = g.uid
                                    INNER JOIN userid ON userid.uid = u.id)
          SELECT m.ID,m.Name,m.Description,m.Created_by_id,m.Last_used,m.Last_updated,m.Time_created,m.Deleted,CURRENT_ROLE(),m.cloned_from_id
            FROM (SELECT owned.mid AS mid FROM owned
                  UNION
                  SELECT acl_groups.mid AS mid FROM acl_groups
                  ) AS mt
            INNER JOIN metadata m ON m.id = mt.mid WHERE m.Deleted=0)
---
DROP PROCEDURE IF EXISTS `sp_select_graph`;
---
DROP PROCEDURE IF EXISTS `sp_select_graph_by_mid`;
---
CREATE PROCEDURE `sp_select_graph`(IN max_depth INT)
SQL SECURITY INVOKER
BEGIN
  WITH RECURSIVE descendants AS
  (
    SELECT e.src_id,e.src_type,e.dest_id as dest_id,e.dest_type, e.etl_id, 0 as depth FROM v_edges e
    UNION DISTINCT
    SELECT e.src_id, e.src_type, e.dest_id, e.dest_type, e.etl_id, d.depth+1
      FROM descendants d, v_edges e
      WHERE e.src_id=d.dest_id AND d.dest_type <> 'DOCKER_IMAGE'
  )
  SELECT m.name,d.src_id,d.dest_id as id,d.dest_type, d.etl_id
    FROM descendants d
    INNER JOIN v_metadata m ON m.id=d.dest_id;
END
---
CREATE PROCEDURE `sp_select_graph_by_mid`(IN mid INT, IN max_depth INT)
SQL SECURITY INVOKER
BEGIN
  WITH RECURSIVE descendants AS
  (
    SELECT e.src_id,e.src_type,e.dest_id as dest_id,e.dest_type, e.etl_id, 0 as depth  FROM v_edges e
      WHERE e.src_id = mid
    UNION DISTINCT
    SELECT e.src_id, e.src_type, e.dest_id, e.dest_type, e.etl_id, d.depth +1
      FROM descendants d, v_edges e
      WHERE e.src_id=d.dest_id AND d.dest_type <> 'DOCKER_IMAGE' AND d.dest_type <> 'COMPUTE_POLICY' AND depth < max_depth
  )
  SELECT m.name,d.src_id,d.src_type,d.dest_id as id,d.dest_type,d.etl_id
    FROM descendants d
    INNER JOIN v_metadata m ON m.id=d.dest_id;
END
---
DROP PROCEDURE IF EXISTS `sp_select_single_graph_by_mid`;
---
CREATE PROCEDURE `sp_select_single_graph_by_mid`(IN mid INT, IN max_depth INT)
SQL SECURITY INVOKER
BEGIN
  WITH RECURSIVE descendants AS
  (
    SELECT e.src_id,e.src_type,e.dest_id as dest_id,e.dest_type, e.etl_id, 0 as depth  FROM v_edges e
      WHERE e.src_id = mid
    UNION DISTINCT
    SELECT e.src_id, e.src_type, e.dest_id, e.dest_type, e.etl_id, d.depth +1
      FROM descendants d, v_edges e
      WHERE e.src_id=d.dest_id AND d.dest_type <> 'KNOWLEDGE_OBJECT' AND d.dest_type <> 'DOCKER_IMAGE' AND d.dest_type <> 'COMPUTE_POLICY' AND depth < max_depth
  )
  SELECT m.name,d.src_id,d.src_type,d.dest_id as id,d.dest_type,d.etl_id
    FROM descendants d
    INNER JOIN v_metadata m ON m.id=d.dest_id;
END
---
DROP PROCEDURE IF EXISTS `sp_admin_select_graph_by_mid`;
---
CREATE PROCEDURE `sp_admin_select_graph_by_mid`(IN mid INT, IN max_depth INT)
SQL SECURITY INVOKER
BEGIN
  WITH RECURSIVE descendants AS
  (
    SELECT e.src_id,e.src_type,e.dest_id as dest_id,e.dest_type, e.etl_id, 0 as depth  FROM edges e
      WHERE e.src_id = mid
    UNION DISTINCT
    SELECT e.src_id, e.src_type, e.dest_id, e.dest_type, e.etl_id, d.depth +1
      FROM descendants d, edges e
      WHERE e.src_id=d.dest_id AND d.depth < max_depth
  )
  SELECT m.name,d.src_id,d.src_type,d.dest_id as id,d.dest_type,d.etl_id
    FROM descendants d
    INNER JOIN metadata m ON m.id=d.dest_id;
END
---
DROP PROCEDURE IF EXISTS `sp_admin_delete_graph_by_mid`;
---
CREATE PROCEDURE `sp_admin_delete_graph_by_mid`(IN mid INT, IN max_depth INT)
SQL SECURITY INVOKER
BEGIN
  WITH RECURSIVE descendants AS
  (
    SELECT e.src_id,e.src_type,e.dest_id as dest_id,e.dest_type, e.etl_id, 0 as depth  FROM edges e
      WHERE e.src_id = mid
    UNION DISTINCT
    SELECT e.src_id, e.src_type, e.dest_id, e.dest_type, e.etl_id, d.depth +1
      FROM descendants d, edges e
      WHERE e.src_id=d.dest_id AND d.depth < max_depth
  )
  DELETE m
    FROM descendants d
    INNER JOIN metadata m ON m.id=d.dest_id;
END
---
DROP PROCEDURE IF EXISTS `sp_delete_graph_by_mid`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_delete_graph_by_mid`(IN mid INT, IN max_depth INT)
BEGIN
  DECLARE userid INTEGER DEFAULT -1;
  SELECT `id` FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED() INTO userid;
  WITH RECURSIVE descendants AS
  (
    SELECT e.src_id,e.src_type,e.dest_id as dest_id,e.dest_type, e.etl_id, 0 as depth  FROM v_edges e
      WHERE e.src_id = mid
    UNION DISTINCT
    SELECT e.src_id, e.src_type, e.dest_id, e.dest_type, e.etl_id, d.depth +1
      FROM descendants d, v_edges e
      WHERE e.src_id=d.dest_id AND d.depth < max_depth
  )
  DELETE m
    FROM descendants d
    INNER JOIN metadata m ON m.id=d.dest_id JOIN v_metadata vm ON vm.id=m.id WHERE m.created_by_id=userid;
END
---
DROP PROCEDURE IF EXISTS `sp_soft_delete_graph_by_mid`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_soft_delete_graph_by_mid`(IN mid INT, IN max_depth INT)
BEGIN
 DECLARE userid INTEGER DEFAULT -1;
 SELECT `id` FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED() INTO userid;
  WITH RECURSIVE descendants AS
  (
    SELECT e.src_id,e.src_type,e.dest_id as dest_id,e.dest_type, e.etl_id, 0 as depth  FROM v_edges e
      WHERE e.src_id = mid
    UNION DISTINCT
    SELECT e.src_id, e.src_type, e.dest_id, e.dest_type, e.etl_id, d.depth +1
      FROM descendants d, v_edges e
      WHERE e.src_id=d.dest_id AND d.depth < max_depth
  )
  UPDATE descendants d
    INNER JOIN metadata m ON m.id=d.dest_id JOIN v_metadata vm ON vm.id=m.id SET m.deleted=1 WHERE m.created_by_id=userid; 
END
---
DROP PROCEDURE IF EXISTS `sp_link`
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_link`(IN from_type ENUM('ETL_PROCESS','MODEL','STORAGE','DATASTREAM','CODE','SIMULATOR','KNOWLEDGE_OBJECT','ACTUATOR','UIVIEW', 'DASHBOARD', 'DOCKER_JOB','DEPLOYMENT','COMPUTE_POLICY', 'PROJECT', 'STORAGE_POLICY', 'COMPUTE_RESOURCE_GROUP', 'DOCKER_IMAGE'), IN to_type ENUM('ETL_PROCESS','MODEL','STORAGE','DATASTREAM','CODE','SIMULATOR','KNOWLEDGE_OBJECT','ACTUATOR','UIVIEW','DASHBOARD','DOCKER_JOB','DEPLOYMENT', 'COMPUTE_POLICY', 'PROJECT', 'STORAGE_POLICY', 'COMPUTE_RESOURCE_GROUP',  'DOCKER_IMAGE'), IN from_mid INT, to_mid INT)
BEGIN
  DECLARE has_access BOOLEAN DEFAULT 0;
  WITH userid (uid) AS (SELECT id FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED()),
    owned (mid) AS (SELECT m.id FROM metadata m
                          INNER JOIN users u ON m.created_by_id=u.id
                          INNER JOIN userid ON userid.uid = u.id
                        ),
    acl_groups (mid) AS (SELECT m.id FROM metadata m
                          INNER JOIN read_acl a ON a.wob_mid=m.id
                          INNER JOIN group_maps g ON g.gid = a.gid
                          INNER JOIN users u ON u.id = g.uid
                          INNER JOIN userid ON userid.uid = u.id)
    SELECT mt.mid > 0
      INTO has_access
      FROM (SELECT owned.mid AS mid FROM owned
            UNION
            SELECT acl_groups.mid AS mid FROM acl_groups
            ) AS mt
      WHERE mt.mid = from_mid;
  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
			SET MESSAGE_TEXT = "Parameter from_mid is invalid or user doesn't have access to this object.";
  END IF;
  SET has_access = 0;
  WITH userid (uid) AS (SELECT id FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED()),
    owned (mid) AS (SELECT m.id FROM metadata m
                          INNER JOIN users u ON m.created_by_id=u.id
                          INNER JOIN userid ON userid.uid = u.id
                        ),
    acl_groups (mid) AS (SELECT m.id FROM metadata m
                          INNER JOIN read_acl a ON a.wob_mid=m.id
                          INNER JOIN group_maps g ON g.gid = a.gid
                          INNER JOIN users u ON u.id = g.uid
                          INNER JOIN userid ON userid.uid = u.id)
    SELECT mt.mid > 0
      INTO has_access
      FROM (SELECT owned.mid AS mid FROM owned
            UNION
            SELECT acl_groups.mid AS mid FROM acl_groups
            ) AS mt
      WHERE mt.mid = to_mid
      LIMIT 1;
  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
			SET MESSAGE_TEXT = "Parameter to_mid is invalid or user doesn't have access to this object.";
  END IF;
  INSERT INTO edges (src_type, src_id, dest_type, dest_id) VALUES (from_type, from_mid, to_type, to_mid);
END
---
DROP PROCEDURE IF EXISTS `sp_unlink`
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_unlink`(IN from_mid INT, to_mid INT)
BEGIN
  DECLARE has_access BOOLEAN DEFAULT 0;
  WITH owned (mid) AS (SELECT m.id FROM metadata m
                      INNER JOIN users u ON m.created_by_id=u.id
                      WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED()
                    ),
      acl_groups (mid) AS (SELECT m.id FROM metadata m
                            INNER JOIN read_acl a ON a.wob_mid=m.id
                            INNER JOIN group_maps g ON g.gid = a.gid
                            INNER JOIN users u ON u.id = g.uid
                            WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED())
        SELECT mt.mid > 0
          INTO has_access
          FROM (SELECT owned.mid AS mid FROM owned
                UNION
                SELECT acl_groups.mid AS mid FROM acl_groups
                ) AS mt
          WHERE mt.mid = from_mid
          LIMIT 1;

  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
			SET MESSAGE_TEXT = "Parameter from_mid is invalid or user doesn't have access to this object.";
  END IF;
  SET has_access = 0;
  WITH owned (mid) AS (SELECT m.id FROM metadata m
                      INNER JOIN users u ON m.created_by_id=u.id
                      WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED()
                    ),
      acl_groups (mid) AS (SELECT m.id FROM metadata m
                            INNER JOIN read_acl a ON a.wob_mid=m.id
                            INNER JOIN group_maps g ON g.gid = a.gid
                            INNER JOIN users u ON u.id = g.uid
                            WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED())
        SELECT mt.mid > 0
          INTO has_access
          FROM (SELECT owned.mid AS mid FROM owned
                UNION
                SELECT acl_groups.mid AS mid FROM acl_groups
                ) AS mt
          WHERE mt.mid = to_mid
          LIMIT 1;

  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
			SET MESSAGE_TEXT = "Parameter to_mid is invalid or user doesn't have access to this object.";
  END IF;
  PREPARE stmt FROM "DELETE FROM edges WHERE src_id = ? AND dest_id = ?";
  set @a= from_mid;
  set @b= to_mid;
  EXECUTE stmt USING @a, @b;
  DEALLOCATE PREPARE stmt;
END
---
DROP PROCEDURE IF EXISTS `get_wob_message_for_user`;
---
CREATE PROCEDURE `get_wob_message_for_user`(IN u VARCHAR(40), IN t VARCHAR(40))
SQL SECURITY INVOKER
BEGIN
DECLARE wid INT;
SET @ticket = current_timestamp(2);
SELECT `id`
  FROM wob_message_queue
  WHERE `status` = 0 AND `user` = u AND `target` = t
  ORDER BY `priority` DESC,`write_ts` ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED
  INTO wid;
IF wid IS NOT NULL THEN
  UPDATE wob_message_queue
    SET `status` = 1,
        `read_ts` = @ticket
    WHERE `status` = 0
    AND `id` = wid;
  SELECT `id`,
        `wob_id`,
        `wob_type`,
        `payload`,
        `priority`,
        `write_ts`,
        `read_ts`,
        `target`,
        `user`
    FROM wob_message_queue
    WHERE `id` = wid;
END IF;
END
---
DROP PROCEDURE IF EXISTS `sp_notify_processor`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_notify_processor` (IN v_project_id INTEGER, IN v_payload JSON)
BEGIN
  DECLARE v_user VARCHAR(40) DEFAULT '';
  SELECT SUBSTRING(CURRENT_MIRANDA_USER(),9) INTO v_user;
  INSERT INTO wob_message_queue (user, wob_type, wob_id, payload, `priority`, target) VALUES (v_user, 'KNOWLEDGE_OBJECT', v_project_id, v_payload, 0, 'processor');
END;
---
DROP PROCEDURE IF EXISTS `get_wob_message_for_processor`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `get_wob_message_for_processor`(IN project_id INTEGER)
BEGIN
DECLARE wid INT;
DECLARE v_user VARCHAR(40) DEFAULT '';
SELECT SUBSTRING(CURRENT_MIRANDA_USER(),9) INTO v_user;
SET @ticket = current_timestamp(2);
SELECT `id`
  FROM wob_message_queue
  WHERE `status` = 0 AND `user` = v_user AND `target` = 'processor' AND `wob_id` = project_id
  ORDER BY `priority` DESC,`write_ts` ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED
  INTO wid;
IF wid IS NOT NULL THEN
  UPDATE wob_message_queue
    SET `status` = 1,
        `read_ts` = @ticket
    WHERE `status` = 0
    AND `id` = wid;
  SELECT t.`id`,
        t.`wob_id`,
        t.`wob_type`,
        t.`payload`,
        t.`priority`,
        t.`write_ts`,
        t.`read_ts`,
        t.`target`,
        t.`user`
    FROM wob_message_queue t WHERE t.`wob_id` = project_id AND t.`target` = 'processor' AND t.`user` = v_user AND t.`id`=wid;
END IF;
END
---
DROP PROCEDURE IF EXISTS `get_own_wob_message`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `get_own_wob_message`(IN target VARCHAR(40))
BEGIN
DECLARE wid INT;
DECLARE v_user VARCHAR(40) DEFAULT '';
SELECT SUBSTRING(CURRENT_MIRANDA_USER(),9) INTO v_user;
SET @ticket = current_timestamp(2);
SELECT `id`
  FROM wob_message_queue
  WHERE `status` = 0 AND `user` = v_user AND `target` = target
  ORDER BY `priority` DESC,`write_ts` ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED
  INTO wid;
IF wid IS NOT NULL THEN
  UPDATE wob_message_queue
    SET `status` = 1,
        `read_ts` = @ticket
    WHERE `status` = 0
    AND `id` = wid;
  SELECT t.`id`,
        t.`wob_id`,
        t.`wob_type`,
        t.`payload`,
        t.`priority`,
        t.`write_ts`,
        t.`read_ts`,
        t.`target`,
        t.`user`
    FROM wob_message_queue t WHERE t.`target` = target AND t.`user` = v_user AND t.`id`=wid;
END IF;
END
---
DROP PROCEDURE IF EXISTS `get_wob_message_for_target_by_id`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `get_wob_message_for_target_by_id`(IN target VARCHAR(40), IN project_id INTEGER)
BEGIN
DECLARE wid INT;
DECLARE v_user VARCHAR(40) DEFAULT '';
SELECT SUBSTRING(CURRENT_MIRANDA_USER(),9) INTO v_user;
SET @ticket = current_timestamp(2);
SELECT `id`
  FROM wob_message_queue
  WHERE `status` = 0 AND `user` = v_user AND `target` = target AND `wob_id` = project_id
  ORDER BY `priority` DESC,`write_ts` ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED
  INTO wid;
IF wid IS NOT NULL THEN
  UPDATE wob_message_queue
    SET `status` = 1,
        `read_ts` = @ticket
    WHERE `status` = 0
    AND `id` = wid;
  SELECT t.`id`,
        t.`wob_id`,
        t.`wob_type`,
        t.`payload`,
        t.`priority`,
        t.`write_ts`,
        t.`read_ts`,
        t.`target`,
        t.`user`
    FROM wob_message_queue t WHERE t.`wob_id` = project_id AND t.`target` = target AND t.`user` = v_user AND t.`id`=wid;
END IF;
END
---
DROP PROCEDURE IF EXISTS `get_wob_message_from_control`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `get_wob_message_from_control`(IN wob_id INTEGER)
BEGIN
DECLARE wid INT;
DECLARE v_user VARCHAR(40) DEFAULT '';
SELECT SUBSTRING(CURRENT_MIRANDA_USER(),9) INTO v_user;
SET @ticket = current_timestamp(2);
SELECT `id`
  FROM wob_message_queue
  WHERE `status` = 0 AND `user` = v_user AND `target` = 'wob' AND `wob_id` = wob_id
  ORDER BY `priority` DESC,`write_ts` ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED
  INTO wid;
IF wid IS NOT NULL THEN
  UPDATE wob_message_queue
    SET `status` = 1,
        `read_ts` = @ticket
    WHERE `status` = 0
    AND `id` = wid;
  SELECT t.`id`,
        t.`wob_id`,
        t.`wob_type`,
        t.`payload`,
        t.`priority`,
        t.`write_ts`,
        t.`read_ts`,
        t.`target`,
        t.`user`
    FROM wob_message_queue t WHERE t.`wob_id` = wob_id AND t.`target` = 'wob' AND t.`user` = v_user AND t.`id`=wid;
END IF;
END
---
DROP PROCEDURE IF EXISTS `clear_wob_messages_for_processor`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `clear_wob_messages_for_processor`(IN project_id INTEGER)
BEGIN
DECLARE wid INT;
DECLARE v_user VARCHAR(40) DEFAULT '';
SELECT SUBSTRING(CURRENT_MIRANDA_USER(),9) INTO v_user;
SET @ticket = current_timestamp(2);
UPDATE wob_message_queue
  SET `status` = 2,
      `read_ts` = @ticket
  WHERE `status` = 0
    AND `user` = v_user
    AND `target` = 'processor'
    AND `wob_id` = project_id;
DELETE FROM wob_message_queue WHERE read_ts < UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 1 DAY));
END
---
DROP PROCEDURE IF EXISTS `get_wob_message`;
---
CREATE PROCEDURE `get_wob_message`(IN t VARCHAR(40))
SQL SECURITY INVOKER
BEGIN
DECLARE wid INT;
SET @ticket = current_timestamp(2);
SELECT `id`
  FROM wob_message_queue
  WHERE `status` = 0 AND `target` = t
  ORDER BY `priority` DESC,`write_ts` ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED
  INTO wid;
IF wid IS NOT NULL THEN
  UPDATE wob_message_queue
    SET `status` = 1,
        `read_ts` = @ticket
    WHERE `status` = 0
    AND `id` = wid;
  SELECT `id`,
        `wob_id`,
        `wob_type`,
        `payload`,
        `priority`,
        `write_ts`,
        `read_ts`,
        `target`,
        `user`
    FROM wob_message_queue
    WHERE `id` = wid;
END IF;
END
---
DROP PROCEDURE IF EXISTS `sp_set_edge_attribute`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_set_edge_attribute`(IN psrc_mid INT, IN pdest_mid INT, IN etl_id INT, IN attr JSON)
BEGIN
  DECLARE has_access BOOLEAN DEFAULT 0;
  WITH owned (mid) AS (SELECT m.id FROM metadata m
                      INNER JOIN users u ON m.created_by_id=u.id
                      WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED()
                    ),
      acl_groups (mid) AS (SELECT m.id FROM metadata m
                            INNER JOIN read_acl a ON a.wob_mid=m.id
                            INNER JOIN group_maps g ON g.gid = a.gid
                            INNER JOIN users u ON u.id = g.uid
                            WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED())
        SELECT mt.mid > 0
          INTO has_access
          FROM (SELECT owned.mid AS mid FROM owned
                UNION
                SELECT acl_groups.mid AS mid FROM acl_groups
                ) AS mt
          WHERE mt.mid = psrc_mid
          LIMIT 1;
  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Parameter psrc_mid is invalid or user doesn''t have access to this object.';
  END IF;
  SET has_access = 0;
  WITH owned (mid) AS (SELECT m.id FROM metadata m
                      INNER JOIN users u ON m.created_by_id=u.id
                      WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED()
                    ),
      acl_groups (mid) AS (SELECT m.id FROM metadata m
                            INNER JOIN read_acl a ON a.wob_mid=m.id
                            INNER JOIN group_maps g ON g.gid = a.gid
                            INNER JOIN users u ON u.id = g.uid
                            WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED())
        SELECT mt.mid > 0
          INTO has_access
          FROM (SELECT owned.mid AS mid FROM owned
                UNION
                SELECT acl_groups.mid AS mid FROM acl_groups
                ) AS mt
          WHERE mt.mid = pdest_mid
          LIMIT 1;
  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Parameter pdest_mid is invalid or user doesn''t have access to this object.';
  END IF;
  IF etl_id = -1 THEN
    SET etl_id = NULL;
  END IF;
  UPDATE edges SET `etl_id` = etl_id, `attributes` = attr WHERE src_id = psrc_mid AND dest_id = pdest_mid;
END
---
DROP PROCEDURE IF EXISTS `sp_claim_deployment_job`;
---
CREATE PROCEDURE `sp_claim_deployment_job`()
SQL SECURITY INVOKER
BEGIN
  DECLARE deployment_id INT;
  SELECT g.id INTO deployment_id FROM deployment g WHERE g.workflow_state = 'UNDEPLOYED' LIMIT 1 FOR UPDATE;
  UPDATE deployment SET workflow_state = 'DEPLOYING' WHERE id = deployment_id;
  SELECT * FROM deployment WHERE id = deployment_id;
END;
---
DROP PROCEDURE IF EXISTS `sp_claim_proxy_account`;
---
CREATE PROCEDURE `sp_claim_proxy_account`()
SQL SECURITY INVOKER
BEGIN
  DECLARE username CHAR(32);
  SELECT user INTO username FROM mysql.user WHERE (User_attributes->>"$.is_proxy" = "true") AND (User_attributes->>"$.is_free" = "true") LIMIT 1 FOR UPDATE;
  UPDATE mysql.user SET User_attributes = JSON_SET(User_attributes, '$.is_free', FALSE) WHERE user = username;
  SELECT user, host, User_attributes FROM mysql.user WHERE user = username;
END;
---
DROP VIEW IF EXISTS v_proxy_accounts;
---
CREATE DEFINER = miranda_internal@localhost VIEW v_proxy_accounts AS
(
  SELECT user
  FROM mysql.default_roles
  WHERE DEFAULT_ROLE_USER = CURRENT_MIRANDA_USER() AND USER LIKE 'pxy.%'
);
---
DROP PROCEDURE IF EXISTS `sp_delete_object`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_delete_object`(IN oid INT)
    MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(40);
  SET db_user = CURRENT_MIRANDA_USER_UNPREFIXED();
   WITH owned (mid) AS (SELECT m.id FROM metadata m
                        INNER JOIN users u ON m.created_by_id=u.id
                        WHERE u.username = db_user
                           AND m.id= oid),
       acl_groups (mid) AS (SELECT m.id FROM metadata m
                            INNER JOIN write_acl a ON a.wob_mid=m.id
                            INNER JOIN group_maps g ON g.gid = a.gid
                            INNER JOIN users u ON u.id = g.uid
                            WHERE u.username = db_user
                               AND m.id=oid)
    SELECT mid FROM (SELECT owned.mid AS mid FROM owned
                        UNION
                        SELECT acl_groups.mid AS mid FROM acl_groups
                    ) AS mt
    INTO @mid;
  SET @stmt= "DELETE FROM metadata m WHERE m.id= ?";
  PREPARE `dynstmt` FROM @stmt;
  EXECUTE `dynstmt` USING @mid;
  DEALLOCATE PREPARE `dynstmt`;
END
---
DROP PROCEDURE IF EXISTS `sp_update_storage_data`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_update_storage_data`(IN oid INT, IN data LONGBLOB)
    MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(40);
  SET db_user = CURRENT_MIRANDA_USER_UNPREFIXED();
  WITH owned (mid) AS (SELECT m.id FROM metadata m
                        INNER JOIN users u ON m.created_by_id=u.id
                        WHERE u.username = db_user
                           AND m.id= oid),
       acl_groups (mid) AS (SELECT m.id FROM metadata m
                            INNER JOIN write_acl a ON a.wob_mid=m.id
                            INNER JOIN group_maps g ON g.gid = a.gid
                            INNER JOIN users u ON u.id = g.uid
                            WHERE u.username = db_user
                               AND m.id=oid)
    SELECT mid FROM (SELECT owned.mid AS mid FROM owned
                        UNION
                        SELECT acl_groups.mid AS mid FROM acl_groups
                    ) AS mt
    INTO @mid;
  UPDATE storage t INNER JOIN metadata m ON m.id = t.metadata_id SET t.`data` = unhex(data) WHERE m.id= @mid;
END
---
DROP PROCEDURE IF EXISTS `sp_update_metadata`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_update_metadata`(IN mid INT,IN change_json MEDIUMTEXT)
    MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(40);
  DECLARE m_id INT;
  SET db_user = CURRENT_MIRANDA_USER_UNPREFIXED();
  SET @c = TRIM(BOTH "'" FROM change_json);

  SELECT json_extract(@c,"$[0].name") INTO @update_name;
  SET @update_name = TRIM(BOTH '"' FROM @update_name);
  SET @update_name = CONVERT(FROM_BASE64(@update_name) USING UTF8MB4);
  SET @sets = "";
  SET @prefix = "SET ";
  IF @update_name IS NOT NULL THEN
    SET @sets = CONCAT(@sets,@prefix,"m.name= @update_name");
  END IF;

  SELECT json_extract(@c,"$[0].description") INTO @update_desc;
  SET @update_desc = TRIM(BOTH '"' FROM @update_desc);
  SET @update_desc = CONVERT(FROM_BASE64(@update_desc) USING UTF8MB4);
  IF @update_desc IS NOT NULL THEN
    IF CHAR_LENGTH(@sets) > 4 THEN
      SET @prefix = ", ";
    END IF;
    SET @sets = CONCAT(@sets,@prefix, "m.description= @update_desc");
  END IF;

  WITH owned (mid) AS (SELECT m.id FROM metadata m
                        INNER JOIN users u ON m.created_by_id=u.id
                        WHERE u.username = db_user
                           AND m.id= mid),
       acl_groups (mid) AS (SELECT m.id FROM metadata m
                            INNER JOIN write_acl a ON a.wob_mid=m.id
                            INNER JOIN group_maps g ON g.gid = a.gid
                            INNER JOIN users u ON u.id = g.uid
                            WHERE u.username = db_user
                               AND m.id=mid)
    SELECT DISTINCT mid FROM (SELECT owned.mid AS mid FROM owned
                        UNION
                        SELECT acl_groups.mid AS mid FROM acl_groups
                    ) AS mt
    INTO m_id;
  SET @stmt= concat("UPDATE metadata m ",@sets," WHERE m.id= ?");
  SELECT @stmt;
  SET @p1=m_id;
  PREPARE `dynstmt` FROM @stmt;
  EXECUTE `dynstmt` USING @p1;
  DEALLOCATE PREPARE `dynstmt`;
  SET @stmt = NULL;
  SET @sets = NULL;
  SET @prefix = NULL;
END
---
DROP PROCEDURE IF EXISTS `tag_object`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `tag_object`(IN wob_type VARCHAR(20), IN wob_mid INT, IN tag VARCHAR(20))
    MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(40);
  DECLARE user_id INTEGER DEFAULT -1;
  DECLARE m_id INT;
  DECLARE has_access BOOLEAN DEFAULT 0;
  SET db_user = CURRENT_MIRANDA_USER_UNPREFIXED();
  SET user_id = (SELECT id FROM users WHERE username = db_user);
  WITH owned (mid) AS (SELECT m.id FROM metadata m
                      INNER JOIN users u ON m.created_by_id=u.id
                      WHERE u.username = db_user
                    ),
      acl_groups (mid) AS (SELECT m.id FROM metadata m
                            INNER JOIN read_acl a ON a.wob_mid=m.id
                            INNER JOIN group_maps g ON g.gid = a.gid
                            INNER JOIN users u ON u.id = g.uid
                            WHERE u.username = db_user)
        SELECT mt.mid > 0
          INTO has_access
          FROM (SELECT owned.mid AS mid FROM owned
                UNION
                SELECT acl_groups.mid AS mid FROM acl_groups
                ) AS mt
          WHERE mt.mid = wob_mid
          LIMIT 1;
  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
			SET MESSAGE_TEXT = "Parameter wob_id is invalid or user doesn't have access to this object.";
  END IF;
  INSERT INTO tag2metadata (tag, wob_type, metadata_id, user_id) VALUES (tag, wob_type, wob_mid, user_id);
END
---
DROP PROCEDURE IF EXISTS `public_tag_object`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `public_tag_object`(IN wob_type VARCHAR(20), IN wob_mid INT, IN tag VARCHAR(20))
    MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(40);
  DECLARE user_id INTEGER DEFAULT -1;
  DECLARE m_id INT;
  DECLARE has_access BOOLEAN DEFAULT 0;
  SET db_user = CURRENT_MIRANDA_USER();
  WITH owned (mid) AS (SELECT m.id FROM metadata m
                      INNER JOIN users u ON m.created_by_id=u.id
                      WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED()
                    ),
      acl_groups (mid) AS (SELECT m.id FROM metadata m
                            INNER JOIN write_acl a ON a.wob_mid=m.id
                            INNER JOIN group_maps g ON g.gid = a.gid
                            INNER JOIN users u ON u.id = g.uid
                            WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED())
        SELECT mt.mid > 0
          INTO has_access
          FROM (SELECT owned.mid AS mid FROM owned
                UNION
                SELECT acl_groups.mid AS mid FROM acl_groups
                ) AS mt
          WHERE mt.mid = wob_mid
          LIMIT 1;
  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
			SET MESSAGE_TEXT = "Parameter wob_id is invalid or user doesn't have access to this object.";
  END IF;
  INSERT INTO tag2metadata (tag, wob_type, metadata_id, user_id) VALUES (tag, wob_type, wob_mid, -1);
END
---
DROP VIEW IF EXISTS `vtag2metadata`;
---
CREATE DEFINER=`miranda_internal`@`localhost` VIEW `vtag2metadata` AS
    SELECT t.tag, m.id, m.name, t.wob_type, t.user_id
      FROM tag2metadata t
      INNER JOIN v_metadata m ON m.id = t.metadata_id;
---
DROP VIEW IF EXISTS `v_tags_per_wob`;
---
CREATE DEFINER=`miranda_internal`@`localhost` VIEW `v_tags_per_wob` AS
    SELECT JSON_ARRAYAGG(t.tag), JSON_ARRAYAGG(t.user_id), m.id as metadata_id, t.wob_type
    FROM tag2metadata t
    INNER JOIN v_metadata m ON m.id = t.metadata_id GROUP BY m.id,t.wob_type;
---
DROP VIEW IF EXISTS `v_tags_per_ko`;
---
CREATE DEFINER=`miranda_internal`@`localhost` VIEW `v_tags_per_ko` AS
    SELECT CONCAT(
      '[',
      GROUP_CONCAT(t.tag SEPARATOR ','),
      ']') AS tags, m.id, t.wob_type
    FROM tag2metadata t
    INNER JOIN v_metadata m ON m.id = t.metadata_id GROUP BY m.id,t.wob_type
    HAVING t.wob_type = 'KNOWLEDGE_OBJECT';
---
DROP PROCEDURE IF EXISTS `untag_object`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `untag_object`(IN wob_mid INT, IN tag VARCHAR(20))
    MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(40);
  DECLARE user_id INTEGER DEFAULT -1;
  DECLARE has_access BOOLEAN DEFAULT 0;
  SET db_user = CURRENT_MIRANDA_USER_UNPREFIXED();
  SET user_id = (SELECT id FROM users WHERE username = db_user);
  WITH owned (mid) AS (SELECT m.id FROM metadata m
                      INNER JOIN users u ON m.created_by_id=u.id
                      WHERE u.username = db_user
                    ),
      acl_groups (mid) AS (SELECT m.id FROM metadata m
                            INNER JOIN read_acl a ON a.wob_mid=m.id
                            INNER JOIN group_maps g ON g.gid = a.gid
                            INNER JOIN users u ON u.id = g.uid
                            WHERE u.username = db_user)
        SELECT mt.mid > 0
          INTO has_access
          FROM (SELECT owned.mid AS mid FROM owned
                UNION
                SELECT acl_groups.mid AS mid FROM acl_groups
                ) AS mt
          WHERE mt.mid = wob_mid
          LIMIT 1;
  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Parameter wob_id is invalid or user doesn't have access to this object.";
  END IF;
  DELETE FROM tag2metadata t WHERE t.tag = tag AND t.metadata_id = wob_mid AND t.user_id=user_id;
  COMMIT;
END
---
DROP PROCEDURE IF EXISTS `public_untag_object`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `public_untag_object`(IN wob_mid INT, IN tag VARCHAR(20))
    MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(40);
  DECLARE user_id INTEGER DEFAULT -1;
  DECLARE has_access BOOLEAN DEFAULT 0;
  SET db_user = CURRENT_MIRANDA_USER();
  WITH owned (mid) AS (SELECT m.id FROM metadata m
                      INNER JOIN users u ON m.created_by_id=u.id
                      WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED()
                    ),
      acl_groups (mid) AS (SELECT m.id FROM metadata m
                            INNER JOIN write_acl a ON a.wob_mid=m.id
                            INNER JOIN group_maps g ON g.gid = a.gid
                            INNER JOIN users u ON u.id = g.uid
                            WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED())
        SELECT mt.mid > 0
          INTO has_access
          FROM (SELECT owned.mid AS mid FROM owned
                UNION
                SELECT acl_groups.mid AS mid FROM acl_groups
                ) AS mt
          WHERE mt.mid = wob_mid
          LIMIT 1;
  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
			SET MESSAGE_TEXT = "Parameter wob_id is invalid or user doesn't have access to this object.";
  END IF;
  DELETE FROM tag2metadata t WHERE t.tag = tag AND metadata_id = wob_mid AND t.user_id=user_id;
END
---
DROP VIEW IF EXISTS v_user;
---
CREATE DEFINER = miranda_internal@localhost VIEW v_user AS
(
  SELECT id, username
  FROM miranda.users
  WHERE username = SUBSTRING(CURRENT_MIRANDA_USER(), 9)
);
---
DROP VIEW IF EXISTS v_user_detail;
---
CREATE DEFINER = miranda_internal@localhost VIEW v_user_detail AS
(
  SELECT u.id as user_id, ud.id, u.username, ud.email, ud.first_name, ud.last_name, ud.phone, ud.industry, ud.role, ud.account_status, ud.avatar, ud.consented
  FROM miranda.v_user u JOIN miranda.users_details ud ON u.id = ud.user_id
);
---
DROP PROCEDURE IF EXISTS `sp_extend_proxy_account_claim`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE `sp_extend_proxy_account_claim`(IN by_application VARCHAR(255))
MODIFIES SQL DATA
BEGIN
  DECLARE is_owner BOOLEAN DEFAULT 0;
  DECLARE proxy_account VARCHAR(32);
  SET proxy_account = SUBSTRING_INDEX(USER(), '@', 1);
  SELECT COUNT(*) > 0 INTO is_owner FROM information_schema.APPLICABLE_ROLES WHERE USER = proxy_account LIMIT 1;
  IF is_owner <> 1 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Proxy account is not owned by anyone.";
  END IF;
  INSERT INTO proxy_account_claims (name, belonging_to, at, by_application)
  VALUES (proxy_account, CURRENT_MIRANDA_USER(), NOW(), by_application);
END;
---
DROP VIEW IF EXISTS v_tokens;
---
CREATE DEFINER = miranda_internal@localhost VIEW v_tokens AS
(
  SELECT
    name,
    GROUP_CONCAT(DISTINCT by_application SEPARATOR ',') AS applications,
    MAX(at) AS last_used,
    DATE_ADD(MAX(at), INTERVAL 7 DAY) AS expires
  FROM proxy_account_claims
  WHERE belonging_to = CURRENT_MIRANDA_USER()
  GROUP BY name, belonging_to
);
---
DROP VIEW IF EXISTS v_miranda_logs;
---
CREATE DEFINER = miranda_internal@localhost VIEW v_miranda_logs AS
(

  SELECT
    l.id,
    l.created_at,
    l.message,
    l.tag,
    l.class_id,
    l.instance_id
  FROM miranda_logs l
  LEFT JOIN miranda.users u ON u.id = l.user_id
  WHERE username = SUBSTRING(CURRENT_MIRANDA_USER(), 9)
);
---
DROP PROCEDURE IF EXISTS `sp_log`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE `sp_log`(IN v_class_id SMALLINT, IN v_instance_id INT, IN v_tag SMALLINT, IN v_message TEXT)
MODIFIES SQL DATA
BEGIN
  DECLARE user_id INT DEFAULT -1;
  SET user_id = (SELECT id FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED());
  INSERT INTO miranda_logs (user_id, class_id, instance_id, tag, message) VALUES (user_id, v_class_id, v_instance_id, v_tag, v_message);
END;
---
DROP PROCEDURE IF EXISTS `sp_delete_log_by_id`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE `sp_delete_log_by_id`(IN v_id JSON)
MODIFIES SQL DATA
BEGIN
  DECLARE uid INT DEFAULT -1;
  SET uid = (SELECT id FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED());
  DELETE FROM miranda_logs WHERE id in (SELECT CONCAT(i) FROM JSON_TABLE(v_id, '$[*]' COLUMNS (i INT PATH '$')) AS t) AND user_id = uid;
END;
---
DROP PROCEDURE IF EXISTS `sp_delete_log_by_instance`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE `sp_delete_log_by_instance`(IN v_class_id INT, IN v_instance_ids JSON)
MODIFIES SQL DATA
BEGIN
  DECLARE uid INT DEFAULT -1;
  SET uid = (SELECT id FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED());
  DELETE FROM miranda_logs WHERE instance_id in (SELECT CONCAT(i) FROM JSON_TABLE(v_instance_ids, '$[*]' COLUMNS (i INT PATH '$')) AS t) AND user_id = uid AND class_id=v_class_id;
END;
---
DROP PROCEDURE IF EXISTS `sp_consume_realtime_message_queue`;
---
CREATE PROCEDURE `sp_consume_realtime_message_queue`(IN v_limit INT)
SQL SECURITY INVOKER
MODIFIES SQL DATA
BEGIN
  DECLARE v_id INT DEFAULT 0;
  DECLARE v_via ENUM('admin', 'user');
  DECLARE v_by CHAR(40);
  DECLARE v_for CHAR(40);
  DECLARE v_ticket VARCHAR(64);
  DECLARE v_payload MEDIUMTEXT;
  DECLARE v_created_at TIMESTAMP(2);
  DECLARE v_done INT DEFAULT 0;
  DECLARE v_cursor CURSOR FOR
    SELECT id, via, sent_by, sent_for, ticket, payload, created_at FROM realtime_message_queue WHERE sent_for <> 'processor' ORDER BY created_at LIMIT v_limit;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;
  OPEN v_cursor;
  consume_loop: LOOP
    FETCH v_cursor INTO v_id, v_via, v_by, v_for, v_ticket, v_payload, v_created_at;
    IF v_done = 1 THEN
      LEAVE consume_loop;
    END IF;
    DELETE FROM realtime_message_queue WHERE id = v_id;
    SELECT v_id, v_via, v_by, v_for, v_ticket, v_payload, v_created_at;
  END LOOP consume_loop;
  CLOSE v_cursor;
END;
---
DROP PROCEDURE IF EXISTS `sp_send_realtime_message`;
---
CREATE PROCEDURE `sp_send_realtime_message`(IN v_by CHAR(40), IN v_for CHAR(40), IN v_payload MEDIUMTEXT)
MODIFIES SQL DATA
BEGIN
  INSERT INTO realtime_message_queue (via, sent_for, sent_by, payload) VALUES ('admin', v_for, v_by, v_payload);
END;
---
DROP PROCEDURE IF EXISTS `sp_user_delete_realtime_message`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE `sp_user_delete_realtime_message`(IN v_id INT)
MODIFIES SQL DATA
BEGIN
DECLARE v_sent_for VARCHAR(80);
SET v_sent_for = SUBSTRING(CURRENT_MIRANDA_USER(),length('miranda_')+1);
  DELETE FROM realtime_message_queue WHERE id = v_id AND sent_for = v_sent_for;
END;
---
DROP PROCEDURE IF EXISTS `sp_user_send_realtime_message`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE `sp_user_send_realtime_message`(IN v_payload MEDIUMTEXT)
MODIFIES SQL DATA
BEGIN
  DECLARE v_sent_for VARCHAR(80);
  SET v_sent_for = SUBSTRING(CURRENT_MIRANDA_USER(),length('miranda_')+1);
  SELECT COUNT(*) FROM realtime_message_queue WHERE sent_for = v_sent_for INTO @ct;
  IF @ct > 100 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "User has too many messages in queue.";
  END IF;
  INSERT INTO realtime_message_queue (via, sent_for, sent_by, payload) VALUES ('user', v_sent_for,v_sent_for, v_payload);
END;
---
DROP PROCEDURE IF EXISTS `sp_ko_send_realtime_message`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE `sp_ko_send_realtime_message`(IN ticket VARCHAR(64), IN ko_id INTEGER, IN v_payload MEDIUMTEXT)
MODIFIES SQL DATA
BEGIN
  DECLARE v_sent_by VARCHAR(80);
  DECLARE v_sent_for VARCHAR(40);
  SET v_sent_by = SUBSTRING(CURRENT_MIRANDA_USER(),length('miranda_')+1);
  SET v_sent_for = CONCAT('project_',ko_id);
  SELECT COUNT(*) FROM realtime_message_queue WHERE sent_for = v_sent_for INTO @ct;
  IF @ct > 100 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "User has too many messages in queue.";
  END IF;
  INSERT INTO realtime_message_queue (via, sent_for, sent_by, payload, ticket) VALUES ('user', v_sent_for, v_sent_by, v_payload, ticket);
END;
---
DROP PROCEDURE IF EXISTS `sp_send_message_to_processor`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE `sp_send_message_to_processor`(IN v_payload MEDIUMTEXT)
MODIFIES SQL DATA
BEGIN
  DECLARE v_sent_for VARCHAR(80);
  SET v_sent_for = SUBSTRING(CURRENT_MIRANDA_USER(),length('miranda_')+1);
  SELECT COUNT(*) FROM realtime_message_queue WHERE sent_for = v_sent_for INTO @ct;
  IF @ct > 100 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "User has too many messages in queue.";
  END IF;
  INSERT INTO realtime_message_queue (via, sent_for, sent_by, payload) VALUES ('user', "processor", v_sent_for, v_payload);
END;
---
DROP VIEW IF EXISTS `v_gid_from_read_acls`;
---
CREATE ALGORITHM=UNDEFINED DEFINER=`miranda_internal`@`localhost` SQL SECURITY DEFINER VIEW `v_gid_from_read_acls` AS
 SELECT u.id,u.username,a.gid AS gid,a.wob_mid AS wob_mid
 FROM read_acl a
   JOIN group_maps gm ON gm.gid = a.gid
   JOIN users u ON u.ID = gm.uid
 WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED()
---
DROP VIEW IF EXISTS `v_gid_from_write_acls`;
---
CREATE ALGORITHM=UNDEFINED DEFINER=`miranda_internal`@`localhost` SQL SECURITY DEFINER VIEW `v_gid_from_write_acls` AS
 SELECT u.id,u.username,a.gid AS gid,a.wob_mid AS wob_mid
 FROM write_acl a
   JOIN group_maps gm ON gm.gid = a.gid
   JOIN users u ON u.ID = gm.uid
 WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED()
---
DROP PROCEDURE IF EXISTS `sp_read_acl_grant_wob_to_group`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE sp_read_acl_grant_wob_to_group(IN wob_mid INT, IN gid INT)
MODIFIES SQL DATA
BEGIN
  DECLARE uid INT DEFAULT -1;
  DECLARE user_in_group INT DEFAULT 0;
  SET uid = (SELECT id FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED());
  SELECT COUNT(*) INTO user_in_group FROM group_maps WHERE uid = uid AND gid = gid;
  IF user_in_group > 0 THEN
    INSERT INTO read_acl (wob_mid, gid, oid) VALUES (wob_mid, gid, uid);
  END IF;
END;
---
DROP PROCEDURE IF EXISTS `sp_write_acl_grant_wob_to_group`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE sp_write_acl_grant_wob_to_group(IN wob_mid INT, IN gid INT)
MODIFIES SQL DATA
BEGIN
  DECLARE uid INT DEFAULT -1;
  DECLARE user_in_group INT DEFAULT 0;
  SET uid = (SELECT id FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED());
  SELECT COUNT(*) INTO user_in_group FROM group_maps WHERE uid = uid AND gid = gid;
  IF user_in_group > 0 THEN
    INSERT INTO write_acl (wob_mid, gid, oid) VALUES (wob_mid, gid, uid);
  END IF;
END;
---
DROP VIEW IF EXISTS v_secrets;
---
CREATE DEFINER = miranda_internal@localhost VIEW `v_secrets` AS SELECT s.id,s.`key`, s.`value`, s.last_updated, s.created_at FROM secrets s INNER JOIN users u ON u.id = s.user_id WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED();
---
DROP PROCEDURE IF EXISTS `sp_write_secret`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE `sp_write_secret`(IN v_key VARCHAR(255), IN v_value TEXT)
MODIFIES SQL DATA
BEGIN
  DECLARE uid INT DEFAULT -1;
  SET uid = (SELECT id FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED());
  INSERT INTO secrets (`key`, `value`, user_id) VALUES (v_key, v_value, uid) ON DUPLICATE KEY UPDATE `value` = v_value;
END;
---
DROP PROCEDURE IF EXISTS `sp_delete_secret`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE `sp_delete_secret`(IN v_key VARCHAR(255))
MODIFIES SQL DATA
BEGIN
  DECLARE uid INT DEFAULT -1;
  SET uid = (SELECT id FROM users WHERE username = CURRENT_MIRANDA_USER_UNPREFIXED());
  DELETE FROM secrets WHERE `key` = v_key and user_id = uid;
END;
---
DROP VIEW IF EXISTS v_vault;
---
CREATE DEFINER = miranda_internal@localhost VIEW `v_vault` AS
SELECT
  v.id,
  v.created_at,
  v.updated_at,
  v.deleted_at,
  v.name,
  v.owner_org_id,
  v.max_storage,
  v.storage_used,
  v.access_key_id,
  v.secret_access_key
FROM vault v
JOIN organization o ON o.id = v.owner_org_id
JOIN users u ON u.organization_id = o.id
WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED();
---
DROP PROCEDURE IF EXISTS `sp_admin_grant_credits`;
---
CREATE PROCEDURE `sp_admin_grant_credits`(IN to_org_id INT, IN amount DECIMAL(36,18), IN statement VARCHAR(255))
SQL SECURITY INVOKER
MODIFIES SQL DATA
BEGIN
  INSERT INTO credit_transactions (initiator_user_id, from_organization_id, to_organization_id, amount, statement) VALUES (-1, -1, to_org_id, amount, statement);
  UPDATE organization SET credits = credits + amount WHERE id = to_org_id;
END;
---
DROP PROCEDURE IF EXISTS `sp_admin_transact_credits`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_admin_transact_credits`(IN from_user_id INT, IN to_user_id INT, IN amount DECIMAL(36,18), IN statement VARCHAR(255))
MODIFIES SQL DATA
BEGIN
  DECLARE caller VARCHAR(128);
  DECLARE user_org_id INT;
  DECLARE balance DECIMAL(36,18);
  DECLARE to_org_id INT;

  SET caller = CURRENT_MIRANDA_USER();
  IF caller NOT IN ('miranda_webadmin', 'miranda_ScGzWz_4xTrOgin-', 'miranda_cJUBFnQ-fwV9WCqX') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Unauthorized: caller is not permitted to execute this procedure.";
  END IF;

  IF amount <= 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Amount must be greater than 0.";
  END IF;

  SELECT o.credits, o.id INTO balance, user_org_id FROM users u LEFT JOIN organization o ON o.id = u.organization_id WHERE u.id = from_user_id;

  IF user_org_id IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "User does not have an organization.";
  END IF;

  IF to_user_id = -1 THEN
    SET to_org_id = -1;
  ELSE
    SELECT organization_id INTO to_org_id FROM users WHERE id = to_user_id;

    IF to_org_id IS NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = "Recipient user does not exist or does not have an organization.";
    END IF;
  END IF;

  IF amount > balance THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Insufficient credits.";
  END IF;

  UPDATE organization SET credits = credits - amount WHERE id = user_org_id;

  INSERT INTO credit_transactions (initiator_user_id, from_organization_id, to_organization_id, amount, statement) VALUES (from_user_id, user_org_id, to_org_id, amount, statement);

  IF to_org_id <> -1 THEN
    UPDATE organization SET credits = credits + amount WHERE id = to_org_id;
  END IF;
END;
---
DROP PROCEDURE IF EXISTS `sp_transact_credits`;
---
CREATE DEFINER = miranda_internal@localhost PROCEDURE `sp_transact_credits`(IN to_user_id INT, IN amount DECIMAL(36,18), IN statement VARCHAR(255))
MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(40);
  DECLARE user_org_id INT;
  DECLARE balance DECIMAL(36,18);
  DECLARE user_id INT;
  DECLARE to_org_id INT;
  SET db_user = CURRENT_MIRANDA_USER_UNPREFIXED();

  IF amount <= 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Amount must be greater than 0.";
  END IF;

  IF amount > 10000 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Amount must be less than 10000 per transaction.";
  END IF;
  
  SELECT u.id, o.credits, o.id INTO user_id, balance, user_org_id FROM users u LEFT JOIN organization o ON o.id = u.organization_id WHERE u.username = db_user;

  IF user_org_id IS NULL THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "User does not have an organization.";
  END IF;

  SELECT organization_id INTO to_org_id FROM users WHERE id = to_user_id;

  -- IF to_org_id IS NULL THEN
  --   SIGNAL SQLSTATE '45000'
  --     SET MESSAGE_TEXT = "Recipient user does not exist or does not have an organization.";
  -- END IF;

  IF amount > balance THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Insufficient credits.";
  END IF;

  UPDATE organization SET credits = credits - amount WHERE id = user_org_id;

  INSERT INTO credit_transactions (initiator_user_id, from_organization_id, to_organization_id, amount, statement) VALUES (user_id, user_org_id, to_org_id, amount, statement);

  IF to_org_id <> -1 THEN
    UPDATE organization SET credits = credits + amount WHERE id = to_org_id;
  END IF;
END;
---
DROP VIEW IF EXISTS v_organization_transactions;
---
CREATE OR REPLACE VIEW v_organization_transactions AS
(
    WITH user_org AS (
        SELECT u.organization_id 
        FROM v_user vu
        JOIN users u ON u.id = vu.id
    )
    SELECT 
        ct.*,
        fromOrg.name as from_organization_name,
        toOrg.name as to_organization_name,
        initiator.username as initiator_username
    FROM credit_transactions ct
    CROSS JOIN user_org
    INNER JOIN users initiator ON ct.initiator_user_id = initiator.id
    INNER JOIN organization fromOrg ON ct.from_organization_id = fromOrg.id
    LEFT JOIN organization toOrg ON ct.to_organization_id = toOrg.id
    WHERE ct.from_organization_id = user_org.organization_id
       OR ct.to_organization_id = user_org.organization_id
);
---
DROP VIEW IF EXISTS v_popularity_index;
---
CREATE OR REPLACE VIEW v_popularity_index AS
(
    SELECT p.id, p.popularity, m.name
    FROM popularity_index p
    INNER JOIN v_metadata m ON m.id = p.id
)

---
DROP VIEW IF EXISTS v_groups;
---
CREATE OR REPLACE VIEW v_groups AS
(
    SELECT g.id, g.name, g.icon, g.is_public, g.members_can_invite, g.is_org_managed
    FROM user_groups g
    WHERE g.is_public = 1
    UNION
    SELECT g.id, g.name, g.icon, g.is_public, g.members_can_invite, g.is_org_managed
    FROM user_groups g
    INNER JOIN group_maps gm ON gm.gid = g.id
    INNER JOIN users u ON u.id = gm.uid
    WHERE u.username = CURRENT_MIRANDA_USER_UNPREFIXED()
)
---
DROP VIEW IF EXISTS v_group_members;
---
CREATE OR REPLACE VIEW v_group_members AS
(
    SELECT DISTINCT g.id as gid, u.id, ud.first_name, ud.last_name, ud.email, ud.industry, ud.role, ud.avatar
    FROM users_details ud
    INNER JOIN users u ON u.id = ud.user_id
    INNER JOIN group_maps gm ON gm.uid = u.id
    INNER JOIN user_groups g ON g.id = gm.gid
    WHERE (
            g.is_public = 1
            OR EXISTS (
                SELECT 1
                FROM group_maps gm_self
                INNER JOIN users u_self ON u_self.id = gm_self.uid
                WHERE gm_self.gid = g.id
                    AND u_self.username = CURRENT_MIRANDA_USER_UNPREFIXED()
            )
          )
      AND g.id <> 1
)
---
DROP VIEW IF EXISTS v_node_positions;
---
CREATE DEFINER=`miranda_internal`@`localhost` VIEW `v_node_positions` AS
    SELECT n.id, n.project_id, n.metadata_id, n.x, n.y, n.collapsed_attributes
      FROM miranda_web.designer_nodes n
      INNER JOIN v_metadata m ON m.id = n.metadata_id
      WHERE m.Deleted = 0;
---
DROP PROCEDURE IF EXISTS `sp_upsert_node_position`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_upsert_node_position`(
    IN p_project_id INT,
    IN p_metadata_id INT,
    IN p_x INT,
    IN p_y INT
)
    MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(64);
  DECLARE has_access BOOLEAN DEFAULT 0;
  DECLARE node_user VARCHAR(48) DEFAULT '_FIELD_UNUSED_';

  SET db_user = CURRENT_MIRANDA_USER_UNPREFIXED();

  -- Ensure caller can modify the target node position
  WITH owned (mid) AS (
         SELECT m.id
           FROM metadata m
           INNER JOIN users u ON m.created_by_id = u.id
          WHERE u.username = db_user
            AND m.id = p_metadata_id
       ),
       acl_groups (mid) AS (
         SELECT m.id
           FROM metadata m
           INNER JOIN write_acl a ON a.wob_mid = m.id
           INNER JOIN group_maps g ON g.gid = a.gid
           INNER JOIN users u ON u.id = g.uid
          WHERE u.username = db_user
            AND m.id = p_metadata_id
       )
  SELECT COUNT(*) > 0
    INTO has_access
    FROM (
      SELECT owned.mid AS mid FROM owned
      UNION
      SELECT acl_groups.mid AS mid FROM acl_groups
    ) perms;

  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Parameter metadata_id is invalid or user doesn't have write access to this object.";
  END IF;

  INSERT INTO miranda_web.designer_nodes (project_id, metadata_id, user, x, y, collapsed_attributes)
  VALUES (p_project_id, p_metadata_id, node_user, p_x, p_y, JSON_ARRAY())
  ON DUPLICATE KEY UPDATE x = VALUES(x), y = VALUES(y);
END;
---
DROP PROCEDURE IF EXISTS `sp_upsert_node_control`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_upsert_node_control`(
    IN p_project_id INT,
    IN p_metadata_id INT,
    IN p_control_name VARCHAR(64),
    IN p_w INT,
    IN p_h INT
)
    MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(64);
  DECLARE has_access BOOLEAN DEFAULT 0;
  DECLARE node_user VARCHAR(48) DEFAULT '_FIELD_UNUSED_';

  IF p_control_name IS NULL OR CHAR_LENGTH(TRIM(p_control_name)) = 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Parameter control_name must be provided.";
  END IF;

  SET db_user = CURRENT_MIRANDA_USER_UNPREFIXED();

  -- Ensure caller can modify the target node control
  WITH owned (mid) AS (
         SELECT m.id
           FROM metadata m
           INNER JOIN users u ON m.created_by_id = u.id
          WHERE u.username = db_user
            AND m.id = p_metadata_id
       ),
       acl_groups (mid) AS (
         SELECT m.id
           FROM metadata m
           INNER JOIN write_acl a ON a.wob_mid = m.id
           INNER JOIN group_maps g ON g.gid = a.gid
           INNER JOIN users u ON u.id = g.uid
          WHERE u.username = db_user
            AND m.id = p_metadata_id
       )
  SELECT COUNT(*) > 0
    INTO has_access
    FROM (
      SELECT owned.mid AS mid FROM owned
      UNION
      SELECT acl_groups.mid AS mid FROM acl_groups
    ) perms;

  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Parameter metadata_id is invalid or user doesn't have write access to this object.";
  END IF;

  INSERT INTO miranda_web.designer_sizes (project_id, metadata_id, control_name, user, w, h)
  VALUES (p_project_id, p_metadata_id, p_control_name, node_user, p_w, p_h)
  ON DUPLICATE KEY UPDATE w = VALUES(w), h = VALUES(h);
END;
---
DROP PROCEDURE IF EXISTS `sp_upsert_collapsed_attributes`;
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_upsert_collapsed_attributes`(
    IN p_project_id INT,
    IN p_metadata_id INT,
    IN p_collapsed_attributes JSON
)
    MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(64);
  DECLARE has_access BOOLEAN DEFAULT 0;
  DECLARE node_user VARCHAR(48) DEFAULT '_FIELD_UNUSED_';
  DECLARE v_collapsed JSON;

  SET db_user = CURRENT_MIRANDA_USER_UNPREFIXED();
  SET v_collapsed = IFNULL(p_collapsed_attributes, JSON_ARRAY());

  -- Ensure caller can modify the target node
  WITH owned (mid) AS (
         SELECT m.id
           FROM metadata m
           INNER JOIN users u ON m.created_by_id = u.id
          WHERE u.username = db_user
            AND m.id = p_metadata_id
       ),
       acl_groups (mid) AS (
         SELECT m.id
           FROM metadata m
           INNER JOIN write_acl a ON a.wob_mid = m.id
           INNER JOIN group_maps g ON g.gid = a.gid
           INNER JOIN users u ON u.id = g.uid
          WHERE u.username = db_user
            AND m.id = p_metadata_id
       )
  SELECT COUNT(*) > 0
    INTO has_access
    FROM (
      SELECT owned.mid AS mid FROM owned
      UNION
      SELECT acl_groups.mid AS mid FROM acl_groups
    ) perms;

  IF has_access <> 1 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = "Parameter metadata_id is invalid or user doesn't have write access to this object.";
  END IF;

  INSERT INTO miranda_web.designer_nodes (project_id, metadata_id, user, collapsed_attributes)
  VALUES (p_project_id, p_metadata_id, node_user, v_collapsed)
  ON DUPLICATE KEY UPDATE collapsed_attributes = VALUES(collapsed_attributes);
END;
