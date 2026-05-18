# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

# script that runs every migration file in ./migrations and then updates the database version

import os
import subprocess
import sys

from mirmod import miranda


def main():
    # get the current version from the database
    current_version = 0
    should_ff = False
    admin_sc = miranda.create_security_context("admin", auth_from_config=True)
    with admin_sc.connect() as con:
        # if the migrations table doesn't exist, create it
        with con.cursor() as cur:
            sql = "SELECT count(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = %s and TABLE_SCHEMA = 'miranda'"
            cur.execute(sql, ("migrations",))
            d = cur.fetchall()[0]
            if d[0] == 0:
                print("Migrations table does not exist, creating it")
                sql = "CREATE TABLE migrations (version int, name varchar(255), date datetime)"
                cur.execute(sql)
                con.commit()
            cur.close()

        # get the current version
        with con.cursor() as cur:
            sql = "SELECT max(version) FROM migrations"
            cur.execute(sql)
            d = cur.fetchall()[0]
            if d[0] is not None:
                current_version = d[0]
            else:
                should_ff = True
            cur.close()

    print(f"Current version is {current_version}")

    migrations = os.listdir("migrations")
    # filter migrations that only start with <number>-
    migrations = [m for m in migrations if m.split("-")[0].isdigit()]
    # sort by version from the first part of the filename, split by -
    migrations.sort(key=lambda x: int(x.split("-")[0]))

    didMigrate = False
    for migration in migrations:
        version = int(migration.split("-")[0])
        if version > current_version:
            print(f"Running migration {migration}")
            try:
                if not should_ff:
                    subprocess.run(
                        ["python3", "migrations/" + migration]
                    ).check_returncode()
                with admin_sc.connect() as con:
                    with con.cursor() as cur:
                        sql = "INSERT INTO migrations (version, name, date) VALUES (%s, %s, now())"
                        cur.execute(sql, (version, migration))
                        con.commit()
                        cur.close()
                # run the migration
                if should_ff:
                    print(
                        f"Fast-forwarding past migration {migration} without running it"
                    )
                else:
                    print(f"Migration {migration} complete")
                didMigrate = True
            except Exception as e:
                print(f"Migration {migration} failed")
                print(e)
                sys.exit(1)
    if didMigrate:
        subprocess.run(["python3", "migrations/post_migrations.py"]).check_returncode()
        print("Migrations complete")
    else:
        print("No migrations to run, database is up to date")


if __name__ == "__main__":
    main()
