-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS `realtime_message_ticket` (
  ticket VARCHAR(64) PRIMARY KEY,
  ko_id INT NOT NULL,
  creator_user_id INT NOT NULL,
  created_at TIMESTAMP(2) default CURRENT_TIMESTAMP(2)
) 