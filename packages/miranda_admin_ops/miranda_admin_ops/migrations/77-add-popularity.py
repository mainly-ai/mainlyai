# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if not utilities.table_exists(utilities.admin_sc, 'popularity_index'):
	with utilities.admin_sc.connect() as con:
		with con.cursor() as cur:
			cur.execute("""
				CREATE TABLE popularity_index (
					id INT PRIMARY KEY REFERENCES metadata(id) ON DELETE CASCADE,
					popularity FLOAT NOT NULL DEFAULT 0.0
				)
			""")
			con.commit()
			cur.close()
	con.close()

