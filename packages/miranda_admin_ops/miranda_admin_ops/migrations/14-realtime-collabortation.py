# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

with utilities.admin_sc.connect() as con:
  with con.cursor() as cur:
    sql = """
      CREATE TABLE IF NOT EXISTS miranda_web.realtime_room_membership (
        user_id INT NOT NULL,
        room VARCHAR(40) NOT NULL,
        last_seen_at TIMESTAMP(2) NOT NULL DEFAULT CURRENT_TIMESTAMP(2),
        PRIMARY KEY (user_id, room),
        FOREIGN KEY (user_id)
            REFERENCES miranda.users(id)
            ON DELETE CASCADE
      ) ENGINE=MEMORY
    """
    print(sql)
    cur.execute(sql)
    con.commit()

  with con.cursor() as cur:
    sql = """
      CREATE TABLE IF NOT EXISTS miranda_web.realtime_room_chat (
        id INT AUTO_INCREMENT,
        user_id INT NOT NULL,
        room VARCHAR(40) NOT NULL,
        content TEXT NOT NULL,
        sent_at TIMESTAMP(2) NOT NULL DEFAULT CURRENT_TIMESTAMP(2),
        PRIMARY KEY (id),
        FOREIGN KEY (user_id)
            REFERENCES miranda.users(id)
            ON DELETE CASCADE
      )
    """
    print(sql)
    cur.execute(sql)
    con.commit()

utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)