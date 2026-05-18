# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
from mirmod import miranda

with utilities.admin_sc.connect() as con:
  with con.cursor(dictionary=True) as cur:
    cur.execute("SELECT k.metadata_id, m.Name, m.Description, m.Created_by_id, u.organization_id FROM miranda.knowledge_object k LEFT JOIN miranda.metadata m ON k.metadata_id = m.id LEFT JOIN miranda.users u ON m.Created_by_id = u.id")
    all_kos = cur.fetchall()

    print(all_kos)

    to_bind = {}

    for ko in all_kos:
      cur.execute("SELECT count(*) FROM miranda.edges WHERE src_type = 'PROJECT' and dest_id = %s", (ko["metadata_id"],))
      count = cur.fetchone()["count(*)"]
      if count == 0:
        print("adding ko %s to_bind" % ko["metadata_id"])
        if ko["Created_by_id"] not in to_bind:
          to_bind[ko["Created_by_id"]] = []
        to_bind[ko["Created_by_id"]].append(ko)
      else:
        print("Project already exists for ko %s" % ko["metadata_id"])
    
    for uid in to_bind:
      print("Adding project for user %s" % uid)
      cur.execute("INSERT INTO miranda.metadata (Created_by_id, Name, Description) VALUES (%s, %s, %s)", (uid, "Migrated Graphs", "Graphs that were created before Projects were introduced"))
      cur.execute("SELECT LAST_INSERT_ID()")
      project_metaid = cur.fetchone()["LAST_INSERT_ID()"]
      cur.execute("INSERT INTO miranda.project (metadata_id, organization_id, stripe_sub_id) VALUES (%s, %s, %s)", (project_metaid, ko["organization_id"], ""))
      for ko in to_bind[uid]:
        cur.execute("INSERT INTO miranda.edges (src_type, src_id, dest_type, dest_id) VALUES ('PROJECT', %s, 'KNOWLEDGE_OBJECT', %s)", (project_metaid, ko["metadata_id"],))
      con.commit()
