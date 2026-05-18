# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

with utilities.admin_sc.connect() as con:
    with con.cursor() as cur:
        cur.execute("ALTER TABLE metadata ADD INDEX idx_metadata_deleted_id (Deleted, ID)")
        print("Index idx_metadata_deleted_id added to metadata table")
        cur.execute("ALTER TABLE metadata ADD INDEX idx_metadata_last_updated (Last_updated)")
        print("Index idx_metadata_last_updated added to metadata table")
        cur.execute("ALTER TABLE metadata ADD INDEX idx_metadata_cloned_from_id (cloned_from_id)")
        print("Index idx_metadata_cloned_from_id added to metadata table")
        cur.execute("ALTER TABLE metadata ADD INDEX idx_metadata_created_by_id (Created_by_id)")
