#
# Copyright (c) 2023,2024,2025 MainlyAI - contact@mainly.ai
#
import hashlib
from secrets import token_urlsafe
import secrets
import mysql.connector
from mysql.connector import errorcode
import json
import glob
import dill as pickle

import yaml
import random
import string
import os
import asyncssh
from pathlib import Path

from mirmod.workflow_objects import (
    Docker_image,
    Project,
    Compute_resource_group,
    Compute_policy,
    Deployment,
    Knowledge_object,
    Code_block,
    Docker_job,
)

from mirmod import miranda
from mirmod.miranda import create_security_context, find_children
from mirmod.security.security_context import (
    _create_db_cred,
    get_config,
    Security_context,
)
from mirmod.utils.logger import logger
from mirmod import (
    get_all_edge_labels,
    get_all_wob_classes,
    is_valid_object_label,
    object_to_table,
    table_to_object,
)

pickle.settings["recurse"] = True
pickle.load_types(pickleable=True, unpickleable=True)

mod_path = Path(__file__).parent
system_path = Path(__file__).parent.parent
tables_relative_path = "setup/db/tables"
sp_relative_path = "setup/db"


def _load_object(sc: Security_context, type: str, mid: int, user_id=-1):
    """
    Loads a workflow object from database and returns it.
    Args:
        sc: Security context
        type: The workflow object type. ie MODEL, STORAGE, DATASTREAM etc
        mid: The metadata ID

    """
    orm_obj = {
        "KNOWLEDGE_OBJECT": Knowledge_object,
        "CODE": Code_block,
        "DOCKER_JOB": Docker_job,
        "DEPLOYMENT": Deployment,
        "COMPUTE_POLICY": Compute_policy,
        "PROJECT": Project,
        "COMPUTE_RESOURCE_GROUP": Compute_resource_group,
        "DOCKER_IMAGE": Docker_image,
    }
    # print ("DEBUG: Loading object {} with id = {}".format(type,id))
    obj = orm_obj[type](sc, metadata_id=mid, user_id=user_id)
    return obj


def _create_acl(
    cursor, sc: Security_context, priv: str, obj_type: str, metadata_id: int
):
    sql = "INSERT INTO acls (user_id, privilege, object_type, metadata_id, db_user) VALUES (%s,%s,%s,%s,CURRENT_MIRANDA_USER())"
    sql_data = (sc.id, priv, obj_type, metadata_id)
    cursor.execute(sql, sql_data)
    return True


def make_password_hash(salt, pwd):
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), bytes.fromhex(salt), 5000)
    if dk:
        return dk.hex()
    else:
        logger.error("error making password hash")


def _get_all_table_names():
    """
    Returns a list of all the tables in the Datamodel
    """
    return [
        "cr_group_map",
        "acls",
        "group_maps",
        "user_groups",
        "read_acl",
        "write_acl",
        "execute_acl",
        "compute_policy",
        "docker_images",
        "docker_image",
        "docker_job",
        "compute_resources",
        "compute_resource_group",
        "wob_message_queue",
        "dashboard",
        "uiview",
        "actuator",
        "deployment",
        "tag2metadata",
        "knowledge_object",
        "datastream",
        "etl_process",
        "model",
        "code",
        "simulator",
        "edges",
        "storage",
        "storage_policy",
        "metadata",
        "users_details",
        "users",
        "object_store",
        "gri_category",
        "gri_disclosure",
        "gri_requirement",
        "gri_topic",
        "gri_vocabulary",
        "sdg_goal",
        "sdg_gri",
        "sdg_target",
        "secrets",
        "project",
        "billing",
        "credit_transactions",
        "vault_limited_access_token",
        "vault_object",
        "vault",
    ]


def _get_table_dependencies(config, table):
    try:
        return config["tables"][table]["depends_on"]
    except KeyError:
        return ""


def _get_random_string(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    random.seed = os.urandom(1024)
    return "".join(random.choice(chars) for i in range(length))


def create_user(
    sc: Security_context,
    username="testuser",
    password=None,
    email=None,
    first_name="",
    last_name="",
    phone="",
    industry="",
    role="",
    account_status="",
    org_id=None,
):
    """
    Creates a miranda user along with the corresponding miranda DB user and assign
    it the the default roles. This function should be executed with the highest
    security access.
    """
    user_id = -1
    try:
        con = sc.connect()
        cursor = con.cursor()
        if not password:
            account_status = "FORCE_CHANGE_PASSWORD"
            password = _get_random_string()
        config = get_config()
        con2 = mysql.connector.connect(**config)
        cursor2 = con2.cursor()
        sql = "CREATE USER %s@`%` IDENTIFIED BY %s"
        db_username, db_password = _create_db_cred(username, password)
        sql_data = (db_username, db_password)
        cursor2.execute(sql, sql_data)
        con2.commit()
        logger.info("Created user {}".format(username))
        sql = "GRANT mainlyai_user_role TO %s@`%`"
        sql_data = (db_username,)
        cursor2.execute(sql, sql_data)
        con2.commit()
        logger.info("Granted mainlyai_user_role to user {}".format(username))
        sql = "SET DEFAULT ROLE mainlyai_user_role TO %s@`%`"
        sql_data = (db_username,)
        cursor2.execute(sql, sql_data)
        con2.commit()
        ########################

        sql = "SELECT id FROM users WHERE username = %s"
        sql_data = (username,)
        cursor.execute(sql, sql_data)
        found = False
        for r in cursor:
            logger.info("Found user {}".format(username))
            found = True
            user_id = r[0]

        if not found:
            sql = "INSERT INTO users (username, `auth`, salt, organization_id) VALUES (%s, %s, %s, %s)"
            salt = os.urandom(32).hex()
            hashed_password = make_password_hash(salt, password)
            sql_data = (
                username,
                hashed_password,
                salt,
                org_id if org_id is not None else -1,
            )
            cursor.execute(sql, sql_data)
            con.commit()
            user_id = cursor.lastrowid
            _create_user_details(
                con,
                user_id,
                email=email,
                account_status=account_status,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                industry=industry,
                role=role,
            )
            if org_id is None:
                org_id = _create_organzation(con, f"{username}'s org", user_id)
                sql = "UPDATE users SET organization_id = %s WHERE id = %s"
                sql_data = (org_id, user_id)
                cursor.execute(sql, sql_data)
                con.commit()  # Commit the organization_id update
            logger.info("Created user {}".format(username))

        if user_id != -1:
            sql = "INSERT INTO group_maps (uid,gid) VALUES (%s, 1)"
            data = (user_id,)
            cursor.execute(sql, data)
            con.commit()

            # Add user to organization team if org_id is provided
            if org_id is not None and org_id != -1:
                # Get the organization's team group ID
                sql = "SELECT org_team_group_id, subscribed FROM organization WHERE id = %s LIMIT 1"
                cursor.execute(sql, (org_id,))
                result = cursor.fetchone()
                if result and result[0] is not None:
                    team_group_id = result[0]
                    # Add user to the organization's team
                    admin_assign_user_to_group(None, user_id, team_group_id)
                    logger.info(
                        "Added user {} to organization team (group {})".format(
                            username, team_group_id
                        )
                    )

                if result and result[1] is not None:
                    subscribed = bool(result[1])
                    paid_user_group_id = os.environ.get("PAID_USER_GROUP_ID", None)
                    if subscribed and paid_user_group_id:
                        admin_assign_user_to_group(
                            None, user_id, int(paid_user_group_id)
                        )

        cursor.close()
        con.close()
        con2.close()
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)
    assert user_id != -1, "create_user failed to create user {}".format(username)
    return db_username, db_password


class Miranda_user_update_error(Exception):
    pass


# TODO: implement support for db_secret
def update_user(sc: Security_context, current_username="testuser", **kwargs):
    _assert_legal_username(current_username)
    con = sc.connect()
    user_id = -1
    with con.cursor() as cur:
        sql = "SELECT id FROM users WHERE username = %s"
        sql_data = (current_username,)
        cur.execute(sql, sql_data)
        for rs in cur:
            user_id = int(rs[0])
    if user_id == -1:
        # No such user
        raise Miranda_user_update_error
    password = None
    with con.cursor() as cur:
        sql = "UPDATE users u INNER JOIN users_details d ON d.user_id = u.id "
        sql_sets = []
        if "password" in kwargs.keys():
            _assert_legal_password(kwargs["password"])
            password = kwargs["password"]
            salt = os.urandom(32).hex()
            hashed_password = make_password_hash(salt, kwargs["password"])
            kwargs["password"] = hashed_password
            kwargs["salt"] = salt
        for k in kwargs.keys():
            if k == "username":
                k = "u.username"
                _assert_legal_username(kwargs["username"])
            elif k == "password":
                k = "u.auth"
            elif k == "salt":
                k = "u.salt"
            elif k == "mfa_secret":
                assert False, (
                    "MFA secret is not supported for miranda users. Update webuser instead"
                )
            elif k == "db_secret":
                assert False, (
                    "DB secret is not supported for miranda users. Update webuser instead"
                )
            elif k == "login_time":
                assert False, (
                    "login_time is not supported for miranda users. Update webuser instead"
                )
            else:
                k = "d." + k
            sql_sets.append(f"{k} = %s")
        sql += "SET " + ",".join(sql_sets)
        sql += f" WHERE u.id = {user_id}"
        vals = [v for v in kwargs.values()]
        sql_data = tuple(vals)
        # print (f"DEBUG: {sql},{sql_data}")
        cur.execute(sql, sql_data)
        con.commit()
        if password != None:
            db_username, db_password = _create_db_cred(current_username, password)
            sql = "SET PASSWORD FOR %s = %s"
            sql_data = (db_username, db_password)
            with con.cursor() as cur:
                cur.execute(sql, sql_data)
            con.commit()
        if "username" in kwargs.keys() and kwargs["username"] != current_username:
            sql = "RENAME USER %s TO %s"
            cur_db_username, _ = _create_db_cred(current_username, "")
            new_db_username, _ = _create_db_cred(kwargs["username"], "")
            sql_data = (cur_db_username, new_db_username)
            with con.cursor() as cur:
                cur.execute(sql, sql_data)
        con.commit()


def get_all_users(sc: Security_context, sharing_with_user=None):
    """
    Returns all users from DB
    """
    try:
        if sharing_with_user is None:
            con = sc.connect()
            cursor = con.cursor(dictionary=True)
            sql = """
            SELECT
                u.username,
                d.first_name,
                d.last_name,
                d.email,
                d.phone,
                d.industry,
                d.role,
                d.account_status,
                d.avatar,
                u.id as id
            FROM miranda.users u
            LEFT JOIN miranda.users_details d ON u.id = d.user_id
            LEFT JOIN miranda_web.web_users w ON w.username = u.username;
            """
            cursor.execute(sql)
            d = cursor.fetchall()
            cursor.close()
            con.close()
            logger.info("Got all users")
            return d
        else:
            users = []
            sql = """WITH all_groups (gid) AS (SELECT DISTINCT gid FROM group_maps gm WHERE gm.uid=%s AND gm.gid <> 1)
             SELECT DISTINCT u.id, u.username,
                d.first_name,
                d.last_name,
                d.email,
                d.phone,
                d.industry,
                d.role,
                d.account_status,
                d.avatar,
                FROM users u INNER JOIN group_maps gm ON gm.uid=u.id INNER JOIN all_groups ag ON ag.gid=gm.gid INNER JOIN users_details d ON d.user_id=u.id
                INNER JOIN miranda_web.web_users w ON w.username = u.username"""
            sql_data = (sharing_with_user,)
            # with sc.connect() as con:
            con = sc.connect()
            with con.cursor(dictionary=True) as cur:
                cur.execute(sql, sql_data)
                users = cur.fetchall()
            return users
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
        # print(err.errno)
        # print(err.sqlstate)
        # print(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


def get_user(sc: Security_context, username, con=None, id=None):
    """
    Returns all info for a particular user from DB
    """
    try:
        con = sc.connect()
        cursor = con.cursor(dictionary=True)
        sql = """
        SELECT
            u.username,
            d.first_name,
            d.last_name,
            d.email,
            d.phone,
            d.industry,
            d.role,
            d.account_status,
            d.avatar,
            u.id as id,
            u.organization_id as organization_id,
            d.consented
        FROM miranda.users u
        LEFT JOIN miranda.users_details d ON u.id = d.user_id
        LEFT JOIN miranda_web.web_users w ON w.username = u.username
        """
        if id is not None:
            sql += "WHERE u.id = %s"
            sql_data = (id,)
        else:
            sql += "WHERE u.username = %s"
            sql_data = (username,)
        cursor.execute(sql, sql_data)
        rs = cursor.fetchone()
        cursor.close()
        con.close()
        logger.info("Got user {}".format(username))
        return rs
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
        # print(err.errno)
        # print(err.sqlstate)
        # print(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


class IllegalUsername(Exception):
    def __init__(self, mesg):
        self.message = mesg


class IllegalPassword(Exception):
    def __init__(self, mesg):
        self.message = mesg


def _assert_legal_username(username):
    if len(username) > 20:
        raise IllegalUsername("Username too long (20 max)")
    for c in username:
        if not (c.isalnum() or c in "_-"):
            raise IllegalUsername("Illegal characters detected.")


def _assert_legal_password(password):
    if len(password) < 5:
        raise IllegalPassword("Password too short.")
    # for c in password:
    #    if not (c.isalnum() or c in "!#¤%&/()=?,._-+*£$[];:"):
    #        raise IllegalPassword("Illegal characters detected.")


def remove_user(sc: Security_context, username):
    """
    Removes a miranda user from the users table. Also drop the corresponding DB user.
    In order to drop the user the security context must be able to provide the necessary privilege level.
    """
    # Don't remove youself
    assert sc.application_user != username
    _assert_legal_username(username)
    try:
        con = sc.connect()
        cursor = con.cursor()
        sql = "DELETE u,d FROM users u INNER JOIN users_details d ON d.user_id=u.id WHERE u.username = %s"
        sql_data = (username,)
        cursor.execute(sql, sql_data)
        con.commit()
        logger.info("Removed user {}".format(username))
        con.commit()
        #
        # TODO Because AWS doesn't give us full admin access we need to use the AWS account
        # for dropping users and granting them privileges
        #
        config = get_config()
        con2 = mysql.connector.connect(**config)
        cursor2 = con2.cursor()

        sql = "DROP USER IF EXISTS %s"
        db_username, _ = _create_db_cred(username, "")
        sql_data = (db_username,)
        cursor2.execute(sql, sql_data)
        logger.info("Dropped user {}".format(username))
        con2.commit()
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
        # print(err.errno)
        # print(err.sqlstate)
        # print(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


def get_inconsistent_users(sc):
    """
    Get inconsistent users from the DB.
    Inconsistent users is a user who does not have a record across
    mysql.user, miranda.users and miranda_web.web_users tables.
    """
    try:
        con = sc.connect()
        cursor = con.cursor()
        sql = """
        select SUBSTRING(user FROM (LOCATE('_',user)+1)) as username from mysql.user where user like 'miranda_%'
        UNION
        select username from miranda.users
        UNION
        select username from miranda_web.web_users;
        """
        cursor.execute(sql)
        rs = cursor.fetchall()
        for user in rs:
            integrity = user_integrity(sc, user[0])
            if integrity == "miranda: 1 mysql: 1 web: 1":
                pass
            else:
                yield user[0]
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


def remove_inconsistent_users(sc):
    """
    Remove inconsistent users from the DB.
    Inconsistent users is a users who does not have a record across
    mysql.user, miranda.users and miranda_web.web_users tables.
    """

    users = get_inconsistent_users(sc)
    try:
        for u in users:
            # TODO: ['webadmin', 'webtest', 'internal', 'testuser'] are excluded from integrity control.
            #  This might change in the future.
            if u in ["webadmin", "webtest", "internal", "testuser"]:
                logger.info(
                    "User ['webadmin', 'webtest', 'internal', 'testuser'] will not be removed."
                )
            else:
                logger.info("User {} is inconsistent, should be removed".format(u))
                remove_user(sc, u)
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


def user_integrity(sc, u):
    con = sc.connect()
    cur = con.cursor()
    sql = "SELECT count(*) as c FROM miranda.users WHERE username = %s"
    sql_data = (u,)
    cur.execute(sql, sql_data)
    miranda_users = 0
    for r in cur:
        miranda_users = r[0]
    database_users = 0
    sql = "SELECT count(*) as c FROM mysql.user WHERE user = %s"
    sql_data = ("miranda_" + u,)
    rs = cur.execute(sql, sql_data)
    for r in cur:
        database_users = r[0]
    web_users = 0
    sql = "SELECT count(*) as c FROM miranda_web.web_users WHERE username = %s"
    sql_data = (u,)
    rs = cur.execute(sql, sql_data)
    for r in cur:
        web_users = r[0]
    cur.close()
    return "miranda: {} mysql: {} web: {}".format(
        miranda_users, database_users, web_users
    )


def _create_user_details(
    con,
    user_id,
    email="",
    account_status="",
    first_name="",
    last_name="",
    phone="",
    industry="",
    role="",
    consented=False,
):
    try:
        cursor = con.cursor()
        sql = "INSERT INTO users_details (user_id, email, account_status, first_name, last_name, phone, industry, role, consented) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        sql_data = (
            user_id,
            email,
            account_status,
            first_name,
            last_name,
            phone,
            industry,
            role,
            consented,
        )
        cursor.execute(sql, sql_data)
        con.commit()
        logger.info("Created user details for user {}".format(user_id))
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
        # print(err.errno)
        # print(err.sqlstate)
        # print(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


def drop_database(config, without_confirmation=False):
    if "SKIP_DROP_DB" in os.environ:
        return

    if not without_confirmation:
        y = input("Drop the tables Y/N > ")
        if y != "Y" and y != "y":
            logger.info("Operation cancelled.")
            print("Operation cancelled.")
            return

    # print("Dropping all miranda tables.")

    try:
        with mysql.connector.connect(**config) as cnx:
            print("Connected to the database.")
            # TODO check integrity of the DB
            tables = []
            for t in _get_all_table_names():
                # TODO: quick hack to get things working again. we should use a dependency graph resolver here probably
                if t != "metadata" and t != "users" and t != "users_details":
                    tables.append("DROP TABLE IF EXISTS " + t)

            cur = cnx.cursor()
            cur.execute("DROP TABLE IF EXISTS edges")
            cur.execute("DROP TABLE IF EXISTS miranda_web.web_users")
            cur.execute("DROP TABLE IF EXISTS miranda_web.designer_nodes")
            cur.execute("DROP TABLE IF EXISTS miranda_web.designer_edge_segments")
            cur.execute("DROP TABLE IF EXISTS miranda_web.credentials")
            cur.execute("DROP TABLE IF EXISTS miranda_web.realtime_room_chat")
            cur.execute("DROP TABLE IF EXISTS miranda_web.realtime_room_membership")
            cnx.commit()
            for sql in tables:
                print(sql)
                cur.execute(sql)
            cur.execute("DROP TABLE IF EXISTS miranda.organization")
            cur.execute("DROP TABLE IF EXISTS miranda.metadata")
            cur.execute("DROP TABLE IF EXISTS miranda.users_details")
            cur.execute("DROP TABLE IF EXISTS miranda.users")
            cnx.commit()
            logger.info("Dropped all miranda tables.")
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logger.error("Something is wrong with your user name or password")
            print("Something is wrong with your user name or password")
            exit(-1)
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            logger.error("Database does not exist")
            print("Database does not exist")
            exit(-1)
        else:
            print(err)
            exit(-1)


def _get_table_def(_type):
    definitions = []
    path = str((mod_path / tables_relative_path).resolve())
    with open(str(path + f"/config.yml")) as f:
        conf = yaml.load(f, Loader=yaml.FullLoader)
    for filename in glob.iglob(path + f"/**/{_type}/*.sql", recursive=True):
        table_name = Path(filename).stem
        dependencies = _get_table_dependencies(conf, table_name)
        definitions.append((table_name, dependencies, filename))

    return sorted(definitions, reverse=True)


def insert_into_database(config):
    cnx = mysql.connector.connect(**config)
    cur = cnx.cursor()
    insert_statements = _get_table_def("insert")
    for table, dependencies, insert_st in insert_statements:
        with open(insert_st, encoding="utf8") as sql_file:
            for result in cur.execute(sql_file.read(), multi=True):
                pass
            cnx.commit()


def create_user_role_if_not_exists():
    sc = miranda.create_security_context(auth_from_config=True)
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = "CREATE ROLE IF NOT EXISTS mainlyai_user_role"
        cur.execute(sql)
        con.commit()

    ensure_userspace_view_grants(sc)

    # Grant role so all users
    sql = "SELECT user FROM mysql.user WHERE user LIKE 'miranda_%'"
    with con.cursor() as cur:
        cur.execute(sql)
        users = cur.fetchall()
        for rs in users:
            if rs[0] == "miranda_internal":
                continue
            sql = f"GRANT mainlyai_user_role TO '{rs[0]}'"
            print(sql)
            cur.execute(sql)
            con.commit()
            cur.fetchall()


def ensure_userspace_view_grants(sc: Security_context):
    con = sc.connect()
    with con.cursor() as cur:
        sql = """
        GRANT SELECT ON miranda.v_edges TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_metadata TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_tags_per_ko TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_tags_per_wob TO mainlyai_user_role;
        GRANT SELECT ON miranda.vtag2metadata TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_user TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_tokens TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_miranda_logs TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_gid_from_read_acls TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_secrets TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_gid_from_read_acls TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_gid_from_write_acls TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_organization_transactions TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_user_detail TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_popularity_index TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_groups TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_group_members TO mainlyai_user_role;
        GRANT SELECT ON miranda.v_node_positions TO mainlyai_user_role;
        GRANT APPLICATION_PASSWORD_ADMIN ON *.* TO mainlyai_user_role;
        GRANT EXECUTE ON miranda.* TO mainlyai_user_role;"""
        for table in miranda.get_all_edge_labels():
            sql += f"GRANT SELECT ON miranda.v_{table.lower()} TO mainlyai_user_role;"
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            print(stmt)
            try:
                cur.execute(stmt)
                con.commit()
                cur.fetchall()
            except Exception as e:
                print(f"Failed to grant {stmt}")
                print(e)


def setup_database(config):
    tables_to_be_created = []
    try:
        cnx = mysql.connector.connect(**config)
        cur = cnx.cursor()
        table_definitions = _get_table_def("ddl")
        for table, dependencies, ddl in table_definitions:
            if table == "metadata":
                tables_to_be_created.insert(0, table)
            else:
                tables_to_be_created.append(table)
        print("Tables to be created: {}".format(tables_to_be_created))
        # Create tables from the DDL:s
        while tables_to_be_created:
            for table, dependencies, ddl in table_definitions:
                f = open(ddl, "r")
                sql = f.read()
                if table in tables_to_be_created and dependencies == "":
                    logger.info(
                        "Table: {} does not have any dependencies, create table.".format(
                            table
                        )
                    )
                    for s in sql.split("---"):
                        print(s)
                        cur.execute(s)
                    tables_to_be_created.remove(table)
                # Table with dependencies - CHECK
                elif table in tables_to_be_created and dependencies != "":
                    satisfied = True
                    logger.info(
                        "Table: {} has dependencies, check if they are satisfied.".format(
                            table
                        )
                    )
                    for d in dependencies:
                        if d in tables_to_be_created:
                            logger.info("Dependencies not satisfied!")
                            satisfied = False
                    # Dependencies satisfied - SAFE TO CREATE
                    if satisfied:
                        logger.info("Create table: {}".format(table))
                        for s in sql.split("---"):
                            cur.execute(s)
                        tables_to_be_created.remove(table)
            cnx.commit()
        logger.info("Creating miranda_web schema.")
        cur.execute("CREATE SCHEMA IF NOT EXISTS miranda_web")
        logger.info("Base tables created.")

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logger.error("Something is wrong with your user name or password")
            exit(-1)
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            logger.error("Database does not exist")
            exit(-1)
        else:
            logger.error(err)
            exit(-1)

    logger.info("Setting up mandatory miranda_internal@localhost account.")
    with cnx.cursor() as cur:
        cur.execute("DROP USER IF EXISTS miranda_internal@localhost")
        cur.execute(
            "CREATE USER miranda_internal@localhost IDENTIFIED BY '{miranda_pw}'"
        )
        cur.execute("GRANT ALL ON miranda.* TO miranda_internal@localhost")
        cur.execute(
            "GRANT ALL ON miranda_web.designer_nodes TO miranda_internal@localhost"
        )
        cur.execute("GRANT SELECT ON mysql.default_roles TO miranda_internal@localhost")
        cur.execute("DROP FUNCTION IF EXISTS CURRENT_MIRANDA_USER")
        cur.execute("""CREATE FUNCTION CURRENT_MIRANDA_USER() RETURNS CHAR(128)
DETERMINISTIC
BEGIN
  DECLARE miranda_user CHAR(128);
  SELECT role_name INTO miranda_user FROM information_schema.APPLICABLE_ROLES where IS_DEFAULT = 'YES' AND role_name LIKE 'miranda_%' limit 1;
  IF miranda_user IS NULL THEN
    SET miranda_user = USER();
  END IF;
  RETURN TRIM('`' from REGEXP_REPLACE(miranda_user,'@.*',''));
END;""")
        cnx.commit()
    logger.info("Setting up views and SPs.")
    sc = create_security_context("nobody", "nopass")
    for ob_class in get_all_wob_classes():
        ob = ob_class(sc, -1)
        ob.create_view(cnx)
        ob.create_sp(cnx, object_to_table)
        ob.make_update_sp(cnx)
    with open(str((mod_path / sp_relative_path).resolve()) + "/sp.sql") as fh:
        with cnx.cursor() as cursor:
            file = fh.read()
            for sql in file.split("---"):
                cursor.execute(sql)
                for rs in cursor:
                    pass
            cnx.commit()
    cnx.close()

    create_user_role_if_not_exists()

    # grant the user role to all existing users.
    sc = miranda.create_security_context(auth_from_config=True)
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = "SELECT user,host FROM mysql.user WHERE left(user,8) = 'miranda_'"
        cur.execute(sql)
        all_users = cur.fetchall()
        for user in all_users:
            sql = "GRANT mainlyai_user_role TO '{}'@'{}'".format(user[0], user[1])
            print(sql)
            cur.execute(sql)
            sql = "SET DEFAULT ROLE mainlyai_user_role TO '{}'@'{}'".format(
                user[0], user[1]
            )
            print(sql)
            cur.execute(sql)
        con.commit()


def hard_delete(sc: Security_context):
    try:
        sql = "DELETE FROM metadata m WHERE m.deleted = 1"
        con = sc.connect()
        cur = con.cursor()
        cur.execute(sql)
        con.commit()
        affected = cur.rowcount
        cur.close()
        logger.info("{} objects deleted.".format(affected))
        return affected
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
        # print(err.errno)
        # print(err.sqlstate)
        # print(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


def queue_message(
    admin_sc: Security_context, user: str, wob, payload="", priority=10, target=None
):
    assert target is not None
    assert admin_sc.require_admin == True
    try:
        con = admin_sc.connect()
        wob_type = object_to_table(wob)
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO wob_message_queue (user, wob_type, wob_id, payload, `priority`, target) VALUES (%s, %s, %s, %s, %s, %s)",
                (user, wob_type, wob.id, payload, priority, target),
            )
            con.commit()
        con.close()
        return True
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)
        return False


def get_message_queue(sc: Security_context, user, target=None):
    """
    Get all messages from the message queue but don't remove them.
    """
    assert target is not None
    assert sc.require_admin == True
    try:
        con = sc.connect()
        with con.cursor(dictionary=True) as cur:
            cur.execute(
                "SELECT id, wob_type, wob_id, payload, `priority` FROM wob_message_queue WHERE user = %s AND target = %s AND status = 0 ORDER BY `priority` DESC",
                (user, target),
            )
            rs = cur.fetchall()
            for r in rs:
                yield r
        con.close()
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)
        return False


def update_message(sc: Security_context, jobid, priority=None, payload=None):
    try:
        con = sc.connect()
        params = []
        set_stmt = "SET"
        if priority is not None:
            set_stmt += " `priority` = %s"
            params.append(priority)
        if payload is not None:
            if len(set_stmt) > 3:
                set_stmt += ", "
            set_stmt += "payload = %s"
            params.append(payload)
        params.append(jobid)
        with con.cursor() as cur:
            cur.execute(
                "UPDATE wob_message_queue " + set_stmt + " WHERE id = %s", params
            )
            con.commit()
        con.close()
        return True
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)
    return False


def delete_message(sc: Security_context, jobid):
    try:
        con = sc.connect()
        with con.cursor() as cur:
            cur.execute("DELETE FROM wob_message_queue WHERE id = %s", (jobid,))
            con.commit()
        con.close()
        return True
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)
    return False


class No_more_messages_error(Exception):
    pass


def get_message(sc: Security_context, user, target=None):
    """
    Fetch the next message from the message queue for a particular user. This method requires admin
    """
    assert target is not None
    assert sc.require_admin == True
    try:
        con = sc.connect()
        with con.cursor(dictionary=True) as cur:
            if user == "%":
                cur.callproc(f"get_wob_message", (target,))
            else:
                cur.callproc(f"get_wob_message_for_user", (user, target))
            con.commit()
            for result in cur.stored_results():
                for row in result:
                    return row
            raise No_more_messages_error
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)
        return None


class InvalidSSHKey(Exception):
    def __init__(self, message):
        self.message = message
        logger.error(message)


async def verify_ssh_host(user, host, port, key):
    try:
        client_keys = [asyncssh.import_private_key(key)]
    except Exception as e:
        raise InvalidSSHKey(f"Invalid SSH key: {key}")
    async with asyncssh.connect(
        host=host, port=port, username=user, client_keys=client_keys
    ) as conn:
        try:
            cmd = f"ls /dev/null"
            result = await conn.run(cmd)
        except asyncssh.ProcessError as exc:
            logger.error(str(exc))
            raise exc
        except asyncssh.misc.ProtocolError as exc:
            logger.error(str(exc))
            raise exc


def add_compute_resource(
    admin_sc: Security_context, host: str, hardware_description={}, ssh_key=""
):
    try:
        # with admin_sc.connect() as con:
        con = admin_sc.connect()
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO compute_resources (host, hardware_description, ssh_key) VALUES (%s, %s, %s)",
                (host, json.dumps(hardware_description), ssh_key),
            )
            con.commit()
            last_id = cur.lastrowid
        return last_id
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
        raise (err)
    except mysql.connector.Error as err:
        logger.error(err)
        raise (err)


def get_compute_resource_by_id(admsc: Security_context, id):
    """
    find a compute resource by its id in the compute_resources table and return the result set
    """
    # with admsc.connect() as con:
    con = admsc.connect()
    with con.cursor(dictionary=True) as cur:
        cur.execute("SELECT * FROM compute_resources WHERE id = %s", (id,))
        return cur.fetchone()


def delete_compute_resource(admin_sc: Security_context, id: int):
    try:
        # with admin_sc.connect() as con:
        con = admin_sc.connect()
        with con.cursor() as cur:
            cur.execute("DELETE FROM compute_resources WHERE id = %s", (id,))
            con.commit()
        return False
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
        return True
    except mysql.connector.Error as err:
        logger.error(err)
        return True


def get_compute_resources(admin_sc: Security_context):
    try:
        # with admin_sc.connect() as con:
        con = admin_sc.connect()
        with con.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM compute_resources")
            res = [result for result in cur]
            return res
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)
    return None


def update_compute_resources(admin_sc: Security_context, id: int, fields: dict):
    # Create an SQL update statement based on the fields dictionary
    # The fields dictionary should contain the field names as keys and the new values as values.
    # The id is the id of the compute resource in the compute_resources table.
    # with admin_sc.connect() as con:
    con = admin_sc.connect()
    with con.cursor() as cur:
        sql = "UPDATE compute_resources SET "
        for key in fields.keys():
            sql += key + " = %s, "
        sql = sql[:-2] + " WHERE id = %s"
        cur.execute(sql, (*fields.values(), id))
        con.commit()


def admin_find_any_by_type(type: str):
    """
    Find all objects for a given type
    :param sc: Security Context
    :param type: given type (e.g. datastream, model, etc)
    :return:
    """

    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    sc.require_admin = True
    if not is_valid_object_label(type):
        logger.error(f"Unknown type {type.upper()}")
        raise Exception("ERROR: Unknown type is given: {}".format(type.upper()))
    try:
        # with sc.connect() as con:
        con = sc.connect()
        with con.cursor() as cursor:
            sql = "SELECT id FROM " + type.lower()
            cursor.execute(sql)
            for row in cursor:
                ob = table_to_object(type)(sc, row[0])
                yield ob
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


def admin_find_any_by_id(id: int, type: str):
    """
    Find all objects for a given type
    Args:
        id: id of the object
        type: given type (e.g. datastream, model, etc)

    """

    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    sc.require_admin = True
    if not is_valid_object_label(type):
        logger.error(f"Unknown type {type.upper()}")
        raise Exception("ERROR: Unknown type is given: {}".format(type.upper()))
    try:
        # with sc.connect() as con:
        con = sc.connect()
        with con.cursor() as cursor:
            sql = "SELECT id FROM " + type.lower() + " WHERE id = %s"
            sql_data = (id,)
            cursor.execute(sql, sql_data)
            for row in cursor:
                return table_to_object(type)(sc, row[0])
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


def admin_find_wob_by_outbound_edges(mid: int):
    """
    Finds all objects that are children of the object with the given metadata id that are also shared in the read_acl table with
    the EVERYONE group.
    Args:
        mid : The metadata id of the parent object
    Returns:
        A list of objects that are children of the parent object.
    """
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    sc.require_admin = True
    wobs = []
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = """SELECT e.dest_id,e.dest_type,m.name FROM edges e INNER JOIN metadata m ON m.id=e.dest_id INNER JOIN read_acl ra ON e.dest_id=ra.wob_mid WHERE e.src_id = %s AND ra.gid=1"""
        cur.execute(sql, (mid,))
        for rs in cur:
            wobs.append((table_to_object(rs[1]), rs[0]))
    for wob_class, mid in wobs:
        ob = wob_class(sc, metadata_id=mid)
        yield ob


def admin_find_wob_by_inbound_edges(mid: int):
    """
    Finds all objects that are children of the object with the given metadata id. Note: No access checks performed.
    Args:
        mid : The metadata id of the parent object
    Returns:
        A list of objects that are children of the parent object.
    """
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    sc.require_admin = True
    wobs = []
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = """SELECT e.src_id,e.src_type FROM edges e WHERE e.dest_id = %s"""
        cur.execute(sql, (mid,))
        for rs in cur:
            wobs.append((table_to_object(rs[1]), rs[0]))
    for wob_class, mid in wobs:
        ob = wob_class(sc, metadata_id=mid, user_id=-2)
        if ob.id != -1:
            yield ob


def admin_find_children(mid: int, filter=lambda x: not isinstance(x, Knowledge_object)):
    """
    Finds all objects that are children of the object with the given metadata id.
    Args:
        mid : The metadata id of the parent object
        filter : a lambda expression which skips objects.
    Returns:
        A list of objects that are children of the parent object.
    """
    for ob in [o for o in admin_find_wob_by_outbound_edges(mid)]:
        if filter == None or filter(ob):
            yield ob


def admin_find_wob_by_outbound_edges(mid: int):
    """
    Finds all objects that are children of the object with the given metadata id. NOTE: no access checks performed.
    Args:
        mid : The metadata id of the parent object
    Returns:
        A list of objects that are children of the parent object.
    """
    sc = miranda.create_security_context("admin", auth_from_config=True)
    sc.require_admin = True
    wobs = []
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = """SELECT e.dest_id,e.dest_type FROM edges e WHERE e.src_id = %s"""
        cur.execute(sql, (mid,))
        for rs in cur:
            wobs.append((table_to_object(rs[1]), rs[0]))
    for wob_class, mid in wobs:
        ob = wob_class(sc, metadata_id=mid, user_id=-2)
        if ob.id != -1:
            yield ob


def member_of_group(requester_user_id, gid, admin_sc=None):
    if admin_sc is None:
        sc = miranda.create_security_context("admin", auth_from_config=True)
    else:
        sc = admin_sc
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = """
            SELECT count(*) FROM group_maps gm
            INNER JOIN users u ON u.id=gm.uid
            INNER JOIN user_groups ug ON ug.id=gm.gid
            LEFT JOIN users owners ON owners.id=ug.oid
            WHERE (owners.id=%s OR u.id=%s) and ug.id=%s"""

        cur.execute(sql, (requester_user_id, requester_user_id, gid))
        return cur.fetchone()[0] > 0


def group_is_public(gid, admin_sc=None):
    if admin_sc is None:
        sc = miranda.create_security_context("admin", auth_from_config=True)
    else:
        sc = admin_sc
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = """
        SELECT is_public FROM user_groups WHERE id=%s LIMIT 1"""

        cur.execute(sql, (gid,))
        rs = cur.fetchall()
        if len(rs) == 0:
            return False
        return rs[0][0] == 1


def admin_grant_wob_to_group(
    requesting_user_sc: miranda.Security_context,
    ob,
    gid: int,
    acl: str = "read_acl",
    include_children: bool = False,
    recursive_count: int = 0,
    preview=False,
):
    """
    Assigns the object with the given metadata id to the group with the given gid.
    Args:
        mid : The metadata id of the object to be assigned
        gid : The gid of the group to assign the object to
    Returns:
        Throws exception on error
        A list of aditional children that will be affected.
    """
    mid = ob.metadata_id
    admin_sc = miranda.create_security_context("admin", auth_from_config=True)
    requesting_user_sc.connect()
    requester_user_id = requesting_user_sc.user_id()
    # requesting_user_sc.close()
    assert requester_user_id != -1
    if not has_access(requester_user_id, mid, acl, admin_sc=admin_sc):
        raise ValueError("User does not have access to the object")
    if not member_of_group(
        requester_user_id, gid, admin_sc=admin_sc
    ) and not group_is_public(gid, admin_sc=admin_sc):
        raise ValueError("User is not a member of the group")
    if acl not in ["read_acl", "write_acl", "execute_acl"]:
        raise ValueError("acl must be one of read_acl,write_acl,execute_acl")
    children = []
    change_data = [ob]
    if not preview:
        # with admin_sc.connect() as con:
        con = admin_sc.connect()
        with con.cursor() as cur:
            sql = "INSERT INTO " + acl + " (oid,wob_mid,gid) VALUES (%s,%s,%s)"
            try:
                cur.execute(sql, (requester_user_id, mid, gid))
                con.commit()
            except mysql.connector.IntegrityError:
                pass  # technically failed but we assume it is duplicate and the desired result is alreay in the db.
        con.close()
    if include_children and recursive_count < 4:
        children = [
            o
            for o in find_children(
                requesting_user_sc,
                mid,
                lambda x: not (
                    isinstance(x, Docker_job) or isinstance(x, Compute_resource_group)
                ),
            )
            if o.id != -1
        ]
        # find_children performs the necessary access checks for the user.
        for wob in children:
            # Recurse !
            obs = admin_grant_wob_to_group(
                requesting_user_sc,
                wob,
                gid,
                acl,
                include_children=include_children,
                recursive_count=recursive_count + 1,
                preview=preview,
            )
            for o in obs:
                change_data.append(o)
    # eliminate dups
    change_data = [o[1] for o in list({o.metadata_id: o for o in change_data}.items())]
    return change_data


def is_wob_owner(sc, operating_user_id: int, mid: int):
    # with sc.connect() as con:
    con = sc.connect()
    sql = "SELECT created_by_id FROM metadata WHERE id=%s"
    with con.cursor() as cur:
        cur.execute(sql, (mid,))
        rs = cur.fetchone()
        if rs == None:
            raise ValueError("No such object")
        return int(rs[0]) == operating_user_id


def admin_revoke_group_from_wob(
    operating_user_sc: miranda.Security_context,
    ob,
    gid: int,
    include_children=False,
    recursive_count: int = 0,
    preview=False,
    privilages=["read_acl"],
):
    """
    Removes the object with the given metadata id from the group with the given gid.
    Args:
        ob : Wob object to be removed from the group
        gid : The gid of the group to remove the object from
    Returns:
        Throws exception on error
    """
    mid = ob.metadata_id
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    operating_user_sc.connect()
    operating_user_id = operating_user_sc.user_id()
    assert operating_user_id != -1
    if not is_group_owner(operating_user_id, gid, admin_sc=sc) and not is_wob_owner(
        sc, operating_user_id, mid
    ):
        raise ValueError("User is not owner of group or object")
    children = []
    if recursive_count == 0:
        change_data = [ob]
    else:
        change_data = []
    if not preview:
        # with sc.connect() as con:
        con = sc.connect()
        with con.cursor() as cur:
            for p in privilages:
                if p.lower() in ["read_acl", "write_acl", "execute_acl"]:
                    sql = f"DELETE FROM {p.lower()} WHERE wob_mid = %s AND gid = %s"
                    cur.execute(sql, (mid, gid))
                else:
                    logger.warning(
                        f'Tried to remove "{p.lower()}" from a group, but it is not a valid privilage.'
                    )
            con.commit()
    if include_children and recursive_count < 4:
        children = [o for o in find_children(operating_user_sc, mid) if o.id != -1]
        # find_children performs the necessary access checks for the user.
        for wob in children:
            # Recurse !
            obs = admin_revoke_group_from_wob(
                operating_user_sc, wob, gid, include_children, recursive_count + 1
            )
            for o in obs:
                change_data.append(o)
    return change_data


def is_group_owner(oid: int, gid: int, admin_sc=None):
    """Return True if the user is the owner of group with the given gid."""
    if admin_sc is None:
        sc = miranda.create_security_context("admin", auth_from_config=True)
    else:
        sc = admin_sc
    sc.connect()
    assert sc.require_admin == True
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = "SELECT id FROM user_groups WHERE id=%s AND oid=%s"
        cur.execute(sql, (gid, oid))
        rs = cur.fetchall()
        return cur.rowcount == 1


def can_invite_to_group(operating_uid: int, gid: int):
    """Return True if the user is allowed to invite users to the group with the given gid."""
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    assert sc.require_admin == True
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = """
            SELECT id FROM user_groups WHERE id=%s AND (oid=%s OR is_public=1)
                UNION
            SELECT id FROM group_maps gm INNER JOIN user_groups ug ON ug.id=gm.gid WHERE id=%s AND ug.members_can_invite=1 AND gm.uid=%s
            """
        test_me = sql.format(gid, operating_uid, gid, operating_uid)
        cur.execute(sql, (gid, operating_uid, gid, operating_uid))
        rs = cur.fetchall()
        return cur.rowcount >= 1


def admin_assign_user_to_group(op_sc: Security_context, uid: int, gid: int):
    """
    Assigns the user with the given uid to the group with the given gid.
    Args:
        op_sc : The user performing the operation (or None for admin level access)
        uid : The uid of the user to be assigned
        gid : The gid of the group to assign the user to
    Returns:
        True if the user was assigned to the group, False if the user was already assigned to the group.
    """
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    assert sc.require_admin == True
    if op_sc == None:
        logger.info("Assigning user {} to group {} with admin access".format(uid, gid))
        operating_uid = -1
    else:
        op_sc.connect()
        operating_uid = op_sc.user_id()
    if not can_invite_to_group(operating_uid, gid) and operating_uid != -1:
        raise ValueError("User is not allowed to invite to this group.")
    try:
        # with sc.connect() as con:
        con = sc.connect()
        with con.cursor() as cur:
            try:
                sql = """INSERT INTO group_maps (uid,gid) VALUES (%s,%s)"""
                cur.execute(sql, (uid, gid))
                con.commit()
                return cur.rowcount == 1
            except mysql.connector.IntegrityError:
                return True  # Duplicates are no problems.
    except mysql.connector.IntegrityError as err:
        pass


def admin_remove_user_from_group(op_sc: Security_context, uid: int, gid: int):
    """
    Removes the user with the given uid from the group with the given gid.
    Args:
        op_sc : The user performing the operation (or None for admin level privilege)
        uid : The uid of the user to be removed
        gid : The gid of the group to remove the user from
    Returns:
        True if the user was removed from the group, False if the user was not assigned to the group.
    """
    sc = miranda.create_security_context("admin", auth_from_config=True)
    sc.connect()
    assert sc.require_admin == True
    if op_sc == None:
        logger.info("Removing user {} to group {} with admin access".format(uid, gid))
        operating_uid = -1
    else:
        operating_uid = op_sc.user_id()
    if not is_group_owner(operating_uid, gid) and operating_uid != -1:
        raise ValueError("User is not allowed to invite to this group.")
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = """DELETE FROM group_maps WHERE uid = %s AND gid = %s"""
        cur.execute(sql, (uid, gid))
        con.commit()
        return cur.rowcount == 1


def admin_soft_delete_object(obj):
    """marks object for deletion.
    Args:
        userid : The user iddrop_user
        obj : Any ORM object
    """
    if obj.id == -1:
        return
    try:
        con = obj.sctx.connect()
        with con.cursor(buffered=True) as cur:
            sql = "UPDATE metadata m SET deleted=TRUE WHERE m.id=%s"
            sql_data = (obj.metadata_id,)
            cur.execute(sql, sql_data)
            con.commit()
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


def admin_update_user_group(op_sc: Security_context, group_id: int, **attr):
    """
    Updates the given attribute of the group with the given group id.
    Args:
        op_sc : The user performing the operation or None if this is an admin operation
        group_id : The group id
        attr : The attribute to be updated
    """
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    assert sc.require_admin == True
    if op_sc != None:
        op_sc.connect()
        operating_user_id = op_sc.user_id()
    else:
        operating_user_id = -1
    if not is_group_owner(operating_user_id, group_id) and operating_user_id != -1:
        raise ValueError("User is not allowed to update this group.")
    set_stmts = []
    set_values = []
    for k, v in attr.items():
        set_stmt = f"{k}=%s"
        set_stmts.append(set_stmt)
        set_values.append(v)
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = "UPDATE user_groups SET " + ",".join(set_stmts) + " WHERE id=%s"
        set_values.append(group_id)
        cur.execute(sql, set_values)
        con.commit()


def admin_create_user_group(
    name: str,
    group_owner_id: int = -1,
    is_public: bool = False,
    members_can_invite_others: bool = False,
    icon: str = None,
    is_org_managed: bool = False,
):
    """
    Creates a new user group and return the group id. NOTE: This function does not check if the user is allowed to create a group.
    Args:
        name : The name of the group which should be created
        group_owner_id : The ID of the group owner user.
        is_public: If True, any user on the miranda network can join the group without being invited.
        members_can_invite: If True, members can invite other users to the group.
        is_org_managed: If True, this group is managed by an organization and has special UI restrictions.
    Returns:
        Group id of the newly created group
    """
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    assert sc.require_admin == True
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        if icon is not None:
            sql = """INSERT INTO user_groups (name, oid, is_public, members_can_invite, is_org_managed, icon) VALUES (%s,%s,%s,%s,%s,%s)"""
            cur.execute(
                sql,
                (
                    name,
                    group_owner_id,
                    is_public,
                    members_can_invite_others,
                    is_org_managed,
                    icon,
                ),
            )
        else:
            sql = """INSERT INTO user_groups (name, oid, is_public, members_can_invite, is_org_managed) VALUES (%s,%s,%s,%s,%s)"""
            cur.execute(
                sql,
                (
                    name,
                    group_owner_id,
                    is_public,
                    members_can_invite_others,
                    is_org_managed,
                ),
            )
        lastrowid = cur.lastrowid
        con.commit()
        return lastrowid


def admin_drop_user_group(op_sc: Security_context, id: int):
    """
    Removes the group with the given id
    Args:
        op_sc : The user performing the operation or None if this is an admin operation
        id : The id of the group which should be removed
    Returns:
        Nothing. An exception is raised if there was an error.
    """
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    sc.require_admin = True
    if op_sc != None:
        # This is not performed by an administrator
        assert op_sc.require_admin == False, (
            "This method should not be called with an admin sc. Use None instead."
        )
        op_sc.connect()
        operating_user_id = op_sc.user_id()
    else:
        operating_user_id = -1
    if not is_group_owner(operating_user_id, id) and operating_user_id != -1:
        raise ValueError("User is not allowed to delete this group.")
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        sql = """DELETE FROM user_groups WHERE id=%s"""
        cur.execute(sql, (id,))
        con.commit()


def admin_list_user_groups(user: str = None) -> list[map]:
    """
    Args:
        user : The user name of the user which should be listed. If None, all groups are listed.
    Returns:
        A list of all user groups or all groups per user.
    """
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    assert sc.require_admin == True
    if user == None:
        # with sc.connect() as con:
        con = sc.connect()
        with con.cursor(dictionary=True) as cur:
            sql = """SELECT `id`,`oid`,`is_public`,`members_can_invite`,`name`,`icon` FROM user_groups"""
            cur.execute(sql)
            return cur.fetchall()
    else:
        # with sc.connect() as con:
        con = sc.connect()
        with con.cursor(dictionary=True) as cur:
            groups = []
            sql = """SELECT DISTINCT ug.id,ug.oid,ug.is_public,ug.members_can_invite,ug.name,ug.icon,ug.is_org_managed FROM user_groups ug
                INNER JOIN group_maps gm ON gm.gid=ug.id
                INNER JOIN users u ON u.id=gm.uid
                WHERE u.username=%s
                UNION
                SELECT DISTINCT ug.id,ug.oid,ug.is_public,ug.members_can_invite,ug.name,ug.icon,ug.is_org_managed FROM user_groups ug LEFT JOIN users u ON u.id = ug.oid WHERE ug.is_public=1 OR u.username=%s"""
            cur.execute(sql, (user, user))
            groups = cur.fetchall()
            return groups


def get_acls_given_for_wob(sc: Security_context, user_id, wob_mid):
    """
    Args:
        sc : Security_context
        user_id : User id
        wob_mid : Wob mid
    Returns:
        A list of all acls granted by the given user for a particular wob
    """
    tables = ["read_acl", "write_acl", "execute_acl"]
    ugroups = {}
    sql_data = (wob_mid, user_id)
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor(dictionary=True) as cur:
        for table in tables:
            sql = (
                "SELECT t.gid as gid,g.name as group_name FROM "
                + table
                + " t INNER JOIN user_groups g ON g.id=t.gid WHERE t.wob_mid = %s AND t.oid=%s"
            )
            cur.execute(sql, sql_data)
            id = cur
            for r in cur:
                id = r["group_name"]
                if id not in ugroups:
                    ugroups[id] = []
                ugroups[id].append(table)
    with con.cursor(dictionary=True) as cur:
        sql = "SELECT created_by_id uid FROM metadata WHERE id = %s"
        cur.execute(sql, (wob_mid,))
        d = cur.fetchone()
        if "uid" in d and d["uid"] == user_id:
            ugroups["owner"] = tables
    return ugroups


def get_acls_given_for_wob2(admin_sc: Security_context, user_id, wob_mid):
    """
    Args:
        admin_sc : Security_context
        user_id : User id
        wob_mid : Wob mid
    Returns:
        A list of all acls granted by the given user for a particular wob
    """
    tables = ["read_acl", "write_acl", "execute_acl"]
    ugroups = {}
    orgmgmtmap = {}
    gids = {}
    rs = []
    sql_data = (wob_mid, user_id)
    # with admin_sc.connect() as con:
    con = admin_sc.connect()
    with con.cursor(dictionary=True) as cur:
        for table in tables:
            sql = (
                """SELECT DISTINCT t.gid as gid,g.name AS group_name, g.is_org_managed
                        FROM """
                + table
                + """ t
                        INNER JOIN user_groups g ON g.id=t.gid
                        INNER JOIN group_maps gm ON gm.gid=t.gid
                        WHERE t.wob_mid = %s AND gm.uid=%s"""
            )
            cur.execute(sql, sql_data)
            for r in cur:
                id = r["group_name"]
                if id not in ugroups:
                    ugroups[id] = []
                    gids[id] = r["gid"]
                    orgmgmtmap[id] = r["is_org_managed"] == 1
                ugroups[id].append(table)
    with con.cursor(dictionary=True) as cur:
        sql = "SELECT created_by_id uid FROM metadata WHERE id = %s"
        cur.execute(sql, (wob_mid,))
        d = cur.fetchone()
        if "uid" in d and d["uid"] == user_id:
            ugroups["owner"] = tables
            gids["owner"] = -1
            orgmgmtmap["owner"] = False
    for ug in ugroups.keys():
        rs.append(
            {
                "name": ug,
                "permissions": ugroups[ug],
                "id": gids[ug],
                "is_org_managed": orgmgmtmap[ug],
            }
        )
    return rs


def has_access(uid: int, mid: int, access_type="read_acl", admin_sc=None):
    """
    Args:
        uid : User id
        mid : Wob metadata id
        access_type : The type of access to check. Can be "read_acl", "write_acl" or "execute_acl"
        admin_sc : Reuse security context if you got it.
    Returns:
        True if the user has read access to the object with the given mid.
    """
    if not isinstance(mid, list):
        mid = [mid]
    if access_type not in ["read_acl", "write_acl", "execute_acl"]:
        return False
    # SELECT ug.name,u.username,a.wob_mid
    sql = (
        """SELECT u.id
                FROM group_maps gm
                INNER JOIN user_groups ug ON ug.id=gm.gid
                INNER JOIN """
        + access_type
        + """ a ON a.gid = gm.gid
                INNER JOIN users u on u.id=gm.uid
                WHERE a.wob_mid IN (%s) AND u.id = %s
            UNION
            SELECT u.id
                FROM metadata m INNER JOIN users u ON u.id=m.created_by_id
                WHERE m.id IN (%s) AND u.id = %s"""
    )
    comma_sep_list = ",".join([str(m) for m in mid])
    sql_data = (comma_sep_list, uid, comma_sep_list, uid)
    if admin_sc == None:
        sc = miranda.create_security_context(auth_from_config=True)
        sc.require_admin = True
    else:
        sc = admin_sc

    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        cur.execute(sql, sql_data)
        rs = cur.fetchall()
        print(rs)
        return cur.rowcount > 0


def admin_get_users_per_group(gid: int, no_crg_users=False):
    """
    Returns:
        A list of all users per group.
    """
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    assert sc.require_admin == True
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor(dictionary=True) as cur:
        if no_crg_users:
            sql = """
            WITH CRG_USERS AS (
              SELECT DISTINCT u.id FROM users u JOIN compute_resource_group crg ON crg.operator_user_id=u.id
            )
            SELECT ug.id,u.username,u.id,ud.first_name,ud.last_name,ud.avatar,ud.industry,ud.role,ud.email FROM user_groups ug
                INNER JOIN group_maps gm ON gm.gid=ug.id
                INNER JOIN users u ON u.id=gm.uid
                INNER JOIN users_details ud ON u.id=ud.user_id
                WHERE ug.id=%s AND u.id NOT IN (SELECT * FROM CRG_USERS)"""
        else:
            sql = """SELECT ug.id,u.username,u.id,ud.first_name,ud.last_name,ud.avatar,ud.industry,ud.role,ud.email FROM user_groups ug
                INNER JOIN group_maps gm ON gm.gid=ug.id
                INNER JOIN users u ON u.id=gm.uid
                INNER JOIN users_details ud ON u.id=ud.user_id
                WHERE ug.id=%s"""
        cur.execute(sql, (gid,))
        return cur.fetchall()


def admin_find_usergroups(name: str):
    """
    Returns:
        A list of all user groups with the given name.
    """
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    assert sc.require_admin == True
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor(dictionary=True) as cur:
        sql = """SELECT `id`, `oid`, `name`, `is_public`, `members_can_invite` FROM user_groups WHERE name LIKE %s"""
        cur.execute(sql, (name,))
        return cur.fetchall()


def admin_get_user_group(id: int):
    """
    Returns:
        A user group with the given id.
    """
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    assert sc.require_admin == True
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor(dictionary=True) as cur:
        sql = """SELECT `id`, `oid`, `name`, `is_public`, `members_can_invite`, `icon` FROM user_groups WHERE id = %s"""
        cur.execute(sql, (id,))
        return cur.fetchone()


def admin_user_can_see_group(uid: int, gid: int):
    """
    Returns:
        True if the user with the given id can see the group with the given id.
    """
    sc = miranda.create_security_context("webadmin", auth_from_config=True)
    assert sc.require_admin == True
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor(dictionary=True) as cur:
        sql = """SELECT gid FROM group_maps WHERE gid=%s AND uid=%s"""
        cur.execute(sql, (gid, uid))
        rs = cur.fetchall()
        return cur.rowcount > 0


def get_degree(sc: Security_context, wob):
    """Returns the number of inbound and outbound edges of a wob

    Parameters
    ----------
    sc : Security_context
    wob : wob

    Returns
    -------
    inbound_degree, outbound_degree
        the inbound_degree and the outbound_degree of the wob
    """
    try:
        con = sc.connect()
        with con.cursor() as cursor:
            sql = """
            SELECT
                SUM(IF(dest_id = %s, 1, 0)) AS inbound_edges,
                SUM(IF(src_id = %s, 1, 0)) AS outbound_edges
            FROM edges;
            """
            cursor.execute(sql, (wob.metadata_id, wob.metadata_id))
            rs = cursor.fetchone()
            cursor.close()
            con.close()
            return rs[0], rs[1]
    except mysql.connector.Error as err:
        logger.error(err)


def make_single_user(sc: Security_context, parent_wob, wob, new_name):
    """Creates new_wob based on a copy of wob but with a new ID and metadata_id.
       new_wob is linked parent_wob and new_wob.name changed to new_name if not None.
       Any edges between parent_wob and wob are removed. Returns new_wob.

    Parameters
    ----------
    sc : Security_context
    parent_wob: the parent that will get a single instance of the wob
    wob : the wob that will be cloned
    new_name: the new name of the cloned wob

    Returns
    -------
    new_wob
        the new wob
    """
    new_wob = miranda.clone_object(sc, wob, new_name, copy_edges=True)
    miranda.delete_edge(sc, parent_wob.metadata_id, wob.metadata_id)
    miranda.link(sc, parent_wob, new_wob)
    return new_wob


def provision_proxy_account(sc: Security_context, for_user: str):
    """
    This is an admin function that is meant to be used by server code of miranda deployments to provision temporary passwords to users. It does this using "proxy" accounts. These are created on an as needed basis if no users are returned from "call sp_claim_proxy_account()". The user is then granted `for_user`@`%` privileges to the proxied account then it sets its role to the proxied account.
    Args
        sc : The security context of the logged in user
    Returns:
        A temporary token that includes the username and password for the proxy account.
    """

    new_password = token_urlsafe(26)
    proxy_user = None

    con = sc.connect()
    with con.cursor(dictionary=True) as cur:
        # sp_claim_proxy_account() returns user, host, User_attributes
        cur.callproc("sp_claim_proxy_account")
        print("CALL sp_claim_proxy_account()")
        con.commit()

        rs = next(cur.stored_results()).fetchone()

        if rs is None:
            # no free proxy accounts, create one
            proxy_user = "pxy." + token_urlsafe(12)
            sql = "CREATE USER %s@'%' IDENTIFIED BY %s"
            print(f"CREATE USER {proxy_user}@'%' IDENTIFIED BY 'REDACTED'")
            cur.execute(sql, (proxy_user, new_password))

            # set User_attributes = { is_proxy: true, is_free: false }
            sql = 'UPDATE mysql.user SET User_attributes = \'{"is_proxy": true, "is_free": false}\' WHERE User = %s'
            print(
                'UPDATE mysql.user SET User_attributes = \'{"is_proxy": true, "is_free": false}\' WHERE User = '
                + proxy_user
            )
            cur.execute(sql, (proxy_user,))
        else:
            proxy_user = rs["user"]
            print(f"Reclaiming existing proxy user {proxy_user}")
            # sp sets is_free, no need to set it here
            # update password
            sql = "ALTER USER %s@'%' IDENTIFIED BY %s"
            print(f"ALTER USER {proxy_user}@'%' IDENTIFIED BY 'REDACTED'")
            cur.execute(sql, (proxy_user, new_password))

        # Grant proxy privileges
        cur.execute("GRANT %s@'%' TO %s@'%'", (for_user, proxy_user))
        cur.execute("GRANT mainlyai_user_role TO %s@'%'", (proxy_user,))
        print(f"GRANT mainlyai_user_role TO {proxy_user}@'%'")

        # Set role to proxy user
        cur.execute(
            "SET DEFAULT ROLE mainlyai_user_role,%s@'%' TO %s@'%'",
            (
                for_user,
                proxy_user,
            ),
        )
        print(
            f"SET DEFAULT ROLE  mainlyai_user_role, %{for_user}@'%' TO {proxy_user}@'%'"
        )

        # Claim proxy account
        cur.execute(
            " INSERT INTO proxy_account_claims (name, belonging_to, at, by_application) VALUES (%s, %s, NOW(), 'Miranda')",
            (proxy_user, for_user),
        )
        print(
            f"INSERT INTO proxy_account_claims (name, belonging_to, at, by_application) VALUES ({proxy_user}, {for_user}, NOW(), 'Miranda')"
        )
        con.commit()
        cur.close()

    return f"{proxy_user}.{new_password}"


def reset_proxy_account(sc: Security_context, proxy_user: str):
    """
    This is an admin function that is meant to be used by server code of miranda deployments to reset a proxy account. It does this by setting the password to a new random value and setting the is_free attribute to true.
    Args
        sc : The security context of the logged in user
    Returns:
        A temporary token that includes the username and password for the proxy account.
    """

    new_password = token_urlsafe(26)
    con = sc.connect()
    with con.cursor() as cur:
        # update password
        sql = "ALTER USER %s@'%' IDENTIFIED BY %s"
        print(f"ALTER USER {proxy_user}@'%' IDENTIFIED BY 'REDACTED'")
        cur.execute(sql, (proxy_user, new_password))

        # set User_attributes = { is_proxy: true, is_free: true }
        sql = "UPDATE mysql.user SET User_attributes = JSON_SET(User_attributes, '$.is_free', true) WHERE User = %s"
        print(
            "UPDATE mysql.user SET User_attributes = JSON_SET(User_attributes, '$.is_free', true) WHERE User = "
            + proxy_user
        )
        cur.execute(sql, (proxy_user,))

        # set role to NONE
        sql = "SET DEFAULT ROLE NONE TO %s@'%'"
        print("SET DEFAULT ROLE NONE TO " + proxy_user + "@'%'")
        cur.execute(sql, (proxy_user,))

        # revoke %s@'%' from proxy_user
        sql = "REVOKE %s@'%' FROM %s@'%'"
        print("REVOKE " + proxy_user + "@'%' FROM " + proxy_user + "@'%'")
        cur.execute(sql, (proxy_user, proxy_user))

        # delete from proxy_account_claims
        sql = "DELETE FROM proxy_account_claims WHERE name = %s"
        print("DELETE FROM proxy_account_claims WHERE name = " + proxy_user)
        cur.execute(sql, (proxy_user,))

        con.commit()
        cur.close()

    return f"{proxy_user}.{new_password}"


def reset_proxy_account_password(sc: Security_context, proxy_user: str):
    """
    This is an admin function that is meant to be used by server code of miranda deployments to reset a proxy account password. It does this by setting the password to a new random value.
    Args
        sc : The security context of the logged in user
    Returns:
        A temporary token that includes the username and password for the proxy account.
    """

    new_password = token_urlsafe(26)

    con = sc.connect()
    with con.cursor() as cur:
        # update password
        sql = "ALTER USER %s@'%' IDENTIFIED BY %s"
        print(f"ALTER USER {proxy_user}@'%' IDENTIFIED BY 'REDACTED'")
        cur.execute(sql, (proxy_user, new_password))
        con.commit()
        cur.close()

    return f"{proxy_user}.{new_password}"


def get_proxy_accounts(sc: Security_context, name: str = None):
    """
    This is an admin function that is meant to be used by server code of miranda deployments to get a list of proxy accounts. It does this by calling sp_get_proxy_accounts().
    Args
        sc : The security context of the logged in user
    Returns:
        A list of proxy accounts for the user.
    """

    con = sc.connect()
    with con.cursor(dictionary=True) as cur:
        # sp_get_proxy_accounts() returns user, host, User_attributes
        if name:
            cur.execute(f"SELECT * FROM v_tokens WHERE name = %s", (name,))
        else:
            cur.execute(f"SELECT * FROM v_tokens")

        rs = cur.fetchall()
        con.commit()
        cur.close()

    return rs


def register_docker_image(
    admin_sc: Security_context, properties: dict = {}, tag="", creator_user_id: int = 0
):
    """
    Register a docker image uri in the database and return the ID
    """
    con = admin_sc.connect()
    if tag != "":
        properties["tag"] = tag
    last_id = -1
    with con.cursor() as cur:
        str_properties = json.dumps(properties)
        cur.execute(
            "INSERT INTO docker_images (properties, creator_user_id) VALUES (%s, %s)",
            (str_properties, creator_user_id),
        )
        con.commit()
        last_id = cur.lastrowid
        cur.close()
    return last_id


def get_docker_image(sc: Security_context, uri=None, user_id=None):
    """
    Get a docker image uri from the database
    uri: the uri pattern to search for. TO show all uri use '%'
    user_id: the user_id to search for. To show all user_id use None
    """
    con = sc.connect()
    if uri == None:
        uri = "%"
    if user_id == None:
        sql = "SELECT t.id,t.uri,t.properties,t.image_state,t.image_size,t.creator_user_id,t.created_at,t.updated_at,t.is_base_image as is_base_image, t.base_image_id as base_image_id FROM docker_images t WHERE t.URI LIKE %s"
        sql_data = (uri,)
    else:
        sql = "SELECT t.id,t.uri,t.properties,t.image_state,t.image_size,t.creator_user_id,t.created_at,t.updated_at,t.is_base_image as is_base_image, t.base_image_id as base_image_id FROM docker_images t INNER JOIN user_to_resource_map m ON m.res_id =t.id WHERE (t.creator_user_id <> %s AND m.user_id =%s AND t.uri LIKE %s) UNION SELECT * FROM docker_images WHERE URI LIKE %s AND creator_user_id = %s"
        sql_data = (user_id, user_id, uri, uri, user_id)
    with con.cursor(dictionary=True) as cur:
        cur.execute(sql, sql_data)
        rs = cur.fetchall()
        con.commit()
        cur.close()
    return rs


def delete_docker_image(sc: Security_context, id):
    con = sc.connect()
    with con.cursor() as cur:
        cur.execute("DELETE FROM docker_images WHERE id = %s", (id,))
        con.commit()
        cur.close()


def get_docker_image_id(sc, uri):
    con = sc.connect()
    with con.cursor() as cur:
        cur.execute("SELECT id FROM docker_images WHERE URI = %s", (uri,))
        rs = cur.fetchone()
        con.commit()
        cur.close()
    return rs[0]


def update_docker_image(
    sc: Security_context,
    id,
    uri=None,
    base_image_uri=None,
    properties=None,
    image_state=None,
    image_size=None,
    is_base_image=None,
    base_image_id=None,
):
    con = sc.connect()
    with con.cursor() as cur:
        update_str = ""
        values = []
        if uri != None:
            update_str += "URI = %s,"
            values.append(uri)
        if base_image_uri != None:
            update_str += "base_image_URI = %s,"
            values.append(base_image_uri)
        if properties != None:
            update_str += "properties = %s,"
            values.append(properties)
        if image_state != None:
            update_str += "image_state = %s,"
            values.append(image_state)
        if image_size != None:
            update_str += "image_size = %s,"
            values.append(image_size)
        if is_base_image != None:
            update_str += "is_base_image = %s,"
            values.append(is_base_image)
        if base_image_id != None:
            update_str += "base_image_id = %s,"
            values.append(base_image_id)
        update_str = update_str[:-1]
        sql = "UPDATE docker_images SET " + update_str + " WHERE id = %s"
        print(sql)
        print(values)
        cur.execute(sql, values + [id])
        con.commit()


def remove_user_from_docker_image(
    admin_sc: Security_context, user_id: int, docker_image_id: int
):
    # with admin_sc.connect() as con:
    con = admin_sc.connect()
    with con.cursor() as cur:
        sql = "DELETE FROM user_to_resource_map WHERE user_id = %s AND res_id = %s AND res_type = 'DOCKER_IMAGE'"
        sql_data = (user_id, docker_image_id)
        cur.execute(sql, sql_data)
        con.commit()


def get_all_docker_images_by_user_id(admin_sc: Security_context, user_id: int):
    # with admin_sc.connect() as con:
    con = admin_sc.connect()
    with con.cursor(dictionary=True) as cur:
        sql = """SELECT t.id, t.creator_user_id, t.created_at, t.URI, t.image_state, t.image_size, t.properties
        FROM docker_images t
        INNER JOIN user_to_resource_map u ON t.id = u.res_id
        WHERE (u.user_id = %s AND t.creator_user_id <> %s)
        AND u.res_type = 'DOCKER_IMAGE'
        UNION ALL SELECT t.id, t.creator_user_id, t.created_at, t.URI, t.image_state, t.image_size, t.properties
        FROM docker_images t WHERE t.creator_user_id = %s"""
        sql_data = (user_id, user_id, user_id)
        cur.execute(sql, sql_data)
        rs = cur.fetchall()
        return rs


def add_user_to_docker_image(
    admin_sc: Security_context,
    user_id: int,
    docker_image_id: int,
    access_level: str = "READ",
):
    # with admin_sc.connect() as con:
    con = admin_sc.connect()
    with con.cursor() as cur:
        sql = "INSERT INTO user_to_resource_map (user_id, res_id, res_type, access_level) VALUES (%s, %s, 'DOCKER_IMAGE', %s)"
        sql_data = (user_id, docker_image_id, access_level)
        cur.execute(sql, sql_data)
        con.commit()
        last_id = cur.lastrowid
        return last_id


def get_all_compute_policies_by_docker_image(
    admin_sc: Security_context, docker_image_id: int
):
    # with admin_sc.connect() as con:
    con = admin_sc.connect()
    rs = None
    with con.cursor(dictionary=True) as cur:
        sql = "SELECT id FROM compute_policy WHERE docker_image_id = %s"
        sql_data = (docker_image_id,)
        cur.execute(sql, sql_data)
        rs = cur.fetchall()
    obs = []
    for r in rs:
        obs.append(Compute_policy(admin_sc, r["id"]))
    return obs


def send_realtime_message(admin_sc: Security_context, by: str, to: str, payload: str):
    # with admin_sc.connect() as con:
    con = admin_sc.connect()
    with con.cursor() as cur:
        cur.callproc("sp_send_realtime_message", (by, to, payload))
        cur.fetchall()
        con.commit()


def get_docker_image_by_id(admin_sc: Security_context, docker_image_id: int):
    con = admin_sc.connect()
    rs = None
    with con.cursor(dictionary=True) as cur:
        sql = "SELECT * FROM docker_images WHERE id = %s"
        sql_data = (docker_image_id,)
        cur.execute(sql, sql_data)
        rs = cur.fetchall()
    if len(rs) == 0:
        return None
    else:
        return rs[0]


def _create_organzation(con, name: str, creator_user_id: int = None):
    """insert into the organization table and create associated team group"""
    with con.cursor() as cur:
        # Create the organization first
        cur.execute(
            "INSERT INTO organization (name, creator_user_id) VALUES (%s, %s)",
            (name, creator_user_id),
        )
        org_id = cur.lastrowid
        con.commit()

        # Create a team group for this organization
        team_group_id = admin_create_user_group(
            name=f"{name}",
            group_owner_id=creator_user_id,
            is_public=False,
            members_can_invite_others=True,
            is_org_managed=True,
        )

        # Update the organization to reference this team group
        cur.execute(
            "UPDATE organization SET org_team_group_id = %s WHERE id = %s",
            (team_group_id, org_id),
        )
        con.commit()

        # Add the creator to the team group
        if creator_user_id is not None:
            admin_assign_user_to_group(None, creator_user_id, team_group_id)

        return org_id


def update_organization(
    admin_sc: Security_context,
    id,
    name=None,
    icon=None,
    stripe_cus_id=None,
    subscribed=None,
    trial=None,
    has_onboarded=True,
):
    """update the organization table"""

    # with admin_sc.connect() as con:
    con = admin_sc.connect()
    with con.cursor() as cur:
        update_str = ""
        values = []
        if name != None:
            update_str += "name = %s,"
            values.append(name)
        if icon != None:
            update_str += "icon = %s,"
            values.append(icon)
        if stripe_cus_id != None:
            update_str += "stripe_cus_id = %s,"
            values.append(stripe_cus_id)
        if subscribed != None:
            update_str += "subscribed = %s,"
            values.append(subscribed)
        if trial != None:
            update_str += "trial = %s,"
            values.append(trial)
        if has_onboarded != None:
            update_str += "has_onboarded = %s,"
            values.append(has_onboarded)
        update_str = update_str[:-1]
        sql = "UPDATE organization SET " + update_str + " WHERE id = %s"
        print(sql)
        print(values)
        cur.execute(sql, values + [id])
        con.commit()


def get_organization_by_id(admin_sc: Security_context, id: int):
    con = admin_sc.connect()
    rs = None
    with con.cursor(dictionary=True) as cur:
        sql = "SELECT * FROM organization WHERE id = %s"
        sql_data = (id,)
        cur.execute(sql, sql_data)
        rs = cur.fetchall()
    if len(rs) == 0:
        return None
    else:
        return rs[0]


def get_organization_members(admin_sc: Security_context, id: int):
    con = admin_sc.connect()
    rs = None
    with con.cursor(dictionary=True) as cur:
        sql = """
            SELECT u.username,u.id,ud.first_name,ud.last_name,ud.avatar,ud.industry,ud.role,ud.email
            FROM users u
            INNER JOIN users_details ud ON u.id=ud.user_id
            WHERE u.organization_id = %s
            """
        sql_data = (id,)
        cur.execute(sql, sql_data)
        rs = cur.fetchall()
    return rs


def create_realtime_message_ticket(
    admin_sc: Security_context, ko_id: int, creator_user_id: int
):
    con = admin_sc.connect()
    ticket = secrets.token_urlsafe(48)
    with con.cursor(dictionary=True) as cur:
        sql = "INSERT INTO realtime_message_ticket (ticket, ko_id, creator_user_id) VALUES (%s, %s, %s)"
        sql_data = (ticket, ko_id, creator_user_id)
        cur.execute(sql, sql_data)
        con.commit()
    return ticket


def get_realtime_message_ticket(admin_sc: Security_context, ticket: str):
    con = admin_sc.connect()
    rs = None
    with con.cursor(dictionary=True) as cur:
        sql = "SELECT * FROM realtime_message_ticket WHERE ticket = %s"
        sql_data = (ticket,)
        cur.execute(sql, sql_data)
        rs = cur.fetchall()
    if len(rs) == 0:
        return None
    else:
        return rs[0]


def clean_edges(adminsc, wob: Code_block):
    """For all inbound edges to the wob, remove the edges which doesn't have the corresponding attribute in the wob."""
    # with adminsc.connect() as con:
    con = adminsc.connect()
    with con.cursor() as cur:
        sql = "SELECT src_id, dest_id, attributes FROM edges WHERE dest_id = %s and dest_type = 'CODE'"
        cur.execute(sql, (wob.metadata_id,))
        rs = cur.fetchall()
        for row in rs:
            src_id = row[0]
            dest_id = row[1]
            if row[2] == None:
                continue  # TODO
            attributes: dict = json.loads(row[2])
            if attributes is None or len(attributes) == 0:
                print(
                    "|=> clean_edges: Removing edge from {} to {} because it has no attributes".format(
                        src_id, dest_id
                    )
                )
                sql = "DELETE FROM edges WHERE src_id = %s AND dest_id = %s"
                cur.execute(sql, (src_id, dest_id))
                con.commit()
                continue
            attributes_to_remove = []
            for attr in attributes.keys():
                if wob.get_attribute(attr) == None:
                    attributes_to_remove.append(attr)
            for attr in attributes_to_remove:
                attributes.pop(attr)
                print(
                    "|=> clean_edges: Removing the attribute {} from edge from {} to {} ".format(
                        attr, src_id, dest_id
                    )
                )
                if len(attributes) == 0:
                    print(
                        "|=> clean_edges: Removing edge from {} to {} because it has no more attributes".format(
                            src_id, dest_id
                        )
                    )
                    sql = "DELETE FROM edges WHERE src_id = %s AND dest_id = %s"
                    cur.execute(sql, (src_id, dest_id))
                    break
                else:
                    sql = "UPDATE edges SET attributes = %s  WHERE src_id = %s AND dest_id = %s"
                    cur.execute(sql, (json.dumps(attributes), src_id, dest_id))
            con.commit()


def admin_write_secret(adminsc, user_id, key, value):
    """
    This is an admin function that is meant to be used by server code of miranda deployments to write a secret to the secret store.
    Args
        user : The user who is writing the secret
        key : The key of the secret
        value : The value of the secret
    Returns:
        None
    """

    # with adminsc.connect() as con:
    con = adminsc.connect()
    with con.cursor() as cur:
        cur.execute(
            "INSERT INTO secrets (user_id, `key`, `value`) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE value = %s",
            (user_id, key, value, value),
        )
        con.commit()


def admin_read_secret(adminsc, user_id, key):
    """
    This is an admin function that is meant to be used by server code of miranda deployments to read a secret from the secret store.
    Args
        user : The user who is reading the secret
        key : The key of the secret
    Returns:
        The value of the secret
    """

    # with adminsc.connect() as con:
    con = adminsc.connect()
    with con.cursor() as cur:
        cur.execute(
            "SELECT `value` FROM secrets WHERE user_id = %s AND `key` = %s",
            (user_id, key),
        )
        rs = cur.fetchone()
        if rs == None:
            return None
        return rs[0]


def kill_all_sleepers(adminsc, ko_id):
    """List all running processes on MySQL and find does which has the text 'WAIT_FOR_INPUT' and 'WAIT_FOR_EVENT'.
    Iff either of the processes also have the pattern ko:{ko_id} or ({ko_id}) then issue a KILL statement for each match."""
    # with adminsc.connect() as con:
    con = adminsc.connect()
    with con.cursor(dictionary=True) as cur:
        cur.execute(
            "SELECT * FROM information_schema.processlist WHERE info LIKE '%WAIT_FOR_INPUT%' OR command LIKE '%WAIT_FOR_EVENT%'"
        )
        rows = cur.fetchall()
        for row in rows:
            if row["INFO"] is not None:
                if (
                    row["INFO"].find(f"ko:{ko_id}") != -1
                    or row["info"].find(f"({ko_id})") != -1
                ):
                    print(f"Killing process {row['ID']} with command {row['COMMAND']}")
                    cur.execute(f"KILL {row['ID']}")
                    con.commit()


def kill_input_waiter(admin_sc, ko_id, wob_mid):
    """List all running processes on MySQL and find does which has the text 'WAITING_FOR_INPUT'.
    Iff the process also has the pattern (wob:{wob_id} ko:{ko_id}) then issue a KILL statement for each match."""
    # with admin_sc.connect() as con:
    con = admin_sc.connect()
    with con.cursor(dictionary=True) as cur:
        cur.execute(
            "SELECT * FROM information_schema.processlist WHERE info LIKE '%WAITING_FOR_INPUT%'"
        )
        rows = cur.fetchall()
        for row in rows:
            if row["INFO"] is not None:
                if row["INFO"].find(f"(wob:{wob_mid} ko:{ko_id})") != -1:
                    print(f"Killing process {row['ID']} with command {row['COMMAND']}")
                    cur.execute(f"KILL {row['ID']}")


def admin_grant_credits(
    admin_sc: Security_context, organization_id: int, amount: int, statement: str
):
    """Mint new credits and grant them to an organization."""
    con = admin_sc.connect()
    with con.cursor() as cur:
        cur.callproc("sp_admin_grant_credits", (organization_id, amount, statement))
        con.commit()


def admin_get_all_node_positions(con, project_id: int):
    with con.cursor(dictionary=True) as cursor:
        sql = "SELECT x, y, metadata_id, collapsed_attributes FROM miranda_web.designer_nodes WHERE project_id=%s"
        sql_data = (project_id,)
        cursor.execute(sql, sql_data)
        rows = cursor.fetchall()

        nodes = {}
        for row in rows:
            nodes[row["metadata_id"]] = {"x": row["x"], "y": row["y"]}
            if row["collapsed_attributes"]:
                try:
                    nodes[row["metadata_id"]]["collapsed_attributes"] = json.loads(
                        row["collapsed_attributes"]
                    )
                except:
                    nodes[row["metadata_id"]]["collapsed_attributes"] = []
            else:
                nodes[row["metadata_id"]]["collapsed_attributes"] = []

        sql = "SELECT h, w, metadata_id, control_name FROM miranda_web.designer_sizes WHERE project_id=%s"
        sql_data = (project_id,)
        cursor.execute(sql, sql_data)
        rows = cursor.fetchall()

    for row in rows:
        if row["metadata_id"] in nodes:
            if "controls" not in nodes[row["metadata_id"]]:
                nodes[row["metadata_id"]]["controls"] = {}
            nodes[row["metadata_id"]]["controls"][row["control_name"]] = {
                "h": row["h"],
                "w": row["w"],
            }

    return nodes


def admin_update_or_insert_node_positions(
    con, project_id: int, x: int, y: int, metadata_id: int
):
    with con.cursor() as cursor:
        sql = """
    INSERT INTO miranda_web.designer_nodes (user, project_id, x, y, metadata_id, collapsed_attributes)
    VALUES (%s, %s, %s, %s, %s, '[]')
    ON DUPLICATE KEY UPDATE x=%s, y=%s
    """
        sql_data = ("_FIELD_UNUSED_", project_id, x, y, metadata_id, x, y)
        cursor.execute(sql, sql_data)
        con.commit()


def admin_update_or_insert_node_control(
    con, project_id: int, metadata_id: int, control_name: str, w: int, h: int
):
    with con.cursor() as cursor:
        sql = "REPLACE INTO miranda_web.designer_sizes (user, project_id, metadata_id, control_name, w, h) VALUES (%s, %s, %s, %s, %s, %s)"
        sql_data = ("_FIELD_UNUSED_", project_id, metadata_id, control_name, w, h)
        cursor.execute(sql, sql_data)
        con.commit()


def admin_update_or_insert_collapsed_attributes(
    con, project_id: int, metadata_id: int, collapsed_attributes: list
):
    with con.cursor() as cursor:
        sql = "UPDATE miranda_web.designer_nodes SET collapsed_attributes=%s WHERE user=%s AND project_id=%s AND metadata_id=%s"
        sql_data = (
            json.dumps(collapsed_attributes),
            "_FIELD_UNUSED_",
            project_id,
            metadata_id,
        )
        cursor.execute(sql, sql_data)
        con.commit()


# Edge segments storage/retrieval
def admin_get_all_edge_segments(con, project_id: int):
    try:
        with con.cursor(dictionary=True) as cursor:
            sql = """
            SELECT src_id, src_handle, dest_id, dest_handle, segments
            FROM miranda_web.designer_edge_segments
            WHERE project_id = %s
            """
            cursor.execute(sql, (project_id,))
            rows = cursor.fetchall()
            data = {}
            for row in rows:
                key = f"{row['src_id']}-{row['src_handle']}-{row['dest_id']}-{row['dest_handle']}"
                try:
                    data[key] = json.loads(row["segments"]) if row["segments"] else []
                except Exception:
                    data[key] = []
            return data
    except Exception:
        # Table might not exist yet; return empty
        return {}


def admin_upsert_edge_segments(
    con,
    project_id: int,
    src_id: int,
    src_handle: str,
    dest_id: int,
    dest_handle: str,
    segments: list,
):
    with con.cursor() as cursor:
        # Use REPLACE INTO for idempotent upsert based on a UNIQUE key
        sql = (
            "REPLACE INTO miranda_web.designer_edge_segments "
            "(project_id, src_id, src_handle, dest_id, dest_handle, segments) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        sql_data = (
            project_id,
            src_id,
            src_handle,
            dest_id,
            dest_handle,
            json.dumps(segments),
        )
        cursor.execute(sql, sql_data)
        con.commit()

def admin_grant_workflow_to_team(admin_sc, ko_mid, gid=-1, user_id=-1, write=False, read=True, execute=False):
    con = admin_sc.connect()
    sql = "SELECT metadata_id FROM knowledge_object where id=%s"
    acl_read_sql = "INSERT IGNORE INTO read_acl (oid,gid,wob_mid) VALUES "
    acl_write_sql = "INSERT IGNORE INTO write_acl (oid,gid,wob_mid) VALUES "
    acl_execute_sql = "INSERT IGNORE INTO read_acl (oid,gid,wob_mid) VALUES "
    acl_tables = []
    if read:
        acl_tables.append(acl_read_sql)
    if write:
        acl_tables.append(acl_write_sql)
    if execute:
        acl_tables.append(acl_execute_sql)

    for acl_sql in acl_tables:
        # get all wob mids connected to ko
        sql = "SELECT e.dest_id as mid,m.name as name FROM edges e JOIN metadata m ON m.id=e.dest_id JOIN knowledge_object t ON t.metadata_id=e.src_id WHERE t.metadata_id=%s AND e.dest_type <> 'DOCKER_JOB' AND e.dest_type <> 'COMPUTE_RESOURCE_GROUP'"
        v = []
        with con.cursor(dictionary=True) as cur:
            cur.execute(sql,(ko_mid,))
            res = cur.fetchall()
            #print (f"{len(res)} objects identified.")
            for r in res:
                # print (r["name"],r["mid"])
                v.append(f"({user_id},{gid},{int(r["mid"])})")
        v.append(f"({user_id}, {gid}, {int(ko_mid)})")
        sql = acl_sql + ','.join(v)
        print ("admin_grant_workflow_to_team: ", sql)
        try:
            with con.cursor(dictionary=True) as cur:
                cur.execute(sql)
                con.commit()
        except mysql.connector.IntegrityError as err:
            print("admin_grant_workflow_to_team: ❌ IntegrityError: %s", err)
            pass  # ignore duplicate entries
    con.close()
    print (f"admin_grant_workflow_to_team: ✅ Granted worflow metadata_id={ko_mid} to group id={gid}")

def admin_revoke_workflow_from_team(admin_sc, ko_mid, gid=-1, user_id=-1, write=False, read=True, execute=False):
    con = admin_sc.connect()

    acl_tables = []
    if read:
        acl_tables.append("read_acl")
    if write:
        acl_tables.append("write_acl")
    if execute:
        acl_tables.append("execute_acl")

    # Get all wob mids connected to ko
    sql = "SELECT e.dest_id as mid FROM edges e JOIN knowledge_object t ON t.metadata_id=e.src_id WHERE t.metadata_id=%s AND e.dest_type <> 'DOCKER_JOB' AND e.dest_type <> 'COMPUTE_RESOURCE_GROUP'"
    wob_mids = []
    with con.cursor(dictionary=True) as cur:
        cur.execute(sql, (ko_mid,))
        res = cur.fetchall()
        for r in res:
            wob_mids.append(r["mid"])
    wob_mids.append(ko_mid)

    if not wob_mids:
        print(f"admin_revoke_workflow_from_team: No objects found for workflow metadata_id={ko_mid}")
        con.close()
        return

    mids_placeholder = ','.join(['%s'] * len(wob_mids))

    for acl_table in acl_tables:
        sql_conditions = ["gid = %s", f"wob_mid IN ({mids_placeholder})"]
        sql_data = [gid] + wob_mids

        sql = f"DELETE FROM {acl_table} WHERE {' AND '.join(sql_conditions)}"

        print (f"admin_revoke_workflow_from_team: {sql}")
        try:
            with con.cursor() as cur:
                cur.execute(sql, tuple(sql_data))
                con.commit()
        except mysql.connector.Error as err:
            print(f"admin_revoke_workflow_from_team: ❌ Error: {err}")

    con.close()
    print (f"admin_revoke_workflow_from_team: ✅ Revoked workflow metadata_id={ko_mid} from group id={gid}")
