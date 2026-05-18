# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities
if utilities.table_exists(utilities.admin_sc, 'docker_image'):
    print('Table docker_image already exists. Skipping.')
else:
    print('Creating table docker_image.')
    sql ="""
    CREATE TABLE docker_image (
        id INT AUTO_INCREMENT PRIMARY KEY,
        URI VARCHAR(255),
        properties TEXT,
        image_state ENUM ('NEW','BUILDING','PUSHING','MODIFIED','ERROR','READY'),
        image_size INT,
        base_image_URI VARCHAR(255),
        is_base_image BOOLEAN,
        base_image_id INT,
        metadata_id INT,
        FOREIGN KEY (metadata_id) REFERENCES metadata(id)
    )"""
    with utilities.admin_sc.connect() as con:
        with con.cursor() as cursor:
          cursor.execute(sql)
        
    print('Table docker_image created.')