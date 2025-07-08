from mirmod.security.security_context import Security_context
from tabulate import tabulate
import mysql
import json
import re
import base64
from mirmod.utils import logger

_representation_policy = "text"


def get_object_view_representation_policy():
    """Valid return valus are 'text','html'"""
    return _representation_policy


def set_object_view_representation_policy(p):
    global _representation_policy
    _representation_policy = p


class Attribute_tracker(object):
    changed_list = []
    change_tracking_enabled = False

    def clear_changed_list(cls):
        cls.changed_list.clear()

    def __setattr__(self, __name: str, __value) -> None:
        if self.change_tracking_enabled and __name != "change_tracking_enabled":
            if __name not in self.changed_list and __name not in ["id", "sctx", "cko"]:
                self.changed_list.append(__name)
        super().__setattr__(__name, __value)


class Base_object_ORM(Attribute_tracker):
    """Base class for all ORM objects"""

    metadata = {
        "metadata_id": "m.id as metadata_id",
        "name": "m.name as name",
        "description": "m.description as `description`",
        "last_updated": "DATE_FORMAT(m.last_updated,'%Y-%m-%dT%TZ') as last_updated",
        "last_used": "DATE_FORMAT(m.last_used,'%Y-%m-%dT%TZ') as last_used",
        "time_created": "DATE_FORMAT(m.time_created,'%Y-%m-%dT%TZ') as time_created",
        "created_by_id": "m.created_by_id as created_by_id",
        "deleted": "m.deleted as deleted",
        "cloned_from_id": "m.cloned_from_id as cloned_from_id",
        "status": "m.status as `status`",
    }

    changed_list = []
    change_tracking_enabled = True

    def get_projection(self, fields: list[str]):
        """Returns a projection of the fields in the ORM"""
        if "id" not in fields:
            fields.append("id")
        for f in fields:
            if f not in self.orm.keys():
                raise ValueError(f"Field {f} not in ORM")
        projection = ",".join(
            [re.sub(r"^[tme]\.[a-zA-Z`_]* (as|AS) ", "", self.orm[x]) for x in fields]
        )
        projection += "," + ",".join(self.metadata.keys())
        return f"SELECT {projection} FROM v_{self.table_name} as v"

    def create_mapping(self, orm, table):
        """NOTE Object table is required to have a metadata_id columns"""
        self.change_tracking_enabled = False
        self.orm = orm
        self.table_name = table
        self.select_projection_stmt = "SELECT DISTINCT " + ",".join(
            [x for x in orm.values()]
        )
        self.select_projection_stmt2 = ",".join([x for x in orm.values()])
        # self.view_projection_stmt = "SELECT " + ",".join([re.sub(r'^[tme]\.[a-zA-Z`_]* (as|AS) ','v.',x) for x in orm.values()])
        # self.view_projection_stmt2= ",".join([re.sub(r'^[tme]\.[a-zA-Z`_]* (as|AS) ','v.',x) for x in orm.values()])
        self.view_projection_stmt = "SELECT " + ",".join(
            [re.sub(r"^.* (as|AS) ", "v.", x) for x in orm.values()]
        )
        self.view_projection_stmt2 = ",".join(
            [re.sub(r"^.* (as|AS) ", "v.", x) for x in orm.values()]
        )
        match = r"t\.`?(?P<field>\w*)`?\s[Aa][Ss].*"
        self.wob_insert_projection = [
            re.sub(match, r"\g<field>", x)
            for x in orm.values()
            if x.startswith("t.") and not x.startswith("t.id")
        ]
        self.from_join_stmt = (
            f" FROM {table} as t" + " INNER JOIN metadata as m on t.metadata_id = m.id"
        )
        self.from_join_stmt_all_users = (
            f" FROM {table} as t" + " INNER JOIN metadata as m on t.metadata_id = m.id"
        )
        self.sql_load_stmt = (
            self.select_projection_stmt
            + self.from_join_stmt_all_users
            + " WHERE t.id = %s"
        )
        self.sql_search_stmt = (
            self.select_projection_stmt + self.from_join_stmt + " WHERE m.name LIKE %s"
        )
        self.sql_delete_by_id_stmt = (
            "DELETE m,t " + self.from_join_stmt + " WHERE t.id=%s"
        )
        self.sql_search_edges_by_ko_stmt = (
            self.select_projection_stmt
            + self.from_join_stmt_all_users
            + " INNER JOIN edges AS e ON e.dest_id=m.id "
            + f" WHERE e.dest_type='{table.upper()}' AND e.src_id = %s AND m.created_by_id=%s"
        )
        self.sql_search_edges_by_ko_stmt_all_users = (
            self.select_projection_stmt
            + self.from_join_stmt
            + " INNER JOIN edges AS e ON e.dest_id=m.id "
            + f" WHERE e.dest_type='{table.upper()}' AND e.src_id = %s"
        )
        self.sql_find_by_metadata_id = (
            self.select_projection_stmt + self.from_join_stmt + " WHERE m.id = %s"
        )
        self.sql_find_by_metadata_id_all_users = (
            self.select_projection_stmt
            + self.from_join_stmt_all_users
            + " WHERE m.id = %s"
        )
        self.all_select_statements = [
            self.sql_load_stmt,
            self.sql_search_stmt,
            self.sql_search_edges_by_ko_stmt,
            self.sql_find_by_metadata_id,
        ]

        self.v_sql_search_stmt = (
            self.view_projection_stmt
            + f" FROM v_{table} AS v"
            + " WHERE v.name LIKE %s"
        )
        self.v_sql_load_stmt = (
            self.view_projection_stmt + f" FROM v_{table} AS v" + " WHERE v.id = %s"
        )
        self.v_sql_find_by_metadata_id = (
            self.view_projection_stmt
            + f" FROM v_{table} AS v"
            + " WHERE v.metadata_id = %s"
        )
        self.v_sql_search_edges_by_ko_stmt = (
            self.view_projection_stmt
            + f" FROM v_{table} AS v"
            + " INNER JOIN v_edges AS e ON e.dest_id=v.metadata_id "
            + f" WHERE e.dest_type='{table.upper()}' AND e.src_id = %s"
        )

        self.groups = {}
        self.change_tracking_enabled = True

    def create_sp_paramlist(self, con):
        """Get the SQL type of the fields that this ORM is comprised of.
        Note: The table must have been constructed before this call is made and
         the ORM must have been initialized.
        """
        params = []
        table_params = {}
        with con.cursor() as cur:
            cur.execute(f"desc {self.table_name}")
            for rs in cur:
                # check if rs[1] is bytes; if so convert to string
                if isinstance(rs[1], bytes):
                    table_params[rs[0].lower()] = rs[1].decode("utf-8").upper()
                else:
                    table_params[rs[0].lower()] = rs[1].upper()
        # Force order and validity of fields to comply to wob_insert_projection
        for p in self.wob_insert_projection:
            if p in table_params.keys():
                paramt = table_params[p]
                params.append(f"`{p}` {paramt}")
        return params

    def create_sp(self, con, object_to_table):
        """Create SP construction statements to be used when the database is setup or updated."""

        def quote_if_not_quoted(x):
            if x[0] == "`":
                return x
            else:
                return "`" + x + "`"

        # otype = object_to_table(self)
        self.sp_create = f"sp_create_{self.table_name}"
        params = self.create_sp_paramlist(con)
        self.sp_param_list = (
            "`name` VARCHAR(200), `description` TEXT, `cloned_from_id` INTEGER, "
            + ",".join(params)
        )
        self.sp_workflow_object_insert_fields_quoted = [
            quote_if_not_quoted(x) for x in self.wob_insert_projection
        ]
        self.create_sp_create = f"""
CREATE DEFINER=miranda_internal@'localhost' PROCEDURE {self.sp_create}({self.sp_param_list})  NOT DETERMINISTIC MODIFIES SQL DATA
BEGIN
DECLARE db_user VARCHAR(40) DEFAULT "nouser";
SET db_user = CURRENT_MIRANDA_USER();
SET db_user = REGEXP_REPLACE(db_user,'^miranda_','');
SELECT ID FROM users WHERE username = db_user INTO @userid;
IF @userid IS NULL THEN
  SIGNAL SQLSTATE '45000'
	SET MESSAGE_TEXT = "Could not find user name in the user table.";
END IF;
SET db_user = CONCAT('miranda_',db_user);
INSERT INTO metadata (`Created_by_id`,`Name`,`Description`,`cloned_from_id`) VALUES (@userid,name,description,cloned_from_id);
SELECT LAST_INSERT_ID() INTO @metadata_id;
INSERT INTO {self.table_name} (`metadata_id`,{",".join(self.sp_workflow_object_insert_fields_quoted)}) VALUES (@metadata_id,{",".join(self.sp_workflow_object_insert_fields_quoted)});
SELECT id FROM {self.table_name} ORDER BY id DESC LIMIT 1 INTO @id;
SELECT @id as id,@metadata_id as metadata_id;
END
        """

        with con.cursor() as cur:
            cur.execute(f"DROP PROCEDURE IF EXISTS {self.sp_create}")
            con.commit()
            cur.execute(self.create_sp_create)
            con.commit()

    def create_view(self, con):
        """Create a secure view of this tabled joined with ACLs and metadata."""
        if self.table_name is None or self.table_name == "":
            print("ERROR: create_view: ORM not initialized properly.")
            return
        self.view = f"miranda.v_{self.table_name}"
        acl_table = "read_acl"
        if self.table_name == "docker_job" or self.table_name == "storage_policy":
            acl_table = "write_acl"
        self.create_view_stmt = f"""
            CREATE DEFINER = miranda_internal@localhost
            VIEW {self.view} AS
                        (WITH userid (uid) AS (SELECT id FROM users WHERE CONCAT('miranda_',username) = CURRENT_MIRANDA_USER()),
                            owned (mid) AS (SELECT m.id FROM metadata m
                                INNER JOIN users u ON m.created_by_id=u.id
                                INNER JOIN userid ON userid.uid = u.id
                                ),
                            acl_groups (mid) AS (SELECT m.id FROM metadata m
                                INNER JOIN {acl_table} a ON a.wob_mid=m.id
                                INNER JOIN group_maps g ON g.gid = a.gid
                                INNER JOIN users u ON u.id = g.uid
                                INNER JOIN userid ON userid.uid = u.id)
                            {self.select_projection_stmt}
                                        FROM (SELECT owned.mid AS mid FROM owned
                                            UNION
                                            SELECT acl_groups.mid AS mid FROM acl_groups) AS mt
                                        INNER JOIN metadata m ON m.id = mt.mid
                                        INNER JOIN {self.table_name} t ON t.metadata_id = m.id WHERE m.deleted=0)"""
        # print ("*** "+self.create_view_stmt)
        self.grant_view_stmt = f"GRANT SELECT ON {self.view} TO `%s`@`%`"
        with con.cursor() as cur:
            cur.execute(f"DROP VIEW IF EXISTS {self.view}")
            con.commit()
            cur.execute(self.create_view_stmt)
            con.commit()

    def make_update_sp(self, con):
        """Create a SP for updating the workflow object using SQL"""
        set_stmts = ""
        match = r"t\.`?(?P<field>\w*)`?\s[Aa][Ss].*"
        # Create list of updatable fields
        field_list = [
            re.sub(match, r"\g<field>", k[1])
            for k in self.orm.items()
            if k[1].startswith("t.")
        ]
        set_stmts = ""
        for field in field_list:
            convert_stmt = f"SET @update_{field} = CONVERT(FROM_BASE64(@update_{field}) USING UTF8MB4);"
            if field in self.default_value.keys():
                # check if type of the field is integer
                if isinstance(self.default_value[field], int) or isinstance(
                    self.default_value[field], float
                ):
                    convert_stmt = ""
            set_stmts += f"""
SELECT json_extract(@c,'$[0].{field}') INTO @update_{field};
SET @update_{field} = TRIM(BOTH '"' FROM @update_{field});
{convert_stmt}
IF @update_{field} IS NOT NULL THEN
    IF CHAR_LENGTH(@sets) > 4 THEN
      SET @prefix = ', ';
    END IF;
    SET @sets = CONCAT(@sets,@prefix,'t.',"`{field}`= @update_{field}");
END IF;

"""
        self.make_update_sp_stmts = f"""
DROP PROCEDURE IF EXISTS sp_update_{self.table_name};
---
CREATE DEFINER=`miranda_internal`@`localhost` PROCEDURE `sp_update_{self.table_name}`(IN oid INT,IN change_json MEDIUMTEXT) NOT DETERMINISTIC MODIFIES SQL DATA
BEGIN
  DECLARE db_user VARCHAR(40);
  DECLARE m_id INT;
  SET db_user = CURRENT_MIRANDA_USER();
  SET @c = TRIM(BOTH "'" FROM change_json);

  SELECT json_extract(@c,"$[0].name") INTO @update_name;
  SET @update_name = TRIM(BOTH '"' FROM @update_name);
  SET @update_name = CONVERT(FROM_BASE64(@update_name) USING UTF8MB4);
  SET @sets = "";
  SET @prefix = "SET ";
  IF @update_name IS NOT NULL THEN
    SET @sets = CONCAT(@sets,@prefix,"m.name= @update_name");
  END IF;

  SELECT json_extract(@c,"$[0].description") INTO @update_desc;
  SET @update_desc = TRIM(BOTH '"' FROM @update_desc);
  SET @update_desc = CONVERT(FROM_BASE64(@update_desc) USING UTF8MB4);
  IF @update_desc IS NOT NULL THEN
    IF CHAR_LENGTH(@sets) > 4 THEN
      SET @prefix = ", ";
    END IF;
    SET @sets = CONCAT(@sets,@prefix, "m.description= @update_desc");
  END IF;

  SELECT json_extract(@c,"$[0].cloned_from_id") INTO @update_cloned_from_id;
  IF @update_cloned_from_id IS NOT NULL THEN
    IF CHAR_LENGTH(@sets) > 4 THEN
      SET @prefix = ", ";
    END IF;
    SET @sets = CONCAT(@sets,@prefix, "m.cloned_from_id= @update_cloned_from_id");
  END IF;

  SELECT json_extract(@c,"$[0].deleted") INTO @update_deleted;
  SET @update_deleted = TRIM(BOTH '"' FROM @update_deleted);
  SET @update_deleted = CONVERT(FROM_BASE64(@update_deleted) USING UTF8MB4);
  IF @update_deleted IS NOT NULL THEN
    IF CHAR_LENGTH(@sets) > 4 THEN
      SET @prefix = ", ";
    END IF;
    SET @sets = CONCAT(@sets,@prefix, "m.deleted= @update_deleted");
  END IF;

  SELECT json_extract(@c,"$[0].status") INTO @update_status;
  SET @update_status = TRIM(BOTH '"' FROM @update_status);
  SET @update_status = CONVERT(FROM_BASE64(@update_status) USING UTF8MB4);
  IF @update_status IS NOT NULL THEN
    IF CHAR_LENGTH(@sets) > 4 THEN
      SET @prefix = ", ";
    END IF;
    SET @sets = CONCAT(@sets,@prefix, "m.status= @update_status");
  END IF;

  IF CHAR_LENGTH(@sets) > 4 THEN
      SET @prefix = ", ";
  END IF;
  SET @sets = CONCAT(@sets,@prefix, "m.last_updated= CURRENT_TIMESTAMP");

  {set_stmts}

  WITH userid (uid) AS (SELECT id FROM users WHERE CONCAT('miranda_',username) = CURRENT_MIRANDA_USER()),
    owned (mid) AS (SELECT m.id FROM metadata m
                          INNER JOIN users u ON m.created_by_id=u.id
                          INNER JOIN userid ON userid.uid = u.id
                          INNER JOIN {self.table_name} t ON t.metadata_id=m.id
                    WHERE t.id = oid),
    acl_groups (mid) AS (SELECT m.id FROM metadata m
                          INNER JOIN write_acl a ON a.wob_mid=m.id
                          INNER JOIN group_maps g ON g.gid = a.gid
                          INNER JOIN users u ON u.id = g.uid
                          INNER JOIN userid ON userid.uid = u.id
                          INNER JOIN {self.table_name} t ON t.metadata_id=m.id
                         WHERE t.id = oid)
  SELECT DISTINCT mid FROM (SELECT owned.mid AS mid FROM owned
                        UNION
                        SELECT acl_groups.mid AS mid FROM acl_groups
                    ) AS mt
        INTO m_id;
  SET @stmt= concat("UPDATE {self.table_name} t INNER JOIN metadata m ON m.id = t.metadata_id ",@sets," WHERE m.id= ?");
  SELECT @stmt;
  SET @p1=m_id;
  PREPARE `dynstmt` FROM @stmt;
  EXECUTE `dynstmt` USING @p1;
  DEALLOCATE PREPARE `dynstmt`;
  SET @stmt = NULL;
  SET @sets = NULL;
  SET @prefix = NULL;
END"""
        # {set_stmts}
        with con.cursor() as cur:
            for stmt in self.make_update_sp_stmts.split("---"):
                # print (stmt)
                cur.execute(stmt)
            con.commit()

    def _load_from_id(self, sc: Security_context, id):
        """Loads the data of a workflow object by object id using an ACL aware SQL VIEW"""
        found = False
        if id < 0:
            return
        try:
            con = sc.connect()
            cursor = con.cursor()
            sql_data = (id,)
            if sc.require_admin:
                cursor.execute(self.sql_load_stmt, sql_data)
            else:
                cursor.execute(self.v_sql_load_stmt, sql_data)
            self.change_tracking_enabled = False
            for r in cursor:
                found = True
                for i, name in enumerate(self.orm.keys()):
                    low_name = name.lower()
                    val = r[i]
                    if low_name in self.default_value.keys():
                        if isinstance(self.default_value[low_name], int):
                            try:
                                val = int(r[i])
                            except Exception as e:
                                logger.error(f"Error loading from id: {e}")
                                logger.warning(
                                    f"{low_name} is not an integer. Retaining identity."
                                )
                                val = r[i]
                        elif isinstance(self.default_value[low_name], float):
                            try:
                                val = float(r[i])
                            except Exception as e:
                                logger.error(f"Error loading from id: {e}")
                                logger.warning(
                                    f"{low_name} is not a float. Retaining identity."
                                )
                                val = r[i]
                    setattr(self, low_name, val)
                    # print ("DEBUG: load_from_id: {} = {} ".format(name.lower(),str(r[i])))
            cursor.close()
            self.change_tracking_enabled = True
        except mysql.connector.ProgrammingError as err:
            logger.error(err.msg)
            print(err.errno)
            print(err.sqlstate)
            print(err.msg)
        except mysql.connector.Error as err:
            logger.error(err)
        if not found:
            mystr = f"{self.table_name}: No such ID {id}"
            self.id = -1
            logger.error(mystr)
            # TODO raise MirandaExceptionNoSuchID(id)
        self.change_tracking_enabled = True

    def _load_from_metadata_id(self, sc: Security_context, metadata_id, user_id=-1):
        """Loads the data of a workflow object by metadata_id using an ACL aware SQL VIEW"""
        try:
            self.id == -1
            con = sc.connect()
            cursor = con.cursor()
            sql_data = (metadata_id,)
            if sc.require_admin:
                if user_id == -2:
                    sql_data = (metadata_id,)
                    cursor.execute(self.sql_find_by_metadata_id_all_users, sql_data)
                else:
                    if user_id != -1:
                        sql_data = (metadata_id, user_id)
                    else:
                        sql_data = (metadata_id, sc.id)
                    cursor.execute(self.v_sql_find_by_metadata_id, sql_data)
            else:
                # If this isn't a privileged account the userid is
                # derived from the SQL IF(CURRENT_ROLE()='NONE', CURRENT_USER(), CURRENT_ROLE()) function as defined the SQL VIEW
                cursor.execute(self.v_sql_find_by_metadata_id, sql_data)
            self.change_tracking_enabled = False
            for r in cursor:
                self.change_tracking_enabled = False
                for i, name in enumerate(self.orm.keys()):
                    low_name = name.lower()
                    val = r[i]
                    if low_name in self.default_value.keys():
                        if isinstance(self.default_value[low_name], int):
                            try:
                                val = int(r[i])
                            except Exception as e:
                                logger.error(f"Error loading from metadata id: {e}")
                                logger.warning(
                                    f"{low_name} is not an integer. Retaining identity."
                                )
                                val = r[i]
                        elif isinstance(self.default_value[low_name], float):
                            try:
                                val = float(r[i])
                            except Exception as e:
                                logger.error(f"Error loading from metadata id: {e}")
                                logger.warning(
                                    f"{low_name} is not a float. Retaining identity."
                                )
                                val = r[i]
                    setattr(self, low_name, val)
                self.change_tracking_enabled = True
                # print ("DEBUG: load_from_id: {} = {} ".format(name.lower(),str(r[i])))
            cursor.close()
        except mysql.connector.ProgrammingError as err:
            logger.error(err.msg)
            # print(err.errno)
            # print(err.sqlstate)
            # print(err.msg)
        except mysql.connector.Error as err:
            logger.error(err)
        self.change_tracking_enabled = True

    def _load_from_name(self, con, name, user_id):
        """TODO Is anyone using this?"""
        try:
            cursor = con.cursor()
            sql_data = (name,)
            cursor.execute(self.v_sql_search_stmt, sql_data, user_id)
            for r in cursor:
                for i, name in enumerate(self.orm.keys()):
                    low_name = name.lower()
                    val = r[i]
                    if low_name in self.default_value.keys():
                        if isinstance(self.default_value[low_name], int):
                            try:
                                val = int(r[i])
                            except Exception as e:
                                logger.error(f"Error loading from name: {e}")
                                logger.warning(
                                    f"{low_name} is not an integer. Retaining identity."
                                )
                                val = None
                        elif isinstance(self.default_value[low_name], float):
                            try:
                                val = float(r[i])
                            except Exception as e:
                                logger.error(f"Error loading from name: {e}")
                                logger.warning(
                                    f"{low_name} is not a float. Retaining identity."
                                )
                                val = None
                    setattr(self, low_name, val)
                    # print ("DEBUG: load_from_id: {} = {} ".format(name.lower(),str(r[i])))
            cursor.close()
        except mysql.connector.ProgrammingError as err:
            logger.error(err.msg)
            # print(err.errno)
            # print(err.sqlstate)
            # print(err.msg)
        except mysql.connector.Error as err:
            logger.error(err)

    def _load_from_resultset(self, rs):
        """Loads the data of a workflow object from a resultset"""
        try:
            self.id == -1
            self.change_tracking_enabled = False
            for i, name in enumerate(self.orm.keys()):
                low_name = name.lower()
                val = rs[i]
                if low_name in self.default_value.keys():
                    if isinstance(self.default_value[low_name], int):
                        try:
                            val = int(rs[i])
                        except Exception as e:
                            logger.error(f"Error loading from resultset: {e}")
                            logger.warning(
                                f"{low_name} is not an integer. Retaining identity."
                            )
                            val = rs[i]
                    elif isinstance(self.default_value[low_name], float):
                        try:
                            val = float(rs[i])
                        except Exception as e:
                            logger.error(f"Error loading from resultset: {e}")
                            logger.warning(
                                f"{low_name} is not a float. Retaining identity."
                            )
                            val = rs[i]
                setattr(self, low_name, val)
            self.change_tracking_enabled = True
        # print ("DEBUG: load_from_id: {} = {} ".format(name.lower(),str(r[i])))
        except mysql.connector.ProgrammingError as err:
            logger.error(err.msg)
            # print(err.errno)
            # print(err.sqlstate)
            # print(err.msg)
        except mysql.connector.Error as err:
            logger.error(err)
        self.change_tracking_enabled = True

    def _load_from_resultset_dict(self, row):
        """Loads the data of a workflow object from a resultset"""
        filtered_orm = {}
        for k, v in self.orm.items():
            if k in row or k in self.metadata.keys():
                filtered_orm[k] = v
        self.orm = filtered_orm
        self.create_mapping(filtered_orm, self.table_name)
        try:
            self.id == -1
            self.change_tracking_enabled = False
            for i, name in enumerate(self.orm.keys()):
                low_name = name.lower()
                val = row[low_name]
                if low_name in self.default_value.keys():
                    if isinstance(self.default_value[low_name], int):
                        try:
                            val = int(row[low_name])
                        except Exception as e:
                            logger.error(f"Error loading from resultset dict: {e}")
                            logger.warning(
                                f"{low_name} is not an integer. Retaining identity."
                            )
                            val = row[low_name]
                    elif isinstance(self.default_value[low_name], float):
                        try:
                            val = float(row[low_name])
                        except Exception as e:
                            logger.error(f"Error loading from resultset dict: {e}")
                            logger.warning(
                                f"{low_name} is not a float. Retaining identity."
                            )
                            val = row[low_name]
                setattr(self, low_name, val)
            self.change_tracking_enabled = True
        # print ("DEBUG: load_from_id: {} = {} ".format(name.lower(),str(r[i])))
        except mysql.connector.ProgrammingError as err:
            logger.error(err.msg)
            # print(err.errno)
            # print(err.sqlstate)
            # print(err.msg)
        except mysql.connector.Error as err:
            logger.error(err)
        self.change_tracking_enabled = True

    def __repr__(self, format: str = None):
        """Regulating how the workflow object is displayed when serialized."""
        if format is not None and format not in ["dict", "json", "jdict"]:
            raise ValueError(
                "Invalid format parameter. Valid values are 'dict','json','jdict'"
            )

        if self.id == -1:
            return "Workflow object is not initialized."

        table = []
        table.append(["class", self.__class__.__name__])
        pol = get_object_view_representation_policy() if format is None else format

        # a smarter implementation of "dict" that properly unpacks json and non-string types
        # dict remains unchanged for backwards compatibility reasons. this should be the default moving forward.
        if pol == "jdict":
            d = {}
            for k in self.orm:
                v = getattr(self, k)
                # unpack json strings, questionable way to check IF its json but it works for now
                if isinstance(v, str) and (
                    (v.startswith("{") and v.endswith("}"))
                    or (v.startswith("[") and v.endswith("]"))
                ):
                    v = json.loads(v)
                d[k] = v
            if hasattr(self, "groups"):
                d["groups"] = getattr(self, "groups")
            if "description" not in d:
                d["description"] = ""
            d["class"] = self.__class__.__name__
            return d

        for v in self.orm:
            table.append([v, str(getattr(self, v))])
        # If a list of group acls was loaded; include it in the representation
        table.append(["groups", getattr(self, "groups", [])])

        if pol == "dict":
            d = {}
            for r in table:
                d[r[0]] = r[1]
            return d
        if pol == "json":
            k = json.dumps(table)
            return k
        return tabulate(table, tablefmt=get_object_view_representation_policy())

    def create_sql_delete_stmt(self, objids_array, user_id):
        """Helper function"""
        return (
            "DELETE FROM "
            + self.table_name
            + " AS t WHERE t.id IN ("
            + ",".join(objids_array)
            + ")"
        )

    def admin_update(self, sc):
        """Connects to the database and updates all fields with new values. ACL doesn't matter. Requires admin sctx."""
        try:
            assert self.id != -1, "Object does not have an ID yet and can't be updated."
            con = sc.connect()
            cursor = con.cursor()
            for obj, db in self.orm.items():
                if db.startswith("t."):
                    field_name = [x for x in db.split(" ")][0]
                    attribute_name = field_name[2:].strip("`")
                    if attribute_name not in self.changed_list:
                        continue
                    sql = "UPDATE {} AS t SET {} = %s WHERE t.id={}".format(
                        self.table_name, field_name, self.id
                    )
                    sql_data = (getattr(self, obj),)
                    # print ("DEBUG : update : {} [data= {} ]".format(sql,sql_data))
                    cursor.execute(sql, sql_data)
            sql = "UPDATE metadata SET Last_updated=NOW(), name=%s, description=%s, deleted=%s WHERE id=%s"
            sql_data = (self.name, self.description, self.deleted, self.metadata_id)
            cursor.execute(sql, sql_data)
            con.commit()
            cursor.close()
        except mysql.connector.ProgrammingError as err:
            logger.error(err.msg)
            # print(err.errno)
            # print(err.sqlstate)
            # print(err.msg)
        except mysql.connector.Error as err:
            logger.error(err)

    def update(self, sc):
        """Updates a workflow object through a ACL controlled SQL SP"""
        try:
            if self.id == -1 or len(self.changed_list) == 0:
                return  # This object doesn't have any db representation yet
            con = sc.connect()
            fields = [
                k
                for k, x in self.orm.items()
                if x.startswith("t.")
                and k not in ["id", "metadata_id"]
                and k in self.changed_list
            ]
            fields += [
                k
                for k in ["name", "description", "deleted", "status", "cloned_from_id"]
                if k in self.changed_list
            ]
            field_and_values = {}
            with con.cursor() as cur:
                for k in fields:
                    value = getattr(self, k)
                    if isinstance(value, str):
                        value = base64.b64encode(value.encode("utf-8")).decode("ascii")
                    elif isinstance(value, bytes):
                        value = base64.b64encode(value).decode("ascii")
                    elif isinstance(value, bool):
                        value = "1" if value else "0"
                        value = value = base64.b64encode(value.encode("utf-8")).decode(
                            "ascii"
                        )
                    field_and_values[k] = value

                # debug = f"DEBUG: calling miranda.sp_update_{self.table_name}({self.id}, '{json.dumps(field_and_values)}'"
                # print (debug)
                # cur.execute(f"SHOW CREATE PROCEDURE miranda.sp_update_{self.table_name}")
                # for rs in cur:
                #    proc = rs[0]
                #    proc = rs[2]
                #    print ("DEBUG:" , proc)
                j = json.dumps(field_and_values)
                cur.callproc(f"sp_update_{self.table_name}", [self.id, j])
                con.commit()
                # print("DEBUG: update changed_list: ", self.changed_list)
                # print ("DEBUG: fields_and_values: ", field_and_values)
                self.clear_changed_list()
                mids = []
                for result in cur.stored_results():
                    rows = result.fetchall()
                    for row in rows:
                        # print (f"DEBUG: {row}")
                        mids.append(row)
                return mids
        except Exception as e:
            print("=> ERROR: ", e)
            return []

    def create(self, con, name: str, description: str, **values):
        """Creates a workflow object through a ACL controlled SQL SP"""
        # Values are assumed to be in ORM order, excluding any metadata
        sql_data = [name, description]

        # find cloned_from_id in **values so we don't have to change the function signature
        if "cloned_from_id" in values and values["cloned_from_id"] is not None:
            sql_data.append(values["cloned_from_id"])
        else:
            sql_data.append(-1)

        # Insert parameters in correct
        for attr in self.wob_insert_projection:
            if attr in values.keys():
                sql_data.append(values[attr])
            elif attr in self.default_value:
                sql_data.append(self.default_value[attr])
            else:
                sql_data.append("")
        sql_data = tuple(sql_data)
        logger.debug(f"sp_create_{self.table_name}", sql_data)
        aid = -1
        metadata_id = -1
        with con.cursor() as cursor:
            cursor.callproc(f"sp_create_{self.table_name}", sql_data)
            con.commit()
            for result in cursor.stored_results():
                rows = result.fetchall()
                for row in rows:
                    # print (f"DEBUG: {row}")
                    aid = row[0]
                    metadata_id = row[1]
        setattr(self, "id", aid)
        setattr(self, "metadata_id", metadata_id)
        return aid, metadata_id
