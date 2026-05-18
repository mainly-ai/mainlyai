# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import sys
import mysql.connector
import hashlib
import os

import miranda_admin_ops as admin
from mirmod import miranda
from mirmod.security.security_context import get_config
from mirmod.utils.logger import Logger


logger = Logger()

yes_all = False
if "YES_ALL" in os.environ:
    yes_all = True


def web_user_to_miranda_user(webtest_webuser, webtest_webpass, db_secret_webtest):
    return webtest_webuser, webtest_webpass + db_secret_webtest


def make_password_hash(salt, pwd):
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), bytes.fromhex(salt), 5000)
    return dk.hex()


def user_exists(sc, u):
    con = sc.connect()
    cur = con.cursor()
    sql = "SELECT count(*) as c FROM miranda.users WHERE username = %s"
    sql_data = (u,)
    cur.execute(sql, sql_data)
    c = 0
    for r in cur:
        c = r[0]
    cur.close()
    if c > 0:
        return True
    return False


def create_webuser(cursor, u, p, isadmin=False):
    sql = (
        "SELECT count(*) as c,db_secret FROM miranda_web.web_users WHERE username = %s"
    )
    sql_data = (u,)
    cursor.execute(sql, sql_data)
    create_webadmin = False
    for r in cursor:
        create_webadmin = r[0] == 0
        db_secret = r[1]
    if create_webadmin:
        jwt_secret = os.urandom(32).hex()
        db_secret = os.urandom(32).hex()
        salt = os.urandom(32).hex()
        if isadmin:
            isadmin = 1
        else:
            isadmin = 0
        hashed_password = make_password_hash(salt, p)
        sql = "INSERT INTO miranda_web.web_users (username,auth,jwt_secret,db_secret,salt,is_admin) VALUES (%s,%s,%s,%s,%s,%s)"
        sql_data = (u, hashed_password, jwt_secret, db_secret, salt, isadmin)
        cursor.execute(sql, sql_data)
        con.commit()
    return db_secret


if __name__ == "__main__":
    path = ""
    if sys.argv == 2:
        path = sys.argv[1]
    miranda_config = get_config(path)
    admin.drop_database(miranda_config, yes_all)
    if yes_all:
        choice = "y"
    else:
        choice = ""
    while choice == "" or choice not in "yn":
        choice = input("Do you want to create database tables? [Y] > ") or "y"
        choice = choice.lower()
    if choice == "y":
        admin.setup_database(miranda_config)
    if yes_all:
        choice = "y"
    else:
        choice = ""
    while choice == "" or choice not in "yn":
        choice = (
            input("Do you want to insert SDG data into the database? [Y] > ") or "y"
        )
        choice = choice.lower()
    if choice == "y":
        admin.insert_into_database(miranda_config)
    if yes_all:
        choice = "y"
    else:
        choice = ""
    while choice == "" or choice not in "yn":
        choice = input("Do you want to setup the users? [Y] > ") or "y"
        choice = choice.lower()
    username = "testuser"
    password = "pass"
    webadmin = "webadmin"
    webadmin_password = "p0Odle1!"
    webtest_webuser = "webtest"
    webtest_webpass = "p0Odle2!"
    if choice == "y":
        print("Setting up test user.")
        if not yes_all:
            choice = input(f"Enter test username [{username}] > ")
            if choice != "":
                username = choice
            choice = input(f"Enter test password [{password}] > ")
            if choice != "":
                password = choice
            choice = input(f"Enter web administrator username [{webadmin}] >")
            if choice != "":
                webadmin = choice
            choice = input(f"Enter web administrator password [{webadmin_password}] > ")
            if choice != "":
                webadmin_password = choice
            choice = input(f"Enter web user webtest username [{webtest_webuser}] >")
            if choice != "":
                webtest_user = choice
            choice = input(f"Enter web user webtest password [{webtest_webpass}] >")
            if choice != "":
                webtest_webpass = choice

        # TODO User management will be separated from miranda code management
        # For test purpose they remain the same
        con = mysql.connector.connect(**miranda_config)
        sc = miranda.create_security_context(
            miranda_config["user"], miranda_config["password"]
        )

        def bootstrap_func():
            pass

        sc.renew_id = bootstrap_func
        sc.db_config["user"] = miranda_config["user"]
        sc.db_config["password"] = miranda_config["password"]
        admin.remove_user(sc, username)
        u, p = admin.create_user(sc, username, password, email=f"{username}@mainly.ai")
        logger.info(f"Created {u} with password {p} ")

        admin.remove_user(sc, webtest_webuser)
        admin.remove_user(sc, webadmin)
        # Create default webadmin account
        miranda_user, miranda_pw = None, None
        cursor = con.cursor()
        # Make sure the DB user is removed for the webadmin and webtest_user
        # as leaving this untouched might cause confusion.
        sql = "DROP USER IF EXISTS miranda_{}@'%', miranda_{}@'%'".format(
            webadmin, webtest_webuser
        )
        cursor.execute(sql)
        con.commit()
        # Here we transform the web side user/pw to the miranda side user/pw.
        # This is done to hide the backend details from the user of the web system
        # The create_miranda_credentials function must be the same which is used in
        # the backend_flask system
        # salt = os.urandom(32).hex()
        db_secret_webadmin = create_webuser(
            cursor, webadmin, webadmin_password, isadmin=True
        )
        webadmin_mirandauser, webadmin_mirandapass = web_user_to_miranda_user(
            webadmin, webadmin_password, db_secret_webadmin
        )
        admin.create_user(sc, webadmin_mirandauser, webadmin_mirandapass)
        logger.info(f"Created {webadmin_mirandauser} using {webadmin_mirandapass}")
        db_secret_webtest = create_webuser(cursor, webtest_webuser, webtest_webpass)
        webtest_mirandauser, webtest_mirandapass = web_user_to_miranda_user(
            webtest_webuser, webtest_webpass, db_secret_webtest
        )
        admin.create_user(sc, webtest_mirandauser, webtest_mirandapass)
        logger.info(f"Created {webtest_mirandauser} using {webtest_mirandapass}")

        logger.info("Checking integrity for {}.".format(webadmin))
        res = admin.user_integrity(sc, webadmin)
        logger.info(res)
        assert res == "miranda: 1 mysql: 1 web: 1"
        print("Checking integrity for {}.".format(webtest_webuser))
        res = admin.user_integrity(sc, webtest_webuser)
        logger.info(res)
        assert res == "miranda: 1 mysql: 1 web: 1"

        logger.info(
            "Elevating webadmin privilegs to ADMIN level. "
            "NOTE: This is the only account which will have its privileges assigned this way. The"
            " rest of the accounts will be created from the WEB GUI using the webadmin credentials."
        )

        #
        # TODO Because AWS doesn't give us full admin access we need to use the AWS account
        # for dropping users and granting them privileges
        #
        def elevate_db_user(db_user):
            config = get_config()
            con2 = mysql.connector.connect(**config)
            cursor2 = con2.cursor()
            sql = "GRANT ALL ON miranda_web.* TO %s@'%'"
            sql_data = (db_user,)
            cursor2.execute(sql, sql_data)
            con2.commit()
            sql = "GRANT ALL PRIVILEGES ON *.* TO %s@'%'"  # WITH GRANT OPTION")
            sql_data = (db_user,)
            cursor2.execute(sql, sql_data)
            con2.commit()
            cursor.close()
            con.close()

        elevate_db_user("miranda_testuser")
        elevate_db_user("miranda_webadmin")

        while choice == "" or choice not in "yn":
            choice = input("Do you want to create mock data? [N] > ") or "n"
            choice = choice.lower()
        if choice == "y":
            logger.info(f"Creating mock data as {webadmin_mirandauser}.")
            sc = miranda.create_security_context(
                webadmin_mirandauser, webadmin_mirandapass
            )
            for i in range(1, 10):
                ko = miranda.create_knowledge_object(sc, f"Project {i}", "Mock data")
                assert ko.metadata_id != None, "Failed to create Knowledge_object"

            logger.info("Creating mock data as webtest user")
            sc = miranda.create_security_context(
                webtest_mirandauser, webtest_mirandapass
            )
            for i in range(11, 20):
                ko = miranda.create_knowledge_object(sc, str(i), "Mock data")

    print("All is done.")
