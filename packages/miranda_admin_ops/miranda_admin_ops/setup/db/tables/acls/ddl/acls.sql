-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS `read_acl` (
  `oid` int DEFAULT NULL,
  `gid` int DEFAULT NULL,
  `wob_mid` int DEFAULT NULL,
  UNIQUE KEY `groupid` (`gid`,`wob_mid`),
  FOREIGN KEY (oid)
        REFERENCES users(ID)
        ON DELETE CASCADE,
  FOREIGN KEY (wob_mid)
        REFERENCES metadata(id)
        ON DELETE CASCADE
)
---
CREATE TABLE IF NOT EXISTS `write_acl` (
  `oid` int DEFAULT NULL,
  `gid` int DEFAULT NULL,
  `wob_mid` int DEFAULT NULL,
  UNIQUE KEY `kgroupid` (`gid`,`wob_mid`),
  FOREIGN KEY (oid)
        REFERENCES users(ID)
        ON DELETE CASCADE,
  FOREIGN KEY (wob_mid)
        REFERENCES metadata(id)
        ON DELETE CASCADE
)
---
CREATE TABLE IF NOT EXISTS `execute_acl` (
  `oid` int DEFAULT NULL,
  `gid` int DEFAULT NULL,
  `wob_mid` int DEFAULT NULL,
  UNIQUE KEY `kgroupid` (`gid`,`wob_mid`),
  FOREIGN KEY (oid)
        REFERENCES users(ID)
        ON DELETE CASCADE,
  FOREIGN KEY (wob_mid)
        REFERENCES metadata(id)
        ON DELETE CASCADE
)
---
CREATE TABLE IF NOT EXISTS `user_groups` (
    `id` int NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `oid`int NOT NULL,
    `is_public` boolean NOT NULL DEFAULT 0,
    `members_can_invite` boolean NOT NULL DEFAULT 0,
    `is_org_managed` boolean NOT NULL DEFAULT 0,
    `name` varchar(40) NOT NULL,
    `icon` varchar(255) NOT NULL DEFAULT 'https://mainly-web-assets.s3.eu-north-1.amazonaws.com/avatars/group_default.png'
)
---
CREATE TABLE IF NOT EXISTS `group_maps` (
  `uid` int DEFAULT NULL,
  `gid` int DEFAULT NULL,
  UNIQUE KEY `kgroupid` (`gid`,`uid`),
  FOREIGN KEY (gid)
    REFERENCES user_groups(`id`)
    ON DELETE CASCADE,
  FOREIGN KEY (uid)
    REFERENCES users(`id`)
    ON DELETE CASCADE
)
---
DELETE FROM user_groups WHERE `id` = 1;
---
INSERT INTO user_groups (`id`, `oid`, `name`, `is_public`, `members_can_invite`) VALUES (1, -1, 'EVERYONE', 1, 1);

