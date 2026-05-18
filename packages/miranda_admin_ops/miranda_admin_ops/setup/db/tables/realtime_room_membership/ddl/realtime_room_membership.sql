-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS miranda_web.realtime_room_membership (
  user_id INT NOT NULL,
  room VARCHAR(40) NOT NULL,
  last_seen_at TIMESTAMP(2) NOT NULL DEFAULT CURRENT_TIMESTAMP(2),
  PRIMARY KEY (user_id, room),
  FOREIGN KEY (user_id)
      REFERENCES miranda.users(id)
      ON DELETE CASCADE
) ENGINE=MEMORY