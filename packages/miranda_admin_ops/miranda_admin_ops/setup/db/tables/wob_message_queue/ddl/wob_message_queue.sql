-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS wob_message_queue
(
  id INT PRIMARY KEY AUTO_INCREMENT,
  user VARCHAR(20),
  target VARCHAR(40),
  wob_type VARCHAR(20),
  wob_id INT,
  `priority` INT,
  payload JSON,
  status INT default '0',
  read_ts TIMESTAMP(2),
  write_ts TIMESTAMP(2) default CURRENT_TIMESTAMP(2)
)