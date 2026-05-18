# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

# Drop and recreate the foreign key constraint on metadata_id with ON DELETE CASCADE
if utilities.table_exists(utilities.admin_sc, 'docker_image'):
    with utilities.admin_sc.connect() as con:
        with con.cursor() as cur:
            cur.execute("ALTER TABLE docker_image DROP FOREIGN KEY docker_image_ibfk_1")
            print("Dropped foreign key docker_image_ibfk_1 from docker_image")
            cur.execute(
                "ALTER TABLE docker_image ADD CONSTRAINT docker_image_ibfk_1 FOREIGN KEY (metadata_id) REFERENCES metadata(ID) ON DELETE CASCADE"
            )
            print("Added ON DELETE CASCADE to docker_image.metadata_id foreign key") 