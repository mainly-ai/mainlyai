-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS `cr_group_map` (
  `GROUP_ID` int NOT NULL,
  `CR_ID` int NOT NULL,
  PRIMARY KEY (`GROUP_ID`,`CR_ID`)
);