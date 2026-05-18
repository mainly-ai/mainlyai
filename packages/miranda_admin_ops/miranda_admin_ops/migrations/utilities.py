# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import os
import logging
from mirmod import miranda, get_all_wob_classes

os.environ["MIRANDA_LOGLEVEL"] = str(logging.ERROR)
# If the miranad package isn't installed in the environment we need to use the in souce version
# we locate it using an environment variable.


admin_sc = miranda.create_security_context(auth_from_config=True)


def setup_sps(sc):
    cnx = sc.connect()
    for ob_class in get_all_wob_classes():
        ob = ob_class(sc, -1)
        ob.create_view(cnx)
        ob.create_sp(cnx, miranda.object_to_table)
        ob.make_update_sp(cnx)
    with open("setup/db/sp.sql") as fh:
        with cnx.cursor() as cursor:
            file = fh.read()
            for i, sql in enumerate(file.split("---")):
                print("stmt {} - SQL: {}".format(i, sql[:120]))
                cursor.execute(sql)
                for _ in cursor:
                    pass
            cnx.commit()

    # for user in get_all_miranda_users(cnx):
    for sp in get_all_sp_names(cnx, exclude_admin=True):
        grant_sp_to_user(cnx, sp[0], "mainlyai_user_role")
    cnx.close()


def grant_sp_to_user(cnx, sp, user):
    with cnx.cursor() as cursor:
        print("Granting execute on {} to {}".format(sp, user))
        sql = f"GRANT EXECUTE ON PROCEDURE {sp} TO `{user}`"
        cursor.execute(sql)
        cnx.commit()


def table_exists(sc, table):
    """Looks up information schema and checks if a table exists"""
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = f"SELECT count(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = %s and TABLE_SCHEMA = 'miranda'"
            cur.execute(sql, (table,))
            d = cur.fetchall()[0]
            return d[0] == 1


def count_columns(sc, table):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = "select count(*) from information_schema.columns where table_name=%s and table_schema='miranda'"
            cur.execute(sql, (table,))
            d = cur.fetchall()[0]
            print("There are %s columns in table %s" % (d[0], table))
            return d[0]


def modify_column(sc, table, column, type):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = f"ALTER TABLE {table} MODIFY COLUMN {column} {type}"
            print(
                "  Modifying column %s to type %s in table %s" % (column, type, table)
            )
            cur.execute(sql)


def has_column(sc, table, column, schema="miranda"):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = "select count(*) > 0 from information_schema.columns where table_name=%s and table_schema=%s and column_name=%s"
            cur.execute(sql, (table, schema, column))
            d = cur.fetchall()[0]
            if d[0] > 0:
                print("table '%s' has the column '%s'" % (table, column))
                return True
            else:
                print("table '%s' does not have the column '%s'" % (table, column))
                return False


def add_column(sc, table, column, type, schema="miranda"):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = f"ALTER TABLE `{schema}`.`{table}` ADD COLUMN `{column}` {type}"
            print("  Adding column %s to table %s" % (column, table))
            cur.execute(sql)


def drop_column(sc, table, column):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = f"ALTER TABLE `{table}` DROP COLUMN `{column}`"
            print("  Dropping column %s to table %s" % (column, table))
            cur.execute(sql)


def add_index(sc, table, column):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = f"ALTER TABLE {table} ADD INDEX ({column});"
            print("  Adding index %s to table %s" % (column, table))
            cur.execute(sql)


def change_column(sc, table, column, type):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = f"ALTER TABLE {table} MODIFY COLUMN {column} {type}"
            print("  Changing column %s to type %s in table %s" % (column, type, table))
            cur.execute(sql)


def rename_column(sc, table, column, new_column):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = f"ALTER TABLE {table} RENAME COLUMN {column} TO {new_column}"
            print(
                "  Renaming column %s to %s in table %s" % (column, new_column, table)
            )
            cur.execute(sql)


def drop_view_if_exists(sc, view):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = f"DROP VIEW IF EXISTS {view}"
            print("  Dropping view %s" % (view))
            cur.execute(sql)


def recreate_views(admin_sc):
    sc = miranda.create_security_context("nobody", "nopass")
    with admin_sc.connect() as cnx:
        for ob_class in get_all_wob_classes():
            ob = ob_class(sc, -1)
            print("  Recreating view for %s" % ob_class.__name__)
            ob.create_view(cnx)
            ob.create_sp(cnx, miranda.object_to_table)
            ob.make_update_sp(cnx)


def get_column_data_type(sc, table, column):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = f"SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s AND COLUMN_NAME = %s"
            cur.execute(sql, (table, column))
            d = cur.fetchall()[0]
            return d[0]


def get_column_column_type(sc, table, column):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = f"SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s AND COLUMN_NAME = %s"
            cur.execute(sql, (table, column))
            d = cur.fetchall()[0]
            return d[0]


def remove_column(sc, table, column):
    with sc.connect() as con:
        with con.cursor() as cur:
            sql = f"ALTER TABLE {table} DROP COLUMN {column}"
            print("  Removing column %s from table %s" % (column, table))
            cur.execute(sql)


def get_all_miranda_users(con):
    with con.cursor() as cur:
        sql = 'SELECT user from mysql.user WHERE substr(user,1,8) = "miranda_" AND host="%"'
        cur.execute(sql)
        res = cur.fetchall()
        cur.close()
        return res


def get_all_miranda_web_users(con):
    with con.cursor() as cur:
        sql = "SELECT username from miranda_web.web_users"
        cur.execute(sql)
        res = cur.fetchall()
        cur.close()
        return res


def get_all_sp_names(con, exclude_admin=False):
    with con.cursor() as cur:
        sql = "SELECT CONCAT(ROUTINE_SCHEMA, '.', ROUTINE_NAME) AS `FullProcedureName` FROM information_schema.routines WHERE ROUTINE_TYPE='PROCEDURE' AND ROUTINE_SCHEMA = 'miranda'"
        if exclude_admin:
            sql += " AND ROUTINE_NAME NOT LIKE 'sp_admin%'"
        cur.execute(sql)
        res = cur.fetchall()
        cur.close()
        return res
