-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS `realtime_message_queue` (
  id INT PRIMARY KEY AUTO_INCREMENT,
  via ENUM('admin', 'user') NOT NULL DEFAULT 'admin',
  sent_by VARCHAR(40),
  sent_for VARCHAR(40),
  ticket VARCHAR(64) DEFAULT NULL,
  payload MEDIUMTEXT,
  created_at TIMESTAMP(2) default CURRENT_TIMESTAMP(2)
)