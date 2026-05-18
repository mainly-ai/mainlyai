-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS miranda_web.realtime_room_chat (
  id INT AUTO_INCREMENT,
  user_id INT NOT NULL,
  room VARCHAR(40) NOT NULL,
  content TEXT NOT NULL,
  metadata JSON DEFAULT NULL,
  sent_at TIMESTAMP(2) NOT NULL DEFAULT CURRENT_TIMESTAMP(2),
  PRIMARY KEY (id),
  FOREIGN KEY (user_id)
      REFERENCES miranda.users(id)
      ON DELETE CASCADE
)