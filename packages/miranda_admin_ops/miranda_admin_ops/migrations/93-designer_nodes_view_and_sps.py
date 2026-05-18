# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

from utilities import *

with admin_sc.connect() as conn:
    with conn.cursor() as cur:
        print("GRANT ALL ON miranda_web.designer_nodes TO miranda_internal@localhost")
        cur.execute(
            "GRANT ALL ON miranda_web.designer_nodes TO miranda_internal@localhost"
        )
        conn.commit()
        cur.close()
    conn.close()
