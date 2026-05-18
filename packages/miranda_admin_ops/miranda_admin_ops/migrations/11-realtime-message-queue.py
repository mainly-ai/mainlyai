# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

from utilities import *

upgrade = False

print ("Using db config: ", admin_sc.db_config)
if not table_exists(admin_sc, "realtime_message_queue"):
  with admin_sc.connect() as con:
    with con.cursor() as cur:
      cur.execute("""CREATE TABLE IF NOT EXISTS `realtime_message_queue` (
                      id INT PRIMARY KEY AUTO_INCREMENT,
                      sent_by VARCHAR(40),
                      sent_for VARCHAR(40),
                      payload VARCHAR(15360), /* ENGINE=MEMORY does not support JSON */
                      created_at TIMESTAMP(2) default CURRENT_TIMESTAMP(2)
                    ) ENGINE=MEMORY""")
      con.commit()
      cur.close()

from mirmod import miranda
admin_sc = miranda.create_security_context(auth_from_config=True)
setup_sps(admin_sc)
recreate_views(admin_sc)
