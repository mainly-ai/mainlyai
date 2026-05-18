# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import mysql.connector
from mysql.connector import errorcode
from pathlib import Path
import yaml
import glob
from mirmod.utils.logger import logger



tables_relative_path = 'setup/db/tables'

def _get_all_table_names():
    ''' returns a list of all the tables in the datamodel'''
    return ["acls", "knowledge_object", "datastream", "etl_process", "model", "code",
            "simulator", "edges", "storage", "metadata", "users", "deployment" ]

def drop_database(config):
    y = input("Drop the tables Y/N > ")
    if y != 'Y' and y != 'y':
        logger.error("Drop database cancelled.")
        return

    logger.info("Dropping all miranda tables.")

    try:
        cnx = mysql.connector.connect(**config)
        logger.info("Connected to the database.")
        # TODO check integrity of the DB
        tables = []
        for t in _get_all_table_names():
            tables.append("DROP TABLE IF EXISTS "+t)

        cur = cnx.cursor()
        cur.execute("DROP TABLE IF EXISTS edges")
        for sql in tables:
            print (sql)
            cur.execute(sql)
        cnx.commit()
        logger.info("Dropped all miranda tables.")
        cnx.close()
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logger.error("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            logger.error("Database does not exist")
        else:
            logger.error(err)

    cnx.close()


def _get_table_dependencies(config, table):
    try:
        return config['tables'][table]['depends_on']
    except KeyError:
        return ''

def _get_table_def(_type, mod_path):
    definitions = []
    path = str((mod_path / tables_relative_path).resolve())
    with open(str(path + f'/config.yml')) as f:
        conf = yaml.load(f, Loader=yaml.FullLoader)
    for filename in glob.iglob(path + f'/*/{_type}/*.sql', recursive=True):
        table_name = Path(filename).stem
        dependencies = _get_table_dependencies(conf, table_name)
        definitions.append((table_name, dependencies, filename))
    return sorted(definitions, reverse=True)


def setup_database(config, modpath):
    tables_to_be_created = []
    try:
        cnx = mysql.connector.connect(**config)
        cur = cnx.cursor()
        print("Connected to the database.")
        definitions = _get_table_def('ddl', modpath)
        for table, dependencies, ddl in definitions:
            tables_to_be_created.append(table)

        while tables_to_be_created:
            for table, dependencies, ddl in definitions:
                f = open(ddl, "r")
                sql = f.read()
                if table in tables_to_be_created and dependencies == '':
                    logger.info(f" Table does not have any dependencies, create table{table}")
                    cur.execute(sql)
                    tables_to_be_created.remove(table)
                # Table with dependencies - CHECK
                elif table in tables_to_be_created and dependencies != '':
                    satisfied = True
                    logger.info(f" Table {table} has dependencies, check dependencies")
                    for d in dependencies:
                        if d in tables_to_be_created:
                            logger.info("Dependencies not satisfied!")
                            satisfied = False
                    # Dependencies satisfied - SAFE TO CREATE
                    if satisfied:
                        logger.info(f"Dependencies satisfied! Create table {table}")
                        cur.execute(sql)
                        tables_to_be_created.remove(table)
            cnx.commit()

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logger.error("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            logger.error("Database does not exist")
        else:
            logger.error(err)
    cnx.close()


def create_user(con, app_user,app_pass,db_user,db_pass):
    ''' Creates a dbuser and assign it the the default roles.
        This function should be executed with the highest security
        access and thus not part of the miranda library but the
        miranda_admin library not yet built. '''
    try:    
        cursor = con.cursor()
        sql = "CREATE USER IF NOT EXISTS %s@`%` IDENTIFIED BY %s"
        sql_data = (db_user, db_pass)
        cursor.execute(sql,sql_data)
        sql = "GRANT UPDATE,DELETE,CREATE,INSERT,SELECT ON miranda.* TO %s@`%`"
        sql_data = (db_user,)
        cursor.execute(sql,sql_data)
        sql = "SELECT username FROM users WHERE username = %s"
        sql_data = (app_user,)
        cursor.execute(sql, sql_data)
        found = False
        for r in cursor:
            found = True
            logger.info("User already exists")
        if not found:
            # TODO currently I'm just inserting a plain text password here but it will be a crypt string
            # later. This is for debug purpose only when developing. 
            sql = "INSERT INTO users (username, `auth`) VALUES (%s,%s)"
            sql_data = (app_user, app_pass)
            cursor.execute(sql, sql_data)
            logger.info("User created")

        con.commit()
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logger.error("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            logger.error("Database does not exist")
        else:
            logger.error(err)
