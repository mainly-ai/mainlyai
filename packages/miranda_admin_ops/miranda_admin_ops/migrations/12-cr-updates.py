# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import utilities

sql = """alter table miranda.compute_resources
    modify host varchar(128) not null;

alter table miranda.compute_resources
    drop column port;

alter table miranda.compute_resources
    drop column user;

alter table miranda.compute_resources
    drop column ssh_key;

alter table miranda.compute_resources
    drop column docker_env_vars;

alter table miranda.compute_resources
    drop column docker_sudo;

alter table miranda.compute_resources
    drop column docker_network;

alter table miranda.compute_resources
    drop column has_firewall;

alter table miranda.compute_resources
    drop column firewall_is_configured;

alter table miranda.compute_resources
    add base_docker_image int null;

alter table miranda.compute_resources
    drop column registered_as_known_host;

create index index_name
    on miranda.compute_resources (host)
    comment 'host';

drop index miranda_user_id on miranda.compute_resources;

alter table miranda.compute_resources
    drop column miranda_user_id;
    
alter table miranda.knowledge_object
    drop column compute_resource_id;

alter table miranda.knowledge_object
    drop column deployed_image;


alter table miranda.edges add column attributes json after etl_id;
    """

with utilities.admin_sc.connect() as con:
  with con.cursor() as cur:
    print(sql)
    cur.execute(sql, multi=True)
    con.commit()

with utilities.admin_sc.connect() as con:
  for user in utilities.get_all_miranda_users(con):
    with con.cursor() as cur:
      sql = "GRANT SELECT ON miranda.v_gid_from_read_acls TO %s@`%`"
      sql_data = (user[0],)
      cur.execute(sql, sql_data)
      con.commit()
      sql = "GRANT SELECT ON miranda.v_gid_from_write_acls TO %s@`%`"
      sql_data = (user[0],)
      cur.execute(sql, sql_data)
      con.commit()

utilities.setup_sps(utilities.admin_sc)
utilities.recreate_views(utilities.admin_sc)
