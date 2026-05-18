# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

from utilities import *

upgrade = False

print ("Using db config: ", admin_sc.db_config)

c = count_columns(admin_sc, "knowledge_object")
if c <=5 :
  print ("Upgrading table 'knowledge_object'...")
  add_column(admin_sc, "knowledge_object", "deployed_image", "varchar(255)")
  add_column(admin_sc, "knowledge_object", "compute_resource_id", "int")
  upgrade = True
  print ("  Done")
if c <=6:
  print ("Upgrading table 'knowledge_object'...")
  add_column(admin_sc, "knowledge_object", "origin_project_id", "INTEGER DEFAULT -1")
  upgrade = True
  print ("  Done")

c = count_columns(admin_sc, "storage")
if c <= 6:
  print ("Upgrading table 'storage' 1 (2)...")
  add_column(admin_sc, "storage", "load_url", "varchar(255)")
  add_column(admin_sc, "storage", "store_url", "varchar(255)")
  add_column(admin_sc, "storage", "mount_point", "varchar(255)")
  upgrade = True
  print ("  Done")

if c<=9:
  print ("Upgrading table 'storage' 2 (2)...")
  add_column(admin_sc, "storage", "storage", "longblob")
  upgrade = True
  print ("  Done")

c = count_columns(admin_sc, "docker_job")
if c <= 12:
  if str(get_column_data_type(admin_sc, "docker_job", "logs")).upper() == "TEXT":
    print ("Upgrading table 'docker_job'...")
    change_column(admin_sc, "docker_job", "logs", "LONGTEXT")
    upgrade = True
    print ("  Done")
if c <= 13:
  print ("Upgrading table 'docker_job'...")
  add_column(admin_sc, "docker_job", "message_id", "INTEGER")
  add_column(admin_sc, "docker_job", "tag", "INTEGER")
  add_index(admin_sc, "docker_job", "tag")
  upgrade = True
  print ("  Done")

c = count_columns(admin_sc, "compute_resources")
if c <= 16:
  print ("1. Upgrading table 'compute_resources'...")
  add_column(admin_sc, "compute_resources", "error_count", "INTEGER DEFAULT 0")
  add_column(admin_sc, "compute_resources", "last_error", "DATETIME DEFAULT NULL")
  add_column(admin_sc, "compute_resources", "is_up", "BOOLEAN DEFAULT FALSE")
  upgrade = True
  print ("  Done")
if c <= 19:
  print ("2. Upgrading table 'compute_resources'...")
  add_column(admin_sc, "compute_resources", "last_up", "DATETIME DEFAULT NULL")
  upgrade = True
  print ("  Done")
if c<=20:
  print ("3. Upgrading table 'compute_resources'...")
  add_column(admin_sc, "compute_resources", "registered_as_known_host", "BOOLEAN DEFAULT FALSE")
  upgrade = True
  print ("  Done")

if not table_exists(admin_sc,"deployment"):
  print ("Creating table 'delopment'...")
  create_table(admin_sc, "deployment")
  upgrade = True
  print ("  Done")

if get_column_column_type(admin_sc, 'deployment', 'workflow_state') != bytes("enum('UNDEPLOYED','DEPLOYING','FAILED','DEPLOYED','STOPPING','STOPPED')", encoding='ascii'):
  print ("Upgrading table 'deployment' workflow_state column...")
  change_column(admin_sc, 'deployment', 'workflow_state', "enum('UNDEPLOYED','DEPLOYING','FAILED','DEPLOYED','STOPPING','STOPPED')")
  upgrade = True
  print ("  Done")

if 'DEPLOYMENT' not in get_column_column_type(admin_sc, 'edges', 'src_type').decode("utf-8") :
  print ("Upgrading table 'edges' src_type column...")
  change_column(admin_sc, 'edges', 'src_type', get_column_column_type(admin_sc, 'edges', 'src_type').decode("utf-8") [:-1] + ",'DEPLOYMENT')")
  upgrade = True
  print ("  Done")

if 'DEPLOYMENT' not in get_column_column_type(admin_sc, 'edges', 'dest_type').decode("utf-8") :
  print ("Upgrading table 'edges' dest_type column...")
  change_column(admin_sc, 'edges', 'dest_type', get_column_column_type(admin_sc, 'edges', 'dest_type').decode("utf-8") [:-1] + ",'DEPLOYMENT')")
  upgrade = True
  print ("  Done")

if has_column(admin_sc, 'deployment', 'proxy_url'):
  print ("Removing column 'proxy_url' from table 'deployment'...")
  remove_column(admin_sc, 'deployment', 'proxy_url')
  upgrade = True
  print ("  Done")

if not has_column(admin_sc, 'deployment', 'pod_id'):
  print ("Adding column 'pod_id' to table 'deployment'...")
  add_column(admin_sc, 'deployment', 'pod_id', "varchar(26)")
  upgrade = True
  print ("  Done")

if not has_column(admin_sc, 'wob_message_queue', 'target'):
  print ("Adding column 'target' to table 'wob_message_queue'...")
  add_column(admin_sc, 'wob_message_queue', 'target', "varchar(40)")
  upgrade = True
  print ("  Done")

if not table_exists(admin_sc, "tag2metadata"):
  print ("Creating table 'tag2metadata'...")
  create_table(admin_sc, "tag2metadata")
  upgrade = True
  print ("  Done")

if not has_column(admin_sc, 'tag2metadata', 'user_id'):
  print ("Adding column 'user_id' to table 'tag2metadata'...")
  add_column(admin_sc, 'tag2metadata', 'user_id', "INT")
  upgrade = True
  print ("  Done")

if upgrade:
  print ("Rewriting SPs and VIEWs...")
  setup_sps(admin_sc)
  print ("  Done")

admin_sc.close()
