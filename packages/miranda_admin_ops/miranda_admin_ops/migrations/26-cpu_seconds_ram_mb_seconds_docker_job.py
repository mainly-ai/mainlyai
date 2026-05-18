# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.has_column(utilities.admin_sc, "docker_job", "cpu_seconds"):
	exit(0)
with utilities.admin_sc.connect() as con:
	with con.cursor() as cur:
		cur.execute("alter table miranda.docker_job add column `cpu_seconds` float(12, 3) DEFAULT '0'")
		cur.execute("alter table miranda.docker_job add column `ram_gb_seconds` float(12, 5) DEFAULT '0'")
		cur.execute("alter table miranda.docker_job add column `net_rx_gb` float(12, 5) DEFAULT '0'")
		cur.execute("alter table miranda.docker_job add column `net_tx_gb` float(12, 5) DEFAULT '0'")
		con.commit()

utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)