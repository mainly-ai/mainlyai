import json
import os
import time
import mysql.connector
import mysql.connector.pooling
from pathlib import Path
from hashlib import sha256
from mirmod.utils import logger
import uuid


def get_config(system_path="", config_file_name="config.json", ignore_env=False):
    # TODO make singleton
    if not ignore_env and config_file_name == "config.json":
        if "MIRANDA_CONFIG_JSON" in os.environ:
            try:
                config = json.loads(os.environ["MIRANDA_CONFIG_JSON"])
                logger.debug(
                    "Loaded config file from environment variable MIRANDA_CONFIG_JSON"
                )
                return config
            except Exception as e:
                logger.error(
                    "Can't load config file from environment variable MIRANDA_CONFIG_JSON"
                )
                logger.error(e)
                pass

    path = ""
    paths = [Path("/etc/miranda"), system_path, Path.home(), Path("/miranda")]
    for p in paths:
        try:
            path = p
            config_file = open(os.path.join(p, config_file_name))
            config = json.load(config_file)
            config_file.close()
            return config
        except FileNotFoundError:
            logger.debug(
                f'Tried to find config file "{config_file_name}" in location "{path}" and failed.'
            )
            pass
    logger.error(
        f"Can't find the Miranda configuration file {config_file_name} which should reside in one of the following directories: {paths}"
    )
    logger.error(f"For more information see get_config() in {__file__}")
    exit(-1)


def _create_db_cred(user, auth):
    db_username = "miranda_" + user
    m = sha256()
    db_password = m.update(b"miranda" + bytes(auth, "utf-8"))
    db_password = m.hexdigest()
    if db_username and db_password:
        return (db_username, db_password)
    else:
        logger.error("error creating database credentials")
        return None


class AuthenticationError(Exception):
    def __init__(self, n, p):
        self.name = n
        self.password = p

    def __str__(self):
        return "Authentication error: Can't authenticate as '{}' using password '{}'".format(
            self.name, self.password
        )


class Security_context:
    """The security context handles the database connection and application level identity of the API operator"""

    def __init__(
        self,
        user_name="",
        auth_string="",
        auth_from_config=False,
        system_path="",
        config_file="",
        temp_token=None,
        auth_string_is_already_hashed=False,
        pool_size: int = None,
    ):
        self.connection = None
        self.pool = None
        self.pool_size = pool_size
        self.auth_from_config = auth_from_config
        self.temp_token = temp_token
        self.last_renew = 0
        self.db_config = get_config(system_path)
        # The require_admin attribute is used to determine if a
        # a restricted SQL view is required to access data
        # or if SQL admin privileges can be assumed.
        # Note: setting require_admin = True doesn't grant admin
        # privileges
        self.require_admin = False
        if auth_from_config:
            self.application_user = self.db_config["user"]
            self.application_authstr = self.db_config["password"]
            self.database_user, self.database_password = (
                self.application_user,
                self.application_authstr,
            )
            self.require_admin = (
                True  # If we read the admin password this is an admin user
            )
        else:
            self.application_user = user_name
            self.application_authstr = auth_string
            if temp_token is None:
                self.database_user, self.database_password = _create_db_cred(
                    self.application_user, self.application_authstr
                )
                if auth_string_is_already_hashed:
                    self.database_password = self.application_authstr
            else:
                if " " in temp_token:
                    self.application_user = temp_token.split(" ")[0]
                    temp_token = temp_token.split(" ")[1]

                if temp_token.startswith("pxy."):
                    [_, user, pwd] = temp_token.split(".")
                    self.application_user = "pxy." + user
                    self.database_user, self.database_password = ("pxy." + user, pwd)
                else:
                    self.database_user, _ = _create_db_cred(
                        self.application_user, self.application_authstr
                    )
                    self.database_password = temp_token
            self.db_config["user"] = self.database_user
            self.db_config["password"] = self.database_password
        self.db_config["use_pure"] = True
        self.id = -1
        logger.debug(f"Security context created: {id(self)}")

    def __del__(self):
        logger.debug(f"Security context closed: {id(self)}")
        try:
            self.close()
        except Exception as e:
            logger.error(f"Error closing security context: {e}")

    def renew_id(self):
        if time.time() - self.last_renew < 30:
            return self.id

        self.last_renew = time.time()

        with self.connection.cursor() as cursor:
            sql = "SELECT id FROM v_user"
            cursor.execute(sql)
            res = cursor.fetchone()
            if res is None:
                self.id = -1
                # special case for when you try to authenticate using a non-miranda mysql user
                if self.auth_from_config:
                    return -1
                raise AuthenticationError(
                    self.application_user, self.application_authstr
                )
            self.id = res[0]

            if self.application_user.startswith("pxy."):
                sql = "CALL sp_extend_proxy_account_claim(%s)"
                cursor.execute(
                    sql,
                    (
                        os.environ["MIRANDA_APPLICATION_NAME"]
                        if "MIRANDA_APPLICATION_NAME" in os.environ
                        else "miranda",
                    ),
                )

        return self.id

    def user_id(self):
        if self.id == -1:
            self.id = self.renew_id()
        return self.id

    def connect(self):
        if self.pool_size is not None:
            if self.pool is None:
                pool_config = {
                    "pool_name": str(uuid.uuid4()),
                    "pool_size": self.pool_size,
                    "pool_reset_session": True,
                }
                self.pool = mysql.connector.pooling.MySQLConnectionPool(
                    **pool_config, **self.db_config
                )
            try:
                self.connection = self.pool.get_connection()
            except Exception as e:
                logger.error(f"Failed to get connection from pool: {e}")
                retry_count = 3
                while retry_count > 0:
                    try:
                        self.pool.add_connection()
                        self.connection = self.pool.get_connection()
                        logger.debug(
                            f"Added connection to pool and got connection: {self.connection}"
                        )
                        break
                    except Exception as retry_error:
                        retry_count -= 1
                        logger.error(f"Retry {3 - retry_count}/3 failed: {retry_error}")
                        if retry_count == 0:
                            raise Exception(
                                f"Failed to add and get connection after 3 retries: {retry_error}"
                            ) from e
            self.renew_id()
            return self.connection
        else:
            if self.connection is None:
                self.connection = mysql.connector.connect(**self.db_config)
                self.renew_id()
            retry = 3
            while not self.connection.is_connected() and retry > 0:
                self.connection = mysql.connector.connect(**self.db_config)
                self.renew_id()
                retry -= 1
            return self.connection

    def whoami(self):
        return (self.application_user, self.database_user)

    def close(self):
        if self.connection is not None:
            if self.connection.is_connected():
                self.connection.close()
        if self.pool is not None:
            self.pool.closeall()
