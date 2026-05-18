# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

with utilities.admin_sc.connect() as conn:
	with conn.cursor() as cursor:
		cursor.execute("""
DELETE FROM miranda_web.designer_nodes
WHERE id IN (
    SELECT id
    FROM (
        SELECT id, 
               ROW_NUMBER() OVER (PARTITION BY project_id, metadata_id ORDER BY id DESC) as rn
        FROM miranda_web.designer_nodes
    ) as ranked
    WHERE rn > 1
);
		""")
		conn.commit()

		# Add unique key constraint to designer_nodes table for more stable updates
		cursor.execute("""
			ALTER TABLE miranda_web.designer_nodes 
			ADD UNIQUE KEY `project_metadata_key` (`project_id`, `metadata_id`, `user`);
		""")
		conn.commit()
