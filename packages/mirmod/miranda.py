#
# Copyright (c) 2023,2024,2025 MainlyAI - contact@mainly.ai
#
import configparser
import traceback
import mysql.connector
import json
import dill as pickle

import networkx as nx
import sys
import re
import copy
from pathlib import Path
import requests
import os
import time
import importlib
from .security.security_context import Security_context
from .orm.base_orm import (
    Base_object_ORM,
    get_object_view_representation_policy as _get_object_view_representation_policy,
    set_object_view_representation_policy as _set_object_view_representation_policy,
)
from . import (
    Code_block,
    Compute_policy,
    Compute_resource_group,
    Dashboard,
    Deployment,
    Docker_image,
    Docker_job,
    Knowledge_object,
    Model,
    Project,
    Storage_policy,
    get_all_edge_labels,
)

__all__ = [
    "Code_block",
    "Compute_policy",
    "Compute_resource_group",
    "Dashboard",
    "Deployment",
    "Docker_image",
    "Docker_job",
    "Knowledge_object",
    "Model",
    "Project",
    "Storage_policy",
]

from .orm.metadata import _add_edge, _remove_all_edges
from mirmod.utils.logger import logger
from . import object_to_table, table_to_object
from .execution_context import get_execution_context, Execution_context_api
from .miranda_git import git_clone_impl

pickle.settings["recurse"] = True
pickle.load_types(pickleable=True, unpickleable=True)

PASSTHROUGH = "PASSTHROUGH"
TRANSMITTER = "TRANSMITTER"
TRANSMITTER_FIELD = "TRANSMITTER_FIELD"
RECEIVER = "RECEIVER"
RECEIVER_FIELD = "RECEIVER_FIELD"
COMPILE_NODE_NAME = "MainlyAI model compile"  # TODO get from system maybe
WOB_CODE_BLOCK_HEADER = (
    "from mirmod.workflow_object import WOB\nwob = WOB()\n_DYNAMIC_NODE_ATTRS = {}\n"
)

# Return values for the exception handler
F_PROCEED = 0
F_NEXT_ELEMENT = 1
F_EXIT = 2
F_TRY_AGAIN = 3
F_RESTART = 4
F_RESTART_AND_REINIT = 5


class WOBInstanceException(Exception):
    pass


class SkipWOBInstanceException(Exception):
    pass


def get_test_config(test_files_path="."):
    """
    If you have choosen a testuser password different than the default, you can create a test config file in the pytest
    directory and the test files will use this config file.
    """
    try:
        with open(test_files_path + "/test_config.json", "r") as f:
            return json.load(f)
    except Exception:
        pass
    with open(test_files_path + "/test_config.json", "w+") as f:
        default_data = {
            "test": {"username": "testuser", "password": "pass"},
            "admin": {"username": "testuser", "password": "pass"},
        }
        f.write(json.dumps(default_data))
        return default_data


def get_object_view_representation_policy():
    return _get_object_view_representation_policy()


def set_object_view_representation_policy(p):
    _set_object_view_representation_policy(p)


mod_path = Path(__file__).parent
system_path = Path(__file__).parent.parent
tables_relative_path = "setup/db/tables"


def get_global_system_path():
    return system_path


def _ident(a):
    b = []
    for r in a.split("\n"):
        b.append("   " + r + "\n")
    return "".join(b)


def read_acl_grant_wob_to_group(cursor, wob_mid, gid):
    # Call the stored procedure to grant the wob to the group
    try:
        cursor.callproc("sp_read_acl_grant_wob_to_group", (wob_mid, gid))
        for result in cursor.stored_results():
            result.fetchall()
    except mysql.connector.IntegrityError as err:
        logger.debug("read_acl_grant_wob_to_group: IntegrityError: %s", err)
        pass  # ignore duplicate entries
    except Exception as e:
        print("read_acl_grant_wob_to_group: Error: ", e)


def write_acl_grant_wob_to_group(cursor, wob_mid, gid):
    # Call the stored procedure to grant the wob to the group
    try:
        cursor.callproc("sp_write_acl_grant_wob_to_group", (wob_mid, gid))
        for result in cursor.stored_results():
            result.fetchall()
    except mysql.connector.IntegrityError as err:
        logger.debug("write_acl_grant_wob_to_group: IntegrityError: %s", err)
        pass  # ignore duplicate entries
    except Exception as e:
        print("write_acl_grant_wob_to_group: Error: ", e)


def copy_ko_acls(cursor, ko: Knowledge_object, wob) -> tuple:
    """
    Copy the read and write ACLs from the ko to the wob.
    Args:
        cursor: A database cursor
        ko: The knowledge object to copy the ACLs from
        wob: The wob to copy the ACLs to
    Returns:
        The number of read ACLs copied and
        the number of write ACLs copied as a tuple.
    """
    # Get all groups from the group_maps table which the wob user is a member of and which also exists in the
    # read_acls table. If there's no group then the ko isn't shared and we can ignore this step.

    #
    # Copy read ACLs
    #
    sql = "SELECT gid,wob_mid FROM v_gid_from_read_acls WHERE wob_mid=%s"
    cursor.execute(sql, (ko.metadata_id,))
    groups = cursor.fetchall()
    if len(groups) == 0:
        return 0, 0
    for gid, _ in groups:
        read_acl_grant_wob_to_group(cursor, wob.metadata_id, gid)
    rc = len(groups)

    #
    # Copy write ACLs
    #
    try:
        sql = "SELECT gid,wob_mid FROM v_gid_from_write_acls WHERE wob_mid=%s"
        cursor.execute(sql, (ko.metadata_id,))
        groups = cursor.fetchall()
        # print("DEBUG: copy_ko_acls: ko.metadata_id= {} wob.metadata_id= {} groups = {}".format(ko.metadata_id, wob.metadata_id, groups))
        if len(groups) == 0:
            return 0, rc
        for gid, _ in groups:
            # print("DEBUG: write_acl_grant_wob_to_group: wob = ", wob.metadata_id, "gid = ", gid)
            write_acl_grant_wob_to_group(cursor, wob.metadata_id, gid)
        return len(groups), rc
    except Exception as e:
        logger.error("copy_ko_acls: Error: %s", e)
        return 0, rc


def copy_acls(sc: Security_context, src_wob, dest_wob):
    """Copy the read and write ACLs from the src_wob to the dest_wob.
    Args:
        sc: The security context
        src_wob: The source wob
        dest_wob: The destination wob
    Returns:
        The number of read ACLs copied and
        the number of write ACLs copied as a tuple.
    """
    # Get all groups from the group_maps table which the wob user is a member of and which also exists in the
    # read_acl table. If there's no group then the wob isn't shared and we can ignore this step.
    #
    # Copy read ACLs
    #
    con = sc.connect()
    read_copied = 0
    with con.cursor() as cur:
        sql = "SELECT gid,wob_mid FROM v_gid_from_read_acls WHERE wob_mid=%s"
        cur.execute(sql, (src_wob.metadata_id,))
        groups = cur.fetchall()
        read_copied = len(groups)
        for gid, _ in groups:
            # TODO: bulk grant
            read_acl_grant_wob_to_group(cur, dest_wob.metadata_id, gid)

    write_copied = 0
    with con.cursor() as cur:
        sql = "SELECT gid,wob_mid FROM v_gid_from_write_acls WHERE wob_mid=%s"
        cur.execute(sql, (src_wob.metadata_id,))
        groups = cur.fetchall()
        write_copied = len(groups)
        for gid, _ in groups:
            # TODO: bulk grant
            write_acl_grant_wob_to_group(cur, dest_wob.metadata_id, gid)
    return read_copied, write_copied


def create_wob(
    ko: Knowledge_object | Security_context,
    name: str = "No name",
    description: str = "",
    inherit_acls=True,
    wob_type="CODE",
):
    is_direct_context = isinstance(ko, Security_context)
    sc = ko.sctx if not is_direct_context else ko
    con = sc.connect()  # make sure we have a live connection or create a new one.

    wob = table_to_object(wob_type)(sc, id=-1)
    id, metadata_id = wob.create(con, name, description)
    con.commit()
    wob = table_to_object(wob_type)(sc, id)

    # If ko is a Knowledge_object, then link it to the wob
    if not is_direct_context:
        link(sc, ko, wob)

        if inherit_acls:
            # with sc.connect() as con:
            con = sc.connect()
            with con.cursor() as cursor:
                copy_ko_acls(cursor, ko, wob)
                con.commit()
    return wob


class Bad_code:
    The_code_could_not_compile = True


def create_security_context(
    user_name=None,
    auth_string="",
    auth_from_config=False,
    system_path=None,
    temp_token=None,
    auth_string_is_already_hashed=False,
    pool_size: int = None,
):
    if system_path is None:
        system_path = get_global_system_path()
    try:
        sc = Security_context(
            user_name,
            auth_string,
            auth_from_config=auth_from_config,
            system_path=system_path,
            temp_token=temp_token,
            auth_string_is_already_hashed=auth_string_is_already_hashed,
            pool_size=pool_size,
        )
        return sc
    except Exception as e:
        logger.error(
            "Miranda was unable to create a Security_context. The reason could be that the miranda database is unavailable."
        )
        logger.error(e)
        exit(-1)


def find_any_by_type(
    sc: Security_context, ot: str, limit=0, offset=0, fields: list[str] | None = None
):
    """
    Find all objects for a given type
    :param sc: Security Context
    :param ot: given type (e.g. datastream, model, etc)
    :return:
    """

    ot = ot.lower()
    if ot not in ([x.lower() for x in get_all_edge_labels()]):
        logger.error(f"Unknown type {ot}")
        raise Exception("ERROR: Unknown type is given: {}".format(ot))
    try:
        con = sc.connect()
        cursor = con.cursor(buffered=True, dictionary=True)

        ob_cls = table_to_object(ot)
        tmpl_ob = ob_cls(sc)
        sql = (
            tmpl_ob.get_projection(fields)
            if fields is not None
            else f"SELECT * FROM v_{ot}"
        )
        if limit > 0:
            sql += f" LIMIT {limit} OFFSET {offset}"
            sql_data = (limit, offset)
            cursor.execute(sql, sql_data)
        else:
            cursor.execute(sql)

        for row in cursor:
            ob = ob_cls(sc)
            ob._load_from_resultset_dict(row)
            yield ob

        cursor.close()
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


def find_object_by_name(
    sc: Security_context, name: str, type: str = "CODE", user_id=-1
):
    """Iterate over all workflow objects and compare their name using a LIKE where-clause. Any found object is returned using a yield statement."""
    ko = table_to_object(type)(sc, id=-1)
    try:
        # with sc.connect() as con:
        con = sc.connect()
        cursor = con.cursor()
        if sc.require_admin:
            if user_id == -1:
                user_id = sc.id
            sql_data = (name, user_id)
            cursor.execute(ko.sql_search_stmt, sql_data)
        else:
            sql_data = (name,)
            cursor.execute(ko.v_sql_search_stmt, sql_data)

        # print ("DEBUG: {}".format(ko.sql_search_stmt))
        # TODO: use bulk fetch
        for r in cursor:
            # Construct the Knowledge object using ORM
            ko = table_to_object(type)(sc, id=-1)
            for i, name in enumerate(ko.orm.keys()):
                setattr(ko, name.lower(), r[i])
                # DEBUG print (name+ "=" + str(r[i]))
            yield ko
            logger.info(f"Found workflow object {ko.name}")
        cursor.close()
    except mysql.connector.ProgrammingError as e:
        logger.error(e.msg)
    except mysql.connector.Error as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        pass


def find_object_by_id(sc: Security_context, id: int, type: str = "CODE"):
    # return an instance of the object with the given id and type
    return table_to_object(type)(sc, id=id)


def delete_object(obj, objid_array=None, cascading=False, hard=True):
    """Delete a Base_object_ORM by ID from the database. If an array of IDs is supplied then all corresponding objects will be deleted."""
    sctx = obj.sctx
    try:
        con = sctx.connect()
        cursor = con.cursor(buffered=True)

        if cascading and objid_array:
            # print ("API error: cascading and objid_array can't be true at once!")
            logger.info("API error: cascading and objid_array can't be true at once!")
            return 0
        if cascading:
            # Drop all references to this knowledge object
            # TODO don't delete the entire KO if the obj isn't a KO
            if hard:
                cursor.callproc("sp_delete_graph_by_mid", [obj.metadata_id])
                for result in cursor.stored_results():
                    rows = result.fetchall()
                    logger.debug("hard deleted rows: %s", rows)
                con.commit()
                affected = cursor.rowcount
                cursor.close()
                logger.info("Deleted number of {} objects".format(affected))
            else:
                cursor.callproc("sp_soft_delete_graph_by_mid", [obj.metadata_id])
                for result in cursor.stored_results():
                    rows = result.fetchall()
                    logger.debug("soft deleted rows: %s", rows)
                con.commit()
                affected = cursor.rowcount
                cursor.close()
                logger.info("Soft deleted number of {} objects".format(affected))

        if objid_array is not None and isinstance(objid_array, list):
            # Delete all objects with the id in the list
            sql_delete_by_ids_stmt = obj.create_sql_delete_stmt(objid_array)
            # print ("DEBUG : {}".sql_delete_by_ids_stmt)
            cursor.execute(sql_delete_by_ids_stmt)
            cursor.commit()
            return cursor.rowcount

        # sql_data = (obj.id, sctx.id)
        # cursor.execute(obj.sql_delete_by_id_stmt, sql_data)
        with con.cursor() as cur:
            if hard:
                cur.callproc("sp_delete_object", [obj.metadata_id])
                for result in cur.stored_results():
                    rows = result.fetchall()
                    logger.debug("hard deleted rows: %s", rows)
                con.commit()
                affected = cursor.rowcount
                cursor.close()
                logger.info("Deleted number of {} objects".format(affected))
            else:
                obj.deleted = True
                obj.update(sctx)
                affected = 1
        return affected
    except mysql.connector.ProgrammingError as e:
        logger.error(e.msg)
    except mysql.connector.Error as e:
        logger.error(e)


def create_graph(
    ko: Knowledge_object,
    materialize=False,
    drop_storage_children=True,
    drop_ko=False,
    include_child_kos=False,
    repr=True,
    fields: dict[list[str]] = {},
    resolve_subscribers=True,
):
    try:
        g = nx.DiGraph()
        set_object_view_representation_policy("dict")
        g.add_node(
            ko.metadata_id,
            type=ko.table_name,
            metadata_id=ko.metadata_id,
            id=ko.id,
            wob=(ko.__repr__() if repr else ko) if materialize else None,
        )
        n = int(ko.metadata_id)
        sc = ko.sctx
        con = sc.connect()
        # get all metadata ids which are connected to the ko
        mids = []
        with con.cursor() as cur:
            if include_child_kos:
                cur.callproc("sp_select_graph_by_mid", [n, 10])
            else:
                cur.callproc("sp_select_single_graph_by_mid", [n, 10])

            for result in cur.stored_results():
                rows = result.fetchall()
                for row in rows:
                    mids.append(row)
            mids = set(mids)
            with con.cursor(dictionary=True) as cur2:
                cached = {}
                if len(mids) > 0:
                    # mid[1] = src_id, mid[3] = dest_id

                    sql = "SELECT * FROM v_code"
                    if fields.get("CODE", None) is not None:
                        code = Code_block(sc, -1)
                        sql = code.get_projection(fields["CODE"])
                    sql += " WHERE metadata_id IN ({})".format(
                        ",".join([str(mid[3]) for mid in mids])
                    )
                    cur2.execute(sql)
                    for row in cur2.fetchall():
                        cached[row["metadata_id"]] = row

                    sql = "SELECT * FROM v_docker_job"
                    if fields.get("DOCKER_JOB", None) is not None:
                        docker_job = Docker_job(sc, -1)
                        sql = docker_job.get_projection(fields["DOCKER_JOB"])
                    sql += " WHERE metadata_id IN ({})".format(
                        ",".join([str(mid[3]) for mid in mids])
                    )
                    cur2.execute(sql)
                    for row in cur2.fetchall():
                        cached[row["metadata_id"]] = row
            if resolve_subscribers:
                subscriber_mids = [
                    x["metadata_id"]
                    for x in cached.values()
                    if "update_policy" in x and x["update_policy"] == "SUBSCRIBE"
                ]
                # print("DEBUG: subscriber_mids = ", subscriber_mids)

                if len(subscriber_mids) > 0:
                    with con.cursor(dictionary=True) as cur2:
                        sql = "SELECT DISTINCT s.metadata_id, d.body, d.api FROM v_code s LEFT JOIN v_code d ON d.metadata_id = s.cloned_from_id WHERE s.metadata_id IN ({})".format(
                            ",".join([str(mid) for mid in subscriber_mids])
                        )
                        cur2.execute(sql)
                        for row in cur2.fetchall():
                            mid = row["metadata_id"]
                            if mid not in cached:
                                continue
                            print(row)
                            cached[mid]["body"] = row["body"]
                            try:
                                source_json = json.loads(row["api"])
                                patch_json = json.loads(cached[mid]["api"])
                                if (
                                    "attributes" in source_json
                                    and "attributes" in patch_json
                                ):
                                    for attr in source_json["attributes"]:
                                        for new_attr in patch_json["attributes"]:
                                            if "name" not in new_attr:
                                                continue
                                            if "value" not in new_attr:
                                                continue
                                            if attr["name"] == new_attr["name"]:
                                                attr["value"] = new_attr["value"]
                                cached[mid]["api"] = json.dumps(source_json)
                            except Exception as e:
                                print(f"Could not load Source API for {mid}", e)
                                cached[mid]["api"] = json.dumps(
                                    {
                                        "compiled": False,
                                        "error": "Could not load Source API",
                                    }
                                )

        def add_node(n: int, g: nx.DiGraph, type):
            if n not in g.nodes():
                ob = None
                if materialize:
                    ob_class = table_to_object(type)
                    if n in cached:
                        ob = ob_class(sc)
                        ob._load_from_resultset_dict(cached[n])
                    else:
                        if type == "DOCKER_JOB":
                            raise SkipWOBInstanceException()
                        ob = ob_class(sc, metadata_id=n)
                    if ob is None or ob.id == -1:
                        raise WOBInstanceException(
                            f"Could not load object type={type} mid={n}"
                        )
                    g.add_node(
                        n,
                        name=ob.name,
                        metadata_id=int(ob.metadata_id),
                        id=int(ob.id),
                        type=type.lower(),
                        wob=ob.__repr__() if repr else ob,
                    )
                else:
                    if type == "DOCKER_JOB":
                        raise SkipWOBInstanceException(f"type={type} mid={n}")
                    g.add_node(n, metadata_id=n, type=type.lower())

        for name, src_id, src_type, dest_id, dest_type, etl_id in mids:
            if drop_ko and src_type == "KNOWLEDGE_OBJECT":
                continue
            try:
                add_node(int(src_id), g, src_type)
                add_node(int(dest_id), g, dest_type)
                g.add_edge(src_id, dest_id)
            except WOBInstanceException as e:
                print("WARNING:", e)
                logger.error(e)
            except SkipWOBInstanceException:
                pass
            except Exception as e:
                print("ERROR:", e)
                pass

        if materialize:
            attrs = bulk_get_edge_attributes(sc, [f"{e[0]}-{e[1]}" for e in g.edges])
            for e0, e1, attr in attrs:
                g.edges[e0, e1]["attributes"] = attr
        # nx.set_edge_attributes(g,edge_prop,"etl_id")
        logger.info(f"Created graph for {ko.name}")
        if drop_ko:
            g.remove_node(ko.metadata_id)
        return g
    except mysql.connector.ProgrammingError as e:
        logger.error(e.msg)
        traceback.print_exc()
    except mysql.connector.Error as e:
        logger.error(e)
        traceback.print_exc()


def traverse_tree(
    ko: Knowledge_object, action, drop_ko=False, filter_type=lambda x: False
):
    """
    For every branch that is connected to ko, perform action(branch_node).
    """
    g = create_graph(ko, drop_ko=drop_ko)
    ct = 0
    ob = ko
    # Note: We don't include the root element
    # action(ob)
    # TODO: use bulk fetch
    for org, dest in nx.bfs_successors(g, ko.metadata_id):
        parent = table_to_object(g.nodes[org]["type"])(ko.sctx, metadata_id=org)
        if parent.id == -1:
            # print (f"DEBUG: traverse_tree: No object with mid = {org}")
            continue
        for n in dest:
            type = g.nodes[n]["type"]
            if filter_type(type):
                continue
            ob = table_to_object(type)(ko.sctx, metadata_id=n)
            if ob.id == -1:
                # print (f"DEBUG: traverse_tree: No object with mid = {n}")
                continue
            action(ob, parent)
            ct += 1
    return ct


def update_api(
    sc,
    wob,
    connector_type,
    connector,
    datatype,
    value=None,
    control=None,
    connectable=True,
    hidden=False,
    edge_text=None,
    recommendation=None,
):
    """Update the API of a workflow object."""
    wob = Code_block(sc, id=wob.id)
    if wob.id == -1:
        raise Exception(f"Could not find workflow object with id = {wob.id}")
    try:
        japi = json.loads(wob.api)
    except Exception:
        japi = {"attributes": []}

    if "attributes" not in japi:
        japi = {"attributes": []}
    found = False
    for attribute in japi["attributes"]:
        if (
            "name" not in attribute
            or "direction" not in attribute
            or "control" not in attribute
        ):
            continue
        if attribute["name"] == connector:
            attribute["kind"] = datatype
            if (
                attribute["direction"] == TRANSMITTER
                or attribute["direction"] == TRANSMITTER_FIELD
                or attribute["control"] is None
            ):
                attribute["value"] = None
            else:
                attribute["value"] = value
            if control is not None:
                attribute["control"] = control
            if connectable is not None:
                attribute["connectable"] = connectable
            if hidden is not None:
                attribute["hidden"] = hidden
            if edge_text is not None:
                attribute["edge_text"] = edge_text
            if recommendation is not None:
                attribute["recommendation"] = recommendation
            found = True

    if not found and control is not None:
        japi["attributes"].append(
            {
                "name": connector,
                "direction": connector_type,
                "kind": datatype,
                "value": value,
                "control": control,
                "connectable": connectable,
                "hidden": hidden,
                "edge_text": edge_text,
                "recommendation": recommendation,
            }
        )
    wob.api = json.dumps(japi)
    wob.update(sc)


def is_field(connector):
    """Mark the connector as a field connector by wrapping it in a tuple"""
    return (connector,)


def update_clone_api(sc, obj):
    """Update the API of a cloned object to match the original object."""
    if obj.cloned_from_id == -1:
        return
    original = table_to_object(obj.table_name)(sc, metadata_id=obj.cloned_from_id)
    if original.id == -1:
        return
    try:
        japi = json.loads(original.api)
    except Exception:
        japi = {"attributes": []}
    try:
        japi_clone = json.loads(obj.api)
    except Exception:
        japi_clone = {"attributes": []}
    for attribute in japi["attributes"]:
        found = False
        for attribute_clone in japi_clone["attributes"]:
            if "name" not in attribute or "direction" not in attribute:
                continue
            if attribute["name"] == attribute_clone["name"]:
                found = True
                break
        if not found:
            # Any missing attribute is added to the clone; nothing is removed.
            # No values are overwritten.
            japi_clone["attributes"].append(attribute)
    obj.api = json.dumps(japi_clone)
    obj.update(sc)


def link(
    sc,
    from_obj,
    to_obj,
    transmitter: str = None,
    receiver: str = None,
    datatype: str = None,
    verify_api: bool = True,
):
    """Connect two objects through an edge table. Knowledge objects can link to other knowledge objects or to workflow objects.
    Workflow objects can link to code blocks.

    Args:
     sc : A Security context
     from_obj : Any ORM object which serves as the source vertex in an edge.
     to_obj : Any ORM object which serves as the destination vertex in an edge.
     transmitter : The name of the transmitter connector
     receiver : The name of the receiver connector
     datatype : The datatype of the edge
    Return: Failure status
     False: Operation was successful
     True: Operation was a failure
    """
    is_transmitter_field = isinstance(transmitter, tuple)
    if is_transmitter_field:
        transmitter = transmitter[0]

    is_receiver_field = isinstance(receiver, tuple)
    if is_receiver_field:
        receiver = receiver[0]

    con = sc.connect()
    src_type, dest_type = from_obj.table_name.upper(), to_obj.table_name.upper()
    suggested_datatype, attr = None, None

    if (
        verify_api
        and transmitter
        and receiver
        and isinstance(from_obj, Code_block)
        and isinstance(to_obj, Code_block)
    ):
        suggested_datatype = _verify_and_get_datatype(
            from_obj,
            transmitter,
            TRANSMITTER,
            [TRANSMITTER, TRANSMITTER_FIELD, PASSTHROUGH],
        )
        if suggested_datatype is None:
            return True

        receiver_datatype = _verify_and_get_datatype(
            to_obj, receiver, RECEIVER, [RECEIVER, RECEIVER_FIELD, PASSTHROUGH]
        )
        if receiver_datatype is None or (
            suggested_datatype and suggested_datatype != receiver_datatype
        ):
            logger.error(
                f"Datatype mismatch between ({from_obj.name} :: {transmitter}) and ({to_obj.name} :: {receiver})"
            )
            logger.error(
                f"Datatype of ({from_obj.name} :: {transmitter}) is '{suggested_datatype}'"
            )
            logger.error(
                f"Datatype of ({to_obj.name} :: {receiver}) is '{receiver_datatype}'"
            )
            return True

    if (
        isinstance(from_obj, Code_block)
        and isinstance(to_obj, Code_block)
        and verify_api
    ):
        datatype = _infer_datatype(
            datatype, suggested_datatype, from_obj, transmitter, to_obj, receiver
        )
        if datatype is None:
            return True

    try:
        # with sc.connect() as con:
        con = sc.connect()
        _add_edge(con, src_type, dest_type, from_obj.metadata_id, to_obj.metadata_id)
        con.commit()
    except Exception as e:
        logger.error(
            f"Failed to create edge from [{src_type}]{from_obj.name}::{transmitter} to [{dest_type}]{to_obj.name}::{receiver}",
            e,
        )
        pass

    if (
        transmitter is None
        or receiver is None
        or isinstance(from_obj, Knowledge_object)
    ):
        return False

    attr = get_edge_attribute(sc, from_obj, to_obj) or {}
    return _update_edge(
        sc,
        from_obj,
        to_obj,
        transmitter,
        receiver,
        datatype,
        is_transmitter_field,
        is_receiver_field,
        attr,
    )


def _verify_and_get_datatype(obj, connector, direction, valid_directions):
    """Helper function to verify and get the datatype from the object's API."""
    if obj.api:
        api = json.loads(obj.api)
        if "attributes" in api:
            attrs = [
                x
                for x in api["attributes"]
                if x["name"] == connector and x["direction"] in valid_directions
            ]
            if len(attrs) == 1:
                return attrs[0]["kind"]
            logger.error(
                f"No {direction.lower()} connector '{connector}' in API of {obj.name}"
            )
            logger.debug("attrs = %s", attrs)
            logger.debug("API = %s", api)
    return None


def _infer_datatype(
    datatype, suggested_datatype, from_obj, transmitter, to_obj, receiver
):
    """Helper function to handle datatype inference and validation."""
    if datatype is None:
        logger.warning(
            f"No datatype specified for edge between ({from_obj.name} :: {transmitter}) and ({to_obj.name} :: {receiver}), inferring '{suggested_datatype}' from API"
        )
        return suggested_datatype
    elif suggested_datatype and datatype != suggested_datatype:
        logger.error(
            f"Datatype mismatch between ({from_obj.name} :: {transmitter}) and ({to_obj.name} :: {receiver})"
        )
        logger.error(
            f"Datatype of ({from_obj.name} :: {transmitter}) is '{suggested_datatype}'"
        )
        logger.error(f"Datatype of ({to_obj.name} :: {receiver}) is '{datatype}'")
        return None
    return datatype


def _update_edge(
    sc,
    from_obj,
    to_obj,
    transmitter,
    receiver,
    datatype,
    is_transmitter_field,
    is_receiver_field,
    attr,
):
    """Helper function to update edge attributes and API."""
    if receiver not in attr or (
        transmitter == attr[receiver][0] and datatype == attr[receiver][1]
    ):
        attr[receiver] = [transmitter, datatype, is_transmitter_field]
        set_edge_attribute(sc, from_obj, to_obj, attr)
        _update_api(
            sc,
            from_obj,
            to_obj,
            transmitter,
            receiver,
            datatype,
            is_transmitter_field,
            is_receiver_field,
        )
        return False
    return False  # Edge update was successful


def _update_api(
    sc,
    from_obj,
    to_obj,
    transmitter,
    receiver,
    datatype,
    is_transmitter_field,
    is_receiver_field,
):
    """Helper function to update the API based on transmitter and receiver information."""
    if datatype == PASSTHROUGH:
        update_api(sc, from_obj, PASSTHROUGH, transmitter, datatype)
    else:
        update_api(
            sc,
            from_obj,
            TRANSMITTER_FIELD if is_transmitter_field else TRANSMITTER,
            transmitter,
            datatype,
        )
        update_api(
            sc,
            to_obj,
            RECEIVER_FIELD if is_receiver_field else RECEIVER,
            receiver,
            datatype,
        )


def unlink(
    sc: Security_context, from_obj, to_obj=None, transmitter=None, receiver=None
):
    """This function has three behaivours:
    1. If only from_obj is specified then all its edges are removed.
    2. If from_obj and to_obj are specified then the edge between them is removed.
    3. If from_obj, to_obj, transmitter and receiver are specified then only the specified transmitter and receiver are removed from the edge attribute.
      If the last attribute is removed then the edge is removed."""

    if to_obj is None:
        con = sc.connect()
        obj_id = to_obj.metadata_id
        try:
            _remove_all_edges(con, obj_id)
            con.commit()
        except mysql.connector.Error as e:
            logger.error(f"Error while removing all edges:{e}")
            return True  # Failure
        con.commit()
    else:
        if transmitter is None or receiver is None:
            delete_edge(sc, from_obj.metadata_id, to_obj.metadata_id)
        else:
            attr: dict = get_edge_attribute(sc, from_obj, to_obj)
            if attr is None:
                return False
            if receiver not in attr:
                return False
            tr = attr[receiver]
            if transmitter == tr[0]:
                del attr[receiver]  # remove the attribute
            if len(attr) == 0:  # if this was the last attribute then remove the edge
                delete_edge(sc, from_obj.metadata_id, to_obj.metadata_id)
            else:  # update the edge record with the remaining attributes
                set_edge_attribute(sc, from_obj, to_obj, attr)

    return False  # Success


def clone_object(
    sc,
    obj,
    new_name: str = None,
    new_description: str = None,
    copy_edges=False,
    copy_tags=False,
    set_cloned_from=True,
    update_policy="NEVER",
    ignore_tags=[],
):
    con = sc.connect()
    obj2 = copy.copy(obj)
    if new_name is not None:
        obj2.name = new_name
    if new_description is not None:
        obj2.description = new_description
    obj2.id = -1
    params = [k for k, v in obj2.orm.items() if v.startswith("t.")]
    d = {}
    for p in params:
        d[p] = getattr(obj, p)
    if set_cloned_from:
        d["cloned_from_id"] = obj.metadata_id
    if hasattr(obj2, "update_policy"):
        # override the update policy with the new value
        if obj.update_policy == "SUBSCRIBE":
            # This node is already a subscriber. When we subscribe to a subscriber, we also
            # copy the cloned_from_id. This ensures that we don't end up with long dependency chains.
            d["cloned_from_id"] = obj.cloned_from_id
        d["update_policy"] = update_policy
    if hasattr(obj2, "git"):
        d["git"] = ""  # Clear the git repo
    if hasattr(obj2, "git_branch"):
        d["git_branch"] = ""
    id, metadata_id = obj2.create(con, obj2.name, obj2.description, **d)
    con.commit()
    obj2._load_from_metadata_id(sc, metadata_id)
    if copy_edges:
        for inbound_wob in [o for o in find_wob_by_inbound_edges(sc, obj.metadata_id)]:
            link(sc, inbound_wob, obj2)
        for outbound_wob in [
            n for n in find_wob_by_outbound_edges(sc, obj.metadata_id)
        ]:
            link(sc, obj2, outbound_wob)
    if copy_tags:
        tags = find_tags_by_wob(sc, obj)
        if "tags" in tags:
            for t in tags["tags"]:
                if t not in ignore_tags:
                    # TODO: bulk tag object
                    tag_object(sc, obj2, t)
    return obj2


def provision_temporary_password(sc, current_miranda_password, admin=False):
    """
    This function can not be called as a client function because it relies on a local secret to be present.
    Args
      sc : The security context of the logged in user
      current_miranda_password : The current miranda password
    Returns:
      A string representing the temporary password for accessing the miranda database directly from a client.
    """
    raise Exception(
        "provision_temporary_password is deprecated. Use miranda_admin_ops.provision_proxy_account() instead."
    )


def has_edge(sc, src_id: int, dest_id: int) -> bool:
    """
    Returns True if there is an edge from src_id to dest_id, False otherwise.
    """
    con = sc.connect()
    with con.cursor() as cur:
        sql = "SELECT 1 FROM v_edges WHERE src_id = %s AND dest_id = %s LIMIT 1"
        cur.execute(sql, (src_id, dest_id))
        result = cur.fetchone()
        return result is not None


def delete_edge(sc: Security_context, from_mid: int, to_mid: int):
    # with sc.connect() as con:
    con = sc.connect()
    mids = []
    with con.cursor() as cur:
        cur.callproc("sp_unlink", [from_mid, to_mid])
        con.commit()
        for result in cur.stored_results():
            rows = result.fetchall()
            for row in rows:
                # print (f"DEBUG: {row}")
                mids.append(row)
    return mids


def get_edge_attribute(sc, src_ob, dest_ob):
    """
    Gets the edge attribute between two objects.
    Args:
        sc : The security context of the logged in user
        src_ob : The source object
        dest_ob : The destination object
    Returns:
        The edge attribute (an ETL_process object ID) between the two objects.
    """
    if not isinstance(src_ob, int):
        src_ob = src_ob.metadata_id
    if not isinstance(dest_ob, int):
        dest_ob = dest_ob.metadata_id
    con = sc.connect()
    sql = "SELECT e.attributes FROM v_edges e WHERE e.src_id = %s AND e.dest_id = %s"
    with con.cursor() as cur:
        cur.execute(sql, (src_ob, dest_ob))
        for rs in cur:
            try:
                j = json.loads(rs[0])
                return j
            except Exception as e:
                logger.error(
                    f"Failed to load edge attribute from {src_ob} to {dest_ob}", e
                )
                return None

    return None


def bulk_get_edge_attributes(sc, edge_keys):
    """
    Gets the edge attribute between two objects.
    Args:
        sc : The security context of the logged in user
        edge_keys : A list of edge_key string "src_id-dest_id"
    Returns:
        The edge attribute (an ETL_process object ID) between the two objects.
    """
    if len(edge_keys) == 0:
        return []

    con = sc.connect()
    placeholders = ", ".join(["%s"] * len(edge_keys))
    sql = f"SELECT e.src_id,e.dest_id,e.attributes FROM v_edges e WHERE e.edge_key in ({placeholders})"
    with con.cursor() as cur:
        cur.execute(sql, edge_keys)
        for rs in cur:
            try:
                if rs[2] is not None:
                    j = json.loads(rs[2])
                else:
                    j = None
                yield (rs[0], rs[1], j)
            except Exception as e:
                logger.error(
                    f"Failed to load edge attribute from {rs[0]} to {rs[1]}", e
                )
                yield (rs[0], rs[1], None)


def set_edge_attribute(sc: Security_context, src, dest, attributes={}):
    """
    Args:
        sc : The security context of the logged in user
        src : The source wob or metadata id of the source object
        dest : The destination wob or metadata id of the destination object
        etl : The etl object to use or the id
    """
    if not isinstance(src, int):
        src = src.metadata_id
    if not isinstance(dest, int):
        dest = dest.metadata_id
    # with sc.connect() as con:
    con = sc.connect()
    mids = []
    with con.cursor() as cur:
        cur.callproc("sp_set_edge_attribute", [src, dest, -1, json.dumps(attributes)])
        con.commit()
        for result in cur.stored_results():
            rows = result.fetchall()
            for row in rows:
                mids.append(row)
    return mids


def find_wob_by_outbound_edges(
    sc, mid: int, filter=lambda x: not isinstance(x, Knowledge_object), wob_type=None
):
    """
    Finds all objects that are children of the object with the given metadata id.
    Args:
        sc : The security context of the logged in user
        mid : The metadata id of the parent object
    Returns:
        A list of objects that are children of the parent object.
    """
    con = sc.connect()
    bulk_select_statements = {}
    with con.cursor(dictionary=True) as cur:
        if wob_type is not None:
            sql = """SELECT e.dest_id,e.dest_type FROM v_edges e INNER JOIN v_metadata m ON m.id=e.dest_id WHERE e.src_id = %s AND dest_type = %s"""
            cur.execute(sql, (mid, wob_type))
        else:
            sql = """SELECT e.dest_id,e.dest_type FROM v_edges e INNER JOIN v_metadata m ON m.id=e.dest_id WHERE e.src_id = %s"""
            cur.execute(sql, (mid,))
        for rs in cur:
            if rs["dest_type"] not in bulk_select_statements:
                bulk_select_statements[rs["dest_type"]] = []
            bulk_select_statements[rs["dest_type"]].append(rs["dest_id"])
        # print("DEBUG: find_wob_by_outbound_edges,bulk_select_statements = ",bulk_select_statements)
        for ob_table, ids in bulk_select_statements.items():
            if len(ids) == 0:
                continue
            sql = """SELECT * FROM v_{} WHERE metadata_id IN ({})""".format(
                ob_table.lower(), ",".join([str(id) for id in ids])
            )
            cur.execute(sql)
            for rs in cur:
                ob = table_to_object(ob_table)(sc)
                if len(rs) == 0:
                    continue
                ob._load_from_resultset_dict(rs)
                if filter is None or filter(ob):
                    yield ob


def find_wob_by_inbound_edges(
    sc, mid: int, filter=lambda x: not isinstance(x, Knowledge_object), wob_type=None
):
    """
    Finds all objects that are children of the object with the given metadata id.
    Args:
        sc : The security context of the logged in user
        mid : The metadata id of the parent object
    Returns:
        A list of objects that are children of the parent object.
    """
    sc.close()
    con = sc.connect()
    bulk_select_statements = {}
    with con.cursor() as cur:
        if wob_type is not None:
            sql = """SELECT e.src_id,e.src_type,m.name FROM v_edges e INNER JOIN v_metadata m ON m.id=e.src_id WHERE e.dest_id = %s AND src_type = %s"""
            cur.execute(sql, (mid, wob_type))
        else:
            sql = """SELECT e.src_id,e.src_type,m.name FROM v_edges e INNER JOIN v_metadata m ON m.id=e.src_id WHERE e.dest_id = %s"""
            cur.execute(sql, (mid,))
        for rs in cur:
            if rs[1] not in bulk_select_statements:
                bulk_select_statements[rs[1]] = []
            bulk_select_statements[rs[1]].append(rs[0])
        # print("DEBUG: find_wob_by_inbound_edges,bulk_select_statements = ",bulk_select_statements)
        for ob_table, ids in bulk_select_statements.items():
            if len(ids) == 0:
                continue
            sql = """SELECT * FROM v_{} WHERE metadata_id IN ({})""".format(
                ob_table.lower(), ",".join([str(id) for id in ids])
            )
            cur.execute(sql)
            for rs in cur:
                ob: Base_object_ORM = table_to_object(ob_table)(sc)
                ob._load_from_resultset(rs)
                if filter is None or filter(ob):
                    yield ob


def find_children(
    sc, mid: int, filter=lambda x: not isinstance(x, Knowledge_object), wob_type=None
):
    """
    Finds all objects that are children of the object with the given metadata id.
    Args:
        sc : The security context of the logged in user
        mid : The metadata id of the parent object
    Returns:
        A list of objects that are children of the parent object.
    """
    for ob in [
        o for o in find_wob_by_outbound_edges(sc, mid, filter=filter, wob_type=wob_type)
    ]:
        yield ob


def get_degree(sc: Security_context, wob):
    """Returns the number of inbound and outbound edges of a wob

    Parameters
    ----------
    sc : Security_context
    wob : either the metadata_id (int) of a wob or the wob (obj)

    Returns
    -------
    inbound_degree, outbound_degree
        the inbound_degree and the outbound_degree of the wob
    """
    metadata_id = wob if isinstance(wob, int) else wob.metadata_id
    try:
        con = sc.connect()
        with con.cursor() as cursor:
            sql = """
            SELECT
                SUM(IF(dest_id = %s, 1, 0)) AS inbound_edges,
                SUM(IF(src_id = %s, 1, 0)) AS outbound_edges
            FROM v_edges;
            """
            cursor.execute(sql, (metadata_id, metadata_id))
            rs = cursor.fetchone()
            cursor.close()
            con.close()
            return rs[0], rs[1]
    except mysql.connector.Error as err:
        logger.error(err)


def tag_object(sc: Security_context, wob, tag, public=False):
    """Tags an object with a tag

    Parameters
    ----------
    sc : Security_context
    wob : The workflow object to tag
    tag : str
        the tag to add to the object
    """
    try:
        con = sc.connect()
        sql_data = [object_to_table(wob), wob.metadata_id, tag]
        with con.cursor() as cursor:
            cursor.callproc("public_tag_object" if public else "tag_object", sql_data)
            con.commit()
            for result in cursor.stored_results():
                _ = result.fetchall()
                # ignore any rs
            con.commit()
            cursor.close()
    except mysql.connector.IntegrityError as err:
        logger.warning(f"IntegrityError: {err}")  # ignore duplicates
    except mysql.connector.Error as err:
        logger.error(err)


def untag_object(sc: Security_context, wob, tag, public=False):
    """Removes a tag from an object

    Args:
    sc : Security_context
    wob : The workflow object to untag
    tag : str
        the tag to remove from the object
    """
    # with sc.connect() as con:
    con = sc.connect()
    sql_data = [wob.metadata_id, tag]
    with con.cursor() as cursor:
        cursor.callproc("untag_object", sql_data)
        con.commit()
        for result in cursor.stored_results():
            _ = result.fetchall()
            # ignore any rs
        con.commit()


def find_wob_by_tag(sc, tag: str):
    """Returns a list of wobs that have been tagged with the given tag

    Args:
    sc : Security_context
    tag : str
        the tag to search for

    Returns:
        list: a list of wobs that have been tagged with the given tag
    """
    try:
        rs = []
        # with sc.connect() as con:
        con = sc.connect()
        user_id = sc.user_id()
        sql_data = [tag, user_id]
        with con.cursor() as cursor:
            sql = "SELECT * FROM vtag2metadata WHERE tag = %s AND user_id = %s"
            cursor.execute(sql, sql_data)
            rs = cursor.fetchall()
        return rs
    except mysql.connector.Error as err:
        logger.error(err)


def find_tags_by_wob(sc, ob_or_mid):
    """Returns a list of tags that have been applied to the given wob

    Args:
    sc : Security_context
    ob : Workflow object

    Returns:
        list: a list of tags that have been applied to the given wob
    """
    try:
        rs = []
        # with sc.connect() as con:
        con = sc.connect()
        if isinstance(ob_or_mid, int):
            sql_data = [
                ob_or_mid,
            ]
        else:
            sql_data = [
                ob_or_mid.metadata_id,
            ]
        with con.cursor() as cursor:
            sql = "SELECT * FROM v_tags_per_wob WHERE metadata_id = %s"
            cursor.execute(sql, sql_data)
            rows = cursor.fetchall()
            for rs in rows:
                try:
                    tags = json.loads(rs[0])
                    user_ids = json.loads(rs[1])
                    return {"tags": tags, "user_ids": user_ids}
                except Exception as e:
                    print(e)
        return rs
    except mysql.connector.Error as err:
        logger.error(err)


def find_tags_per_wobs(sc, wob_ids):
    """Returns a list of tags that have been applied to the given wob

    Args:
    sc : Security_context

    Returns:
        list: a list of tags that have been applied to the given wob
    """
    rs = {}
    if len(wob_ids) == 0:
        return {}

    try:
        # with sc.connect() as con:
        con = sc.connect()
        with con.cursor() as cur:
            sql = "SELECT * FROM v_tags_per_wob WHERE metadata_id IN ({})".format(
                ",".join([str(wob_id) for wob_id in wob_ids])
            )
            cur.execute(sql)
            rows = cur.fetchall()
            for row in rows:
                rs[row[2]] = {
                    "tags": json.loads(row[0]),
                    "user_ids": json.loads(row[1]),
                }
    except mysql.connector.Error as err:
        logger.error(err)

    return rs


def find_tags_per_all_ko(sc):
    """Returns a list of tags that have been applied to the given wob

    Args:
    sc : Security_context

    Returns:
        list: a list of tags that have been applied to the given wob
    """
    try:
        rs = []
        # with sc.connect() as con:
        con = sc.connect()
        with con.cursor() as cursor:
            sql = "SELECT * FROM v_tags_per_ko"
            cursor.execute(sql)
            rs = cursor.fetchall()
        return rs
    except mysql.connector.Error as err:
        logger.error(err)


def clone_project(
    sc,
    ko: Knowledge_object,
    new_parent_id: int = None,
    new_name: str | None = None,
    exclude_docker_job: bool = True,
):
    """Clones a project

    Args:
    sc : Security_context
    ko : Knowledge_object
        the project to clone
    new_name : str
        the name of the new project

    Returns:
        Knowledge_object: the new project, a translation object containg mapping between new and org mids
    """
    if new_name is None:
        new_name = ko.name + " (copy)"
    new_ko = clone_object(sc, ko, new_name=new_name, copy_edges=False)
    if new_ko.id == -1:
        raise Exception("Failed to create new project")
    cloned_objects = {new_ko.metadata_id: new_ko}
    edge_list = []

    # TODO: use bulk methods
    def clone_from_org(ob, cloned_objects, new_ko):
        # Storage is a global object and we don't have a 1-1 relation to the workflow project
        if isinstance(ob, Storage_policy):
            return None
        if ob.metadata_id not in cloned_objects.keys():
            if exclude_docker_job and isinstance(ob, Docker_job):
                return
            cp = clone_object(sc, ob, ob.name, copy_edges=False)
            assert cp.id != -1, "Failed to copy object mid={} name={}".format(
                ob.metadata_id, ob.name
            )
            cloned_objects[ob.metadata_id] = cp
            link(sc, new_ko, cp, verify_api=False)
        print("|=> Cloned: {} -- {}".format(ob.name, ob.table_name))
        return cloned_objects[ob.metadata_id]

    for ob in [o for o in find_wob_by_outbound_edges(sc, ko.metadata_id)]:
        clone_from_org(ob, cloned_objects, new_ko)
        for wob in [o for o in find_wob_by_inbound_edges(sc, ob.metadata_id)]:
            if clone_from_org(wob, cloned_objects, new_ko) is not None:
                edge_list.append((wob.metadata_id, ob.metadata_id))
        for wob in [o for o in find_wob_by_outbound_edges(sc, ob.metadata_id)]:
            if clone_from_org(wob, cloned_objects, new_ko) is not None:
                edge_list.append((ob.metadata_id, wob.metadata_id))
    edge_set = set(edge_list)

    print(
        "|=> Cloned objects: {}".format(
            ",".join([o.table_name for o in cloned_objects.values()])
        )
    )

    for e in edge_set:
        src = cloned_objects[e[0]]
        dst = cloned_objects[e[1]]
        attributes = get_edge_attribute(sc, e[0], e[1])
        link(sc, src, dst, verify_api=False)
        set_edge_attribute(sc, src, dst, attributes)
        # for receiver in attributes.keys():
        #    tr = attributes[receiver]
        #    print ("{}:{} -|{}|-> {}:{}  {}".format(src.name, tr[0], tr[1], dst.name, receiver, "is a field" if tr[2] else ""))

    if new_parent_id is not None:
        dest_project_ob = Project(sc, id=new_parent_id)
        if dest_project_ob.id == -1:
            raise Exception("Failed to find destination project")
        # with ko.sctx.connect() as con:
        con = ko.sctx.connect()
        _add_edge(
            con,
            "PROJECT",
            "KNOWLEDGE_OBJECT",
            dest_project_ob.metadata_id,
            new_ko.metadata_id,
        )
        con.commit()
    return new_ko, cloned_objects


def delete_project(sc, ko: Knowledge_object, preview=False, hard=True):
    """Deletes a project and all of its contents

    Args:
    sc : Security_context
    ko : Knowledge_object
        the project to clone
    new_name : str
        the name of the new project

    Returns:
        Knowledge_object: the new project
    """
    nodes = {}
    for ob in [o for o in find_wob_by_outbound_edges(sc, ko.metadata_id)]:
        for wob in [o for o in find_wob_by_inbound_edges(sc, ob.metadata_id)]:
            nodes[wob.metadata_id] = wob
        for wob in [o for o in find_wob_by_outbound_edges(sc, ob.metadata_id)]:
            nodes[wob.metadata_id] = wob
    if preview:
        return nodes.values()

    for n in nodes.values():
        # TODO: implement bulk delete
        delete_object(n, hard=hard)
        print("Deleting {}".format(n.metadata_id))
    delete_object(ko, hard=hard)
    return nodes.values()


def has_connected_attribute(context: Execution_context_api, attribute: str) -> bool:
    """Check if the current wob has a connection to another wob with the given attribute."""
    G: nx.DiGraph = context.get_execution_graph()
    current_wob_metadata_id = context.get_current_wob_metadata_id()
    # print ("has_connected_attribute: Current wob: {}".format(current_wob_metadata_id))
    outbound_edges = G.out_edges(current_wob_metadata_id, data=True)
    for edge in outbound_edges:
        # print ("has_connected_attribute: Edge: {}".format(edge))
        # print ("..compare to attribute: {}".format(attribute))
        for edge_attr in edge[2]["attributes"]:
            if "source_transmitter_key" not in edge_attr:
                continue
            if edge_attr["source_transmitter_key"] == attribute:
                return True
    return False


def create_attribute_edge_list(ko: Knowledge_object) -> list[dict]:
    """Transform the wob graph into a an edgelist between wob attributes."""
    g = create_graph(ko, materialize=False)
    edges = []
    wob_nodes = {}
    set_object_view_representation_policy("dict")
    for n in g.nodes:
        wob_nodes[n] = find_object_by_id(ko.sctx, g.nodes[n]["id"], g.nodes[n]["type"])
    # TODO: use bulk fetch
    for e in g.edges:
        attr: dict = get_edge_attribute(ko.sctx, wob_nodes[e[0]], wob_nodes[e[1]])
        if attr is not None:
            for receiver in attr.keys():
                tr = attr[receiver]
                e = {
                    "source_wob_key": e[0],
                    "source_transmitter_key": tr[0],
                    "destination_wob_key": e[1],
                    "destination_receiver_key": receiver,
                    "kind": tr[1],
                }
                edges.append(e)


def create_attribute_graph(edge_list: list[dict]) -> nx.DiGraph:
    """Transform the edge graph generated by create_attribute_edge_list into a networkx graph."""
    G = nx.DiGraph()
    for e in edge_list:
        src_node_key = e["source_wob_key"] + "::" + e["source_transmitter_key"]
        dst_node_key = e["destination_wob_key"] + "::" + e["destination_receiver_key"]
        G.add_edge(src_node_key, dst_node_key, kind=e["kind"])
    return G


def list_secrets(sc: Security_context, limit=50, page=0, search="%") -> list:
    """List all secrets in the secret store."""
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor(dictionary=True) as cur:
        cur.execute(
            "SELECT `key`, last_updated, created_at FROM v_secrets WHERE `key` LIKE %s LIMIT %s OFFSET %s",
            (search, limit, page * limit),
        )
        rows = cur.fetchall()
        return rows


def read_secret(sc: Security_context, key: str) -> str:
    """Get a secret from the secret store."""
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        cur.execute("SELECT value FROM v_secrets WHERE `key` = %s LIMIT 1", (key,))
        row = cur.fetchone()
        if row is None:
            raise Exception("Secret not found: {}".format(key))
        return row[0]


def secret_exists(sc: Security_context, key: str) -> bool:
    """Check if a secret exists in the secret store."""
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        cur.execute("SELECT `key` FROM v_secrets WHERE `key` = %s", (key,))
        row = cur.fetchone()
        return row is not None


def write_secret(sc, key: str, value: str):
    """Call the sp_write_secret stored procedure to write a secret to the secret store."""
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        cur.callproc("sp_write_secret", (key, value))
        con.commit()


def delete_secret(sc, key: str):
    """Call the sp_delete_secret stored procedure to delete a secret from the secret store."""
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor() as cur:
        cur.callproc("sp_delete_secret", (key,))
        con.commit()


def set_chain_execution_priority(ob, p: int):
    """When a KO is executed all the execution graphs are ordered by priority.
    The max priority of all the nodes in the graph is the priroity of the graph.
    In WOBs the order field is the priority."""
    sctx = ob.sctx
    ob.order = p
    ob.update(sctx)


def escape(s: str) -> str:
    """filter out any non alphanumeric characters from a string. Keep dots."""
    return "".join(e for e in s if e.isalnum() or e in [".", "_", " ", "-", "+"])


def find_wob_by_name_and_tag(
    sc: Security_context,
    name: str,
    tags: str,
    hard_limit: int = 20,
    order_by_popularity: bool = False,
):
    if tags is None or tags == "":
        tags = ["'miranda.prefab'"]
    else:
        tags = tags.split(",")
        if "miranda.prefab" not in tags:
            tags.append("miranda.prefab")
        tags = [escape(t) for t in tags]
        tags = [t for t in tags if len(t) > 0]
    conn = sc.connect()
    with conn.cursor(dictionary=True) as cur:
        sql = (
            "WITH r_tags (id) AS (SELECT id FROM vtag2metadata WHERE tag IN ({}) "
            "GROUP BY id HAVING COUNT(DISTINCT tag) = {})".format(
                ",".join(["'{}'".format(t) for t in tags]), len(tags)
            )
        )
        if order_by_popularity:
            sql += (
                " SELECT t.*, COALESCE(p.popularity, 0) as popularity FROM v_code t "
                "JOIN r_tags ON r_tags.id=t.metadata_id "
                "LEFT JOIN v_popularity_index p ON p.id=t.metadata_id "
                "WHERE t.name LIKE %s "
                "ORDER BY popularity DESC "
                "LIMIT %s"
            )
        else:
            sql += " SELECT * FROM v_code t JOIN r_tags ON r_tags.id=t.metadata_id WHERE t.name LIKE %s LIMIT %s"
        cur.execute(sql, (name, hard_limit))
        rows = cur.fetchall()
        ob_class = table_to_object("CODE")
        for row in rows:
            ob = ob_class(sc)
            ob._load_from_resultset_dict(row)
            yield ob


def notify_gui(sc: Security_context, payload: str):
    """Notifies the browser that a GUI element needs to be updated.
    The message is broadcasted to all existing websockets of the current user."""
    # TODO: use execution context here instead of loading message every call
    if "WOB_MESSAGE" in os.environ:
        try:
            msg = json.loads(os.environ["WOB_MESSAGE"])
            ticket = os.environ.get("REALTIME_MESSAGE_TICKET", None)
            if msg["wob_type"] != "KNOWLEDGE_OBJECT" or ticket is None:
                # raise Exception("Has message but no valid ticket")
                # print ("|=> WARNING: Has real time message but no valid ticket.")
                pass

            # with sc.connect() as con:
            con = sc.connect()
            with con.cursor() as cur:
                cur.callproc(
                    "sp_ko_send_realtime_message", (ticket, msg["wob_id"], payload)
                )
                con.commit()
                return  # successfully sent message with ticket, no need to send via user sp

        except Exception as e:
            # print("DEBUG: notify_gui: Failed to send message with ticket, sending via user sp instead.")
            logger.error(e)

    con = sc.connect()
    with con.cursor() as cur:
        cur.callproc("sp_user_send_realtime_message", (payload,))
        con.commit()


def send_realtime_message(
    sc: Security_context,
    payload: str,
    ticket: str | None = None,
    ko_id: int | None = None,
):
    """Send a realtime message to the subject wob."""
    if ticket is None and ko_id is None:
        con = sc.connect()
        with con.cursor() as cur:
            cur.callproc("sp_user_send_realtime_message", (payload,))
            con.commit()
    else:
        assert ticket is not None, "ticket is required when ko_id is provided"
        assert ko_id is not None, "ko_id is required when ticket is provided"
        con = sc.connect()
        with con.cursor() as cur:
            cur.callproc("sp_ko_send_realtime_message", (ticket, ko_id, payload))
            con.commit()


def notify_gui_reload_node(sc: Security_context, ob):
    """Notifies the browser that a GUI element needs to be updated.
    The message is broadcasted to all existing websockets of the current user."""
    notify_gui(
        sc,
        json.dumps(
            {
                "action": "update[VIEW]",
                "data": {"id": ob.id, "metadata_id": ob.metadata_id},
            }
        ),
    )


def execute_processor_command(sc: Security_context, project_id: int, payload: dict):
    """Send a command to a processor either running in DEBUG mode or in a deployed state using the wob message queue."""
    # print ("*** execute_processor_command: project_id = {}, payload = {}".format(project_id, payload))
    assert "command" in payload, "Missing command in payload"
    jpayload = json.dumps(payload)
    con = sc.connect()
    with con.cursor(dictionary=True) as cur:
        print(
            "*** Calling sp_notify_processor project id= {} with payload = {}".format(
                project_id, jpayload
            )
        )
        cur.callproc(
            "sp_notify_processor",
            (
                project_id,
                jpayload,
            ),
        )
        con.commit()
        rows = []
        # Collect resultset from callproc
        for result in cur.stored_results():
            rows = result.fetchall()
            # for row in rows:
            #    print (row)
        return rows


def get_wob_by_connected_attribute(
    context: Execution_context_api, attribute: str
) -> bool:
    """Check if the current wob has a connection to another wob with the given attribute."""
    G: nx.DiGraph = context.get_execution_graph()
    sc = context.get_security_context()
    current_wob_metadata_id = context.get_current_wob_metadata_id()
    # print ("has_connected_attribute: Current wob: {}".format(current_wob_metadata_id))
    outbound_edges = G.out_edges(current_wob_metadata_id, data=True)
    for edge in outbound_edges:
        # print ("has_connected_attribute: Edge: {}".format(edge))
        # print ("..compare to attribute: {}".format(attribute))
        for edge_attr in edge[2]["attributes"]:
            if "source_transmitter_key" not in edge_attr:
                continue
            if edge_attr["source_transmitter_key"] == attribute:
                wob = Code_block(sc, metadata_id=edge[1])
                assert wob.id != -1, "Failed to load wob mid = {}".format(edge[1])
                return wob
    return None


def get_connected_transmitter_node(sc: Security_context, metadata_id: int, socket: str):
    """
    Find the transmitter node connected to the receiver socket of the node with the metadata_id
     sc: The security context
     metadata_id: The metadata id of the node
     socket: The socket name
    Returns: A list of nodes connected to the socket
    """
    con = sc.connect()
    with con.cursor(dictionary=True) as cur:
        cur.execute("SELECT * FROM v_edges e WHERE e.dest_id = %s", (metadata_id,))
        rows = cur.fetchall()
        for row in rows:
            if row["attributes"] is None:
                continue
            attributes = json.loads(row["attributes"])
            for attr, value in attributes.items():
                if attr == socket:
                    # print ("Ob.metadata_id = {}:{}->{}:{}".format(row["src_id"],value[0], row["dest_id"],attr))
                    return row["src_id"]
    return -1  # No connected transmitter node found


def get_connected_subgraph(ob, max_depth=10):
    sql = """
WITH RECURSIVE descendants AS
  (
    SELECT e.src_id,e.src_type,e.dest_id as dest_id,e.dest_type, e.etl_id, 0 as depth  FROM v_edges e
      WHERE e.dest_id = %s
    UNION DISTINCT
    SELECT e.src_id, e.src_type, e.dest_id, e.dest_type, e.etl_id, d.depth +1
      FROM descendants d, v_edges e
      WHERE e.dest_id=d.src_id AND depth < %s AND e.src_type <> 'KNOWLEDGE_OBJECT' AND e.src_type <> 'PROJECT'
  )
  SELECT m.name as name, d.src_id,d.src_type,d.dest_id as id,d.dest_type,d.etl_id
    FROM descendants d
    JOIN v_metadata m ON m.id = d.src_id
    WHERE d.src_type <> 'KNOWLEDGE_OBJECT'
"""
    con = ob.sctx.connect()
    G = nx.DiGraph()
    metadata_id = ob.metadata_id
    G.add_node(metadata_id, name=ob.name, type="CODE")
    with con.cursor(dictionary=True) as cur:
        print((metadata_id, max_depth))
        cur.execute(sql, (metadata_id, max_depth))
        rows = cur.fetchall()
        for row in rows:
            if row["src_id"] not in G.nodes():
                G.add_node(row["src_id"], name=row["name"], type=row["src_type"])
            if (row["src_id"], row["id"]) not in G.edges():
                G.add_edge(row["src_id"], row["id"])

    return G


def find_model_parts_by_ko(ko):
    """
    Find any model parts used with the node COMPILE_NODE_NAME in the specified knowledge object.
     ko: The knowledge object containing the code block COMPILE_NODE_NAME
    Returns: A tuple: (root node,nx.DiGraph) of Code_block objects or None
    """
    sc = ko.sctx
    con = sc.connect()
    subgraph = []
    with con.cursor(dictionary=True) as cur:
        cur.execute(
            """SELECT m.name,e.src_id,e.dest_id
                        FROM v_edges e LEFT JOIN
                            v_metadata m on m.id=e.dest_id
                        WHERE e.src_id = %s AND m.name = %s""",
            (ko.metadata_id, COMPILE_NODE_NAME),
        )
        rows = cur.fetchall()
        for row in rows:
            mid = int(row["dest_id"])
            # print ("*** DEBUG: Found node with name '{}' (mid={}) connected from Knowledge_object mid={}".format(COMPILE_NODE_NAME, mid, ko.metadata_id))
            connected_ob_mid = get_connected_transmitter_node(sc, mid, "model parts")
            if connected_ob_mid == -1:
                logger.warning(
                    f"find_model_parts_by_ko(): No connected transmitter nodes for mid= {mid}"
                )
                return None
            ob = Code_block(sc, metadata_id=connected_ob_mid)
            assert ob.id != -1, (
                f"Can't find the knowledge graph associated with the ID {connected_ob_mid}"
            )
            subgraph = get_connected_subgraph(ob, max_depth=10)
            return ob, subgraph
    # print ("** DEBUG: There are no edges from ko.mid={} to code.mid = {} where the code.name= {}".format(ko.metadata_id, "?", COMPILE_NODE_NAME))
    return Knowledge_object(sc), None


def write_wob_to_files(file_name_template, wobs):
    """This is a helper function which write the code block body to a file to help the pytorch framework to do code analysis.
    It is primarily used by the node "MainlyAI compile model" and the get_model_parts() function.
    """
    for wob in wobs:
        code = wob.body
        with open(file_name_template.format(wob.id), "w+") as f:
            f.write(WOB_CODE_BLOCK_HEADER)
            f.write(code)


def get_model_parts(ko):
    """Returns a list of Code_block objects which are connected to the node COMPILE_NODE_NAME in the specified knowledge object."""
    _, subgraph = find_model_parts_by_ko(ko)
    if subgraph is None:
        logger.error("get_model_parts(): find_model_parts_by_ko() returned None!")
        return []

    wobs = []
    for mids in subgraph.nodes(data=True):
        wobs.append(Code_block(ko.sctx, metadata_id=int(mids[0])))
    write_wob_to_files(file_name_template="./WOB-{}.py", wobs=wobs)
    return wobs


def rewrite_text(text, function_name, payload):
    """
    Rewrite the specified function in the text by replacing the content between
    '## AUTOMAGIC!' and '## END' with the given payload.
    """
    pattern = rf"(def {function_name}\(.*?\).*?## AUTOMAGIC!)(.*?)(\s*## END)"
    replacement = rf"\1{payload}\3"
    modified_text = re.sub(pattern, replacement, text, flags=re.DOTALL)
    return modified_text


def load_plugin_from_string(plugin_code, plugin_name):
    """Helper function used when executing in the processor to load a plugin from a string."""
    spec = importlib.util.spec_from_loader(plugin_name, loader=None)
    plugin_module = importlib.util.module_from_spec(spec)
    sys.modules[plugin_name] = plugin_module
    exec(plugin_code, plugin_module.__dict__)
    return plugin_module


def rewrite_function(ecx, function_name, payload):
    """Helper function used when executing in the processor to rewrite the body of a function in the current wob code.
    The function must have the following structure:

    def function_name(...):
        ## AUTOMAGIC!
        ...
        ## END

    Args:
        ecx: The execution context
        function_name: The name of the function to rewrite
        payload: The new code to insert into the function
    """
    wob = ecx.get_current_wob()
    code = wob.body
    new_code = rewrite_text(code, function_name, payload)
    wob.body = new_code
    sctx = ecx.get_security_context()
    wob.update(sctx)
    code_cache = ecx.get_code_cache()
    preamble = "from mirmod.workflow_object import WOB\nwob = WOB()"
    dyn_attr_str = "_DYNAMIC_NODE_ATTRS = {}"
    runtime_code = f"{dyn_attr_str}\n{preamble}\n{wob.body}"
    code_cache[wob.metadata_id] = load_plugin_from_string(runtime_code, wob.name)


def run_mainly_task(
    pod_id: str, payload=None, auth=None, endpoint="/stream_run_payload"
):
    """Run a task on a MainlyAI pod and return the output as a generator.
    Args:
        pod_id: The MainlyAI pod id
        payload: The payload JSON to send to the pod
        auth: The authentication token as a JSON
    """
    sess = requests.Session()
    r = sess.post(
        f"https://{pod_id}{endpoint}",
        data={"payload": json.dumps(payload)},
        headers={"authorization": json.dumps(auth)},
        verify=False,
        stream=True,
    )
    # TODO: use SSE parsing
    for i in r.iter_lines(1, decode_unicode=True, delimiter="\xb6"):
        yield i


def git_clone(
    sc: Security_context,
    ko: Knowledge_object,
    wob,
    soft=False,
    ask_for_password=input,
    push=False,
):
    if os.path.exists("ENABLE_GIT_LOG"):
        enable_log = True
    else:
        enable_log = False
    wob = git_clone_impl(
        sc, ko, wob, ask_for_password, soft=soft, push=push, enable_log=enable_log
    )
    return wob


def add_requirements(requirements: list):
    ecx = get_execution_context()
    current_requirements = ecx.get_requirements()
    a = set(current_requirements + requirements)
    ecx.set_requirements(list(a))


def get_input_from(wob, socket):
    """Wait for a message on the wob_message_queue and return the payload."""

    class Sleep_time:
        def __init__(self, min=0, max=10, steps=10, exponential=False):
            self.min = min
            self.max = max
            self.steps = steps
            self.count = 0
            self.exponential = exponential

        def __call__(self):
            """Increment current sleep time so that we reach max in self.steps steps"""
            if self.count >= self.steps:
                return self.max
            if self.exponential:
                """ set count to increase exponentially the """
                p = self.count / (self.steps - 1)
                if p > 1.0:
                    p = 1.0

                def f(x):
                    return x**4

                rs = self.min + (self.max - self.min) * f(p)
            else:
                rs = self.min + (self.max - self.min) * self.count / self.steps
            self.count += 1
            # time.sleep(rs)
            return rs

    def wait_for_event(sc, wob_id, ko_id, sleep_time, debug_prompt=""):
        wake_up_counter = 0
        rows = []
        while True:
            if debug_prompt != "":
                logger.debug(debug_prompt)
            # with sc.connect() as con:
            con = sc.connect()
            with con.cursor(dictionary=True) as cur:
                cur.callproc("get_wob_message_from_control", (wob_id,))
                con.commit()
                # Collect resultset from callproc
                for result in cur.stored_results():
                    rows = result.fetchall()
                if rows is not None and len(rows) > 0:
                    return rows
                # print ("DEBUG: wait_for_event: get_wob_message_for_processor({}) didn't return any rows.".format(wob_id))
                didnt_get_any_notification = False
                # check if a stop command was issued
                cur.callproc("get_wob_message_for_processor", (ko_id,))
                con.commit()
                # Collect resultset from callproc
                for result in cur.stored_results():
                    rows = result.fetchall()
                    if rows is not None and len(rows) > 0:
                        raise Exception("|=> Stop command issued!")
                s = 0
                try:
                    # with sc.connect() as con:
                    # con = sc.connect()
                    # with con.cursor(dictionary=True) as cur:
                    # Wait for a maximum of two minutes.
                    # Note: we're using wob_id here intentionally because policy is that there can only be one
                    # running project per wob_id.
                    s = round(sleep_time(), ndigits=1)
                    cur.execute(
                        "SELECT /* WAITING_FOR_INPUT (wob:{} ko:{}) */ SLEEP({})".format(
                            wob_id, ko_id, s
                        )
                    )
                    _ = cur.fetchall()
                    didnt_get_any_notification = True
                except Exception:
                    # NOTE: Error is 2013: Lost connection to MySQL server during query which is expected.
                    if len(debug_prompt) > 0:
                        logger.debug(f"Woke up from sleep. {debug_prompt}")
                    else:
                        logger.debug("Woke up from sleep.")

                if didnt_get_any_notification:
                    logger.debug(
                        f"Didn't get any notifications after {s} seconds. Retrying... ({wake_up_counter} {debug_prompt})"
                    )
                    time.sleep(1)
                    wake_up_counter += 1
                if wake_up_counter > 10:
                    logger.warning(
                        f"Shutting down the processor due to inactivity. {debug_prompt}"
                    )
                    raise Exception(
                        "|=> ERROR: Shutting down the processor due to inactivity."
                    )

    ecx = get_execution_context()
    sc = ecx.get_security_context()
    ko = ecx.get_knowledge_object()
    sleep_time = Sleep_time(min=30, max=60 * 2, steps=10, exponential=True)
    rows = wait_for_event(
        sc, wob.id, ko.id, sleep_time, debug_prompt="Waiting for input"
    )
    payload = json.loads(rows[0]["payload"])
    return payload


def transact_credits(
    sc: Security_context, to_organization_id: int, amount: int, statement: str
):
    """Send credits to an organization via a transaction."""
    con = sc.connect()
    with con.cursor() as cur:
        cur.callproc("sp_transact_credits", (to_organization_id, amount, statement))
        con.commit()


def get_message(sc: Security_context, subject: str):
    """
    Fetch the next message for a subject from the message queue.
    """
    assert subject is not None, "target is required"
    try:
        con = sc.connect()
        with con.cursor(dictionary=True) as cur:
            cur.callproc("get_own_wob_message", (subject,))
            con.commit()
            for result in cur.stored_results():
                rs = result.fetchall()
                if len(rs) > 0:
                    return rs[0]
                else:
                    return None
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)

    return None


def is_uv_venv():
    try:
        venv_path = os.environ.get("VIRTUAL_ENV", "")

        if venv_path:
            pyvenv_cfg = os.path.join(venv_path, "pyvenv.cfg")
            if os.path.exists(pyvenv_cfg):
                # pyvenv.cfg is not a standard INI file, need to add a section header
                with open(pyvenv_cfg, "r") as f:
                    fc = f.read()
                    if not fc.startswith("[pyvenv]"):
                        config_content = "[pyvenv]\n" + fc
                    else:
                        config_content = fc

                config = configparser.ConfigParser()
                config.read_string(config_content)

                if "pyvenv" in config and "uv" in config["pyvenv"]:
                    return True

        return False
    except Exception as e:
        logger.warning(f"is_uv_venv(): {e}")
        return False


class StopIterationToken:
    pass
