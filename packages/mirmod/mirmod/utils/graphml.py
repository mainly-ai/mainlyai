import datetime
import json
from lxml import etree
import networkx as nx
from mirmod import miranda, workflow_object
from mirmod.utils import logger
import traceback
from io import StringIO
import os


def _compile_and_update_api(wob: miranda.Code_block):
    """
    Compiles the code in a wob to discover its API attributes and updates the wob in the database.
    This is a critical step to make sure the UI can render the wob's sockets.
    """
    logger.debug(f"Compiling API for wob '{wob.name}' (mid: {wob.metadata_id})")
    if not isinstance(wob, miranda.Code_block) or not wob.body:
        return

    # Preserve values from the imported API if they exist.
    imported_api = {}
    if wob.api:
        try:
            imported_api = json.loads(wob.api)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse existing API for wob '{wob.name}'. Values may not be preserved.")

    # This function executes code, so it requires a safety flag.
    os.environ["I_AM_IN_AN_ISOLATED_AND_SAFE_CONTEXT"] = "1"
    try:
        # This header is needed for the code to be valid for compilation.
        wob_code = miranda.WOB_CODE_BLOCK_HEADER + wob.body
        entry_class, _, _, _, _ = workflow_object._unsafe_get_code_entry_class(wob_code)
        if entry_class:
            # Create a lookup for imported attribute values
            imported_values = {}
            if imported_api and "attributes" in imported_api:
                for attr in imported_api["attributes"]:
                    if "value" in attr and attr.get("name"):
                        imported_values[attr["name"]] = attr["value"]

            attributes = []
            for key, attr in entry_class.attributes.items():
                attr_dict = {"name": key, "kind": attr.kind, "direction": attr.direction}
                if attr.control:
                    attr_dict["control"] = attr.control.to_dict()
                if key in imported_values:
                    attr_dict["value"] = imported_values[key]
                attributes.append(attr_dict)
            wob.api = json.dumps({"attributes": attributes, "wob_name": entry_class.name})
            wob.update(wob.sctx)
        else:
            logger.warning(f"Could not find entry class in wob '{wob.name}' (mid: {wob.metadata_id}). API will not be updated from code.")

    except Exception as e:
        logger.error(f"Failed to compile API for wob '{wob.name}' (mid: {wob.metadata_id}): {e}")
    finally:
        del os.environ["I_AM_IN_AN_ISOLATED_AND_SAFE_CONTEXT"]


def import_graph(ko, graphml_file):
    """
    Imports a graph from a GraphML file, creating and linking workflow objects (wobs)
    within the context of a given Knowledge Object (ko).

    Args:
        ko (miranda.Knowledge_object): The parent Knowledge Object to which the imported wobs will be linked.
        graphml_file (file-like object): The GraphML file to import.
    """
    # The graphml_file argument is a string containing the file content,
    # so we wrap it in StringIO to make it a file-like object for networkx.
    # networkx.read_graphml automatically handles type conversion for attributes
    # based on the 'attr.type' specified in the GraphML <key> definitions.
    # We do not need to provide a custom type caster.
    G = nx.read_graphml(StringIO(graphml_file))

    node_map = {}
    wobs = {}

    # 1. First pass: Validate and collect all node data from the GraphML file.
    for node in G.nodes(data=True):
        node_id, node_data = node
        if "class" not in node_data:
            logger.warning(f"Skipping node '{node_id}': 'class' attribute is missing.")
            continue
        node_class = node_data["class"].upper()
        print(f"Found node '{node_id}' of type {node_class}")
        if node_class not in ["CODE_BLOCK"]:
            continue
        node_map[node_id] = node_data

    # 2. Second pass: Create all workflow objects.
    for node_id, node_data in node_map.items():
        node_class = node_data["class"].upper()
        print(f"Creating wob '{node_data.get('name', 'Unnamed')}' of type {node_class}")

        try:
            wob = miranda.create_wob(
                ko,
                name=node_data.get("name", "Unnamed Object"),
                description=node_data.get("description", ""),
                wob_type=node_class,
            )
            if wob.id == -1:
                raise Exception(f"Failed to create wob for node '{node_id}'")

            # Set attributes on the newly created wob
            for attr, value in node_data.items():
                if attr in ["class", "name", "description", "id", "metadata_id","cloned_from_id","status"]:
                    continue
                if hasattr(wob, attr):
                    print(f"  Setting attribute '{attr}' to '{str(value)[:50]}...'")
                    # Cast value to the appropriate type based on the ORM's default_value definition.
                    if attr in wob.default_value:
                        default_type = type(wob.default_value[attr])
                        try:
                            if default_type is bool:
                                # Handle string representations of booleans
                                if isinstance(value, str):
                                    casted_value = value.lower() in ("true", "1", "t")
                                else:
                                    casted_value = bool(value)
                            else:
                                casted_value = default_type(value)
                            setattr(wob, attr, casted_value)
                        except (ValueError, TypeError) as e:
                            print(f"  Could not cast attribute '{attr}' with value '{value}' to {default_type}. Using original value. Error: {e}")
                            setattr(wob, attr, value)
                    else:
                        # If no default is defined, set the value as is.
                        setattr(wob, attr, value)

            api_str = wob.api
            if api_str is None:
                logger.error(f" Wob {wob.name} has invalid api string = None.")
            try:
                # Parse the string and then dump it back to a clean JSON string
                wob.api = json.dumps(json.loads(api_str))
                print ("WOB.api = ",wob.api)
            except json.JSONDecodeError:
                logger.error(f"  Wob '{wob.name}' has an invalid API string: '{api_str[:100]}...'. Setting to None.")
                wob.api = None

            wob.update(ko.sctx)
            wobs[node_id] = wob

        except Exception as e:
            logger.error(f"Error creating wob for node '{node_id}': {e}")
            logger.debug(traceback.format_exc())

    # 3. Third pass: Create all edges between the created wobs.
    for edge in G.edges(data=True):
        src_id, dst_id, edge_data = edge
        if src_id not in wobs or dst_id not in wobs:
            logger.warning(f"Skipping edge from '{src_id}' to '{dst_id}': one or both nodes were not created.")
            continue

        logger.info(f"Creating edge from '{src_id}' to '{dst_id}'")

        try:
            src = wobs[src_id]
            dst = wobs[dst_id]
            logger.debug(f"  MIDs: {src.metadata_id} -> {dst.metadata_id}")

            # Create the basic link first
            miranda.link(ko.sctx, src, dst, verify_api=False)

            # Now, set the detailed attributes for the sockets
            attributes = json.loads(edge_data.get("attributes", "{}"))
            if attributes:
                miranda.set_edge_attribute(ko.sctx, src, dst, attributes)
        except Exception as e:
            logger.error(f"  Could not create edge from '{src_id}' to '{dst_id}': {e}")
            logger.debug(traceback.format_exc())
    # 4. Fourth pass: Compile APIs for all created Code_block wobs.
    for wob in wobs.values():
        if isinstance(wob, miranda.Code_block):
            _compile_and_update_api(wob)




def export_graph(graph):
    root = etree.Element("graphml")
    root.set("xmlns", "http://graphml.graphdrawing.org/xmlns")
    root.set("__xmlnsxsi__", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("__xmlnsy__", "http://www.yworks.com/xml/graphml")
    root.set(
        "__xsischemaLocation__",
        "http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd",
    )
    root.append(etree.Comment(f"Generated by Miranda on {datetime.datetime.now()}"))
    gr = etree.SubElement(root, "graph")
    gr.set("edgedefault", "directed")
    key_map = []
    node_els = []
    for id, node in graph.nodes(data=True):
        if "wob" not in node:
            continue
        node_el = etree.SubElement(gr, "node")
        node_el.set("id", f"n{id}")
        node_el.set("attr.name", node["wob"]["name"])
        for key in node["wob"]:
            key_i = key_map.index(key) if key in key_map else None
            if key_i is None:
                key_i = len(key_map)
                key_map.append(key)
                key_el = etree.SubElement(root, "key")
                key_el.set("id", f"d{key_i}")
                key_el.set("for", "node")
                key_el.set("attr.name", key)
                if isinstance(node["wob"][key], int):
                    key_el.set("attr.type", "int")
                elif isinstance(node["wob"][key], float):
                    key_el.set("attr.type", "double")
                else:
                    key_el.set("attr.type", "string")
            data_el = etree.SubElement(node_el, "data")
            data_el.set("key", f"d{key_i}")
            data_el.text = str(node["wob"][key]).replace("\r\n", "\n")
        node_els.append(node_el)
        gr.append(node_el)

    key_map.append("nodegraphics")
    ngkeyi = len(key_map) - 1
    ngkey_el = etree.SubElement(root, "key")
    ngkey_el.set("id", f"d{ngkeyi}")
    ngkey_el.set("for", "node")
    ngkey_el.set("yfiles.type", "nodegraphics")

    for node in node_els:
        data_el = etree.SubElement(node, "data")
        data_el.set("key", f"d{ngkeyi}")
        shape_el = etree.SubElement(data_el, "__yShapeNode__")
        label_el = etree.SubElement(shape_el, "__yNodeLabel__")
        label_el.text = node.get("attr.name")
        geometry_el = etree.SubElement(shape_el, "__yGeometry__")
        geometry_el.set("height", "30.0")
        geometry_el.set("width", f"{len(label_el.text) * 6.0 + 10.0}")

    id = 0
    for src, dest, edge in graph.edges(data=True):
        edge_el = etree.SubElement(gr, "edge")
        edge_el.set("source", f"n{src}")
        edge_el.set("target", f"n{dest}")
        data = etree.SubElement(edge_el, "data")
        data.set("key", "e{}".format(id))
        data.text = json.dumps(edge["attributes"])
        key = etree.SubElement(root, "key")
        key.set("id", f"e{id}")
        key.set("for", "edge")
        key.set("attr.name", "attributes")
        key.set("attr.type", "string")
        id += 1
        gr.append(edge_el)
        root.append(key)

    treestr = etree.tostring(root, pretty_print=True)
    # stupid hack to get past the lxml limitation on not using : in tag and attribute names
    treestr = treestr.replace(b"__yShapeNode__", b"y:ShapeNode")
    treestr = treestr.replace(b"__yNodeLabel__", b"y:NodeLabel")
    treestr = treestr.replace(b"__yGeometry__", b"y:Geometry")
    treestr = treestr.replace(b"__xmlnsxsi__", b"xmlns:xsi")
    treestr = treestr.replace(b"__xmlnsy__", b"xmlns:y")
    treestr = treestr.replace(b"__xsischemaLocation__", b"xsi:schemaLocation")
    return treestr
