-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS miranda_web.designer_sizes (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  project_id INTEGER NOT NULL,
  metadata_id INTEGER NOT NULL,
  control_name VARCHAR(64) NOT NULL,
  user VARCHAR(48) NOT NULL,
  h INTEGER DEFAULT 0,
  w INTEGER DEFAULT 0,

  UNIQUE KEY (project_id, metadata_id, control_name, user)
)