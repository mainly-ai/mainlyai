-- SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
-- SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
--
-- SPDX-License-Identifier: GPL-2.0-only

CREATE TABLE IF NOT EXISTS miranda_web.designer_nodes (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  project_id INTEGER NOT NULL,
  metadata_id INTEGER NOT NULL,
  user VARCHAR(48) NOT NULL,
  x INTEGER DEFAULT 0,
  y INTEGER DEFAULT 0,
  collapsed_attributes JSON
)
