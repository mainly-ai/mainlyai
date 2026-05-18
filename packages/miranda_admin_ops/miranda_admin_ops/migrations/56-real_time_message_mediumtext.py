# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

if utilities.has_column(utilities.admin_sc,"realtime_message_queue","payload") == True:    
  with utilities.admin_sc.connect() as con:
    with con.cursor() as cur:
      print ("Modifying column payload to type MEDIUMTEXT in table realtime_message_queue")
      cur.execute("ALTER TABLE realtime_message_queue MODIFY COLUMN `payload` MEDIUMTEXT")
      con.commit()

  utilities.setup_sps(utilities.admin_sc)
  utilities.recreate_views(utilities.admin_sc)
else:
  print("No column payload in table realtime_message_queue.")