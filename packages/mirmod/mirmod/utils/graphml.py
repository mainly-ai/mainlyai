import datetime
import json
import networkx as nx
from mirmod import miranda
from mirmod.utils import logger
from miranda_admin_ops import admin_get_all_edge_segments, admin_get_all_node_positions
import traceback
from io import StringIO
import xml.etree.ElementTree as ET


def import_graph(ko, graphml_file):
    """
    Imports a graph from a GraphML file, creating and linking workflow objects (wobs)
    within the context of a given Knowledge Object (ko).

    Args:
        ko (miranda.Knowledge_object): The parent Knowledge Object to which the imported wobs will be linked.
        graphml_file (file-like object): The GraphML file to import.

    Returns: node_positions, edge_segments in the form suitable for miranda_admin_ops.admin_update_or_insert_node_positions and miranda_admin_ops.admin_update_or_insert_edge_segments
    """
    # The graphml_file argument is a string containing the file content,
    # so we wrap it in StringIO to make it a file-like object for networkx.
    # networkx.read_graphml automatically handles type conversion for attributes
    # based on the 'attr.type' specified in the GraphML <key> definitions.
    # We do not need to provide a custom type caster.
    G = nx.read_graphml(StringIO(graphml_file))

    # Pre-process the GraphML to extract edge graphics data, as networkx
    # does not parse complex nested XML within <data> tags.
    edge_graphics_map = {}
    try:
        # The graphml_file is a string, so we parse it directly.
        root = ET.fromstring(graphml_file)
        # Define namespaces to correctly find elements. The default namespace
        # (xmlns) must be given a prefix (e.g., 'g') for XPath queries.
        ns = {
            "g": "http://graphml.graphdrawing.org/xmlns",
            "y": "http://www.yworks.com/xml/graphml",
        }
        # Use the namespace prefix in the findall query.
        for graph in root.findall("g:graph", ns):
            print("GRAPHML root!")
            for edge in graph.findall("g:edge", ns):
                src_id = edge.get("source")
                dst_id = edge.get("target")
                print("EDGE!", src_id, dst_id)
                if src_id and dst_id:
                    # Find the PolyLineEdge data within the edge
                    poly_line_edge = edge.find(".//y:PolyLineEdge", ns)
                    print("poly_line_edge = ", poly_line_edge)
                    if poly_line_edge is not None:
                        # Store the raw XML string of the PolyLineEdge element

                        edge_graphics_map[(src_id, dst_id)] = ET.tostring(
                            poly_line_edge, encoding="unicode"
                        )
    except ET.ParseError as e:
        logger.error(f"Failed to parse GraphML for edge graphics: {e}")

    node_map = {}
    wobs = {}
    node_positions = {}
    edge_segments = []

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
                if attr in ["class", "id", "metadata_id", "cloned_from_id", "status"]:
                    continue
                if hasattr(wob, attr):
                    # print(f"  Setting attribute '{attr}' to '{str(value)[:50]}...'")
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
                            print(
                                f"  Could not cast attribute '{attr}' with value '{value}' to {default_type}. Using original value. Error: {e}"
                            )
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
                # print("WOB.api = ", wob.api)
            except json.JSONDecodeError:
                logger.error(
                    f"  Wob '{wob.name}' has an invalid API string: '{api_str[:100]}...'. Setting to None."
                )
                wob.api = None

            wob.update(ko.sctx)
            wobs[node_id] = wob

            # Extract node position
            if "x" in node_data and "y" in node_data:
                try:
                    node_positions[wob.metadata_id] = {
                        "x": float(node_data["x"]),
                        "y": float(node_data["y"]),
                    }
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Could not parse position for node '{node_id}' (MID: {wob.metadata_id}). "
                        f"x='{node_data.get('x')}', y='{node_data.get('y')}'. Error: {e}"
                    )
            else:
                # networkx might not parse nested yfiles geometry.
                # Let's check for the raw 'nodegraphics' attribute if x/y are not top-level.
                if "nodegraphics" in node_data:
                    # This is a string representation of an XML fragment.
                    # A more robust solution might involve parsing this, but for now we can use regex.
                    import re

                    x_match = re.search(r'x="([^"]+)"', node_data["nodegraphics"])
                    y_match = re.search(r'y="([^"]+)"', node_data["nodegraphics"])
                    if x_match and y_match:
                        node_positions[wob.metadata_id] = {
                            "x": float(x_match.group(1)),
                            "y": float(y_match.group(1)),
                        }

        except Exception as e:
            logger.error(f"Error creating wob for node '{node_id}': {e}")
            logger.debug(traceback.format_exc())

    # 3. Third pass: Create all edges between the created wobs.
    for edge in G.edges(data=True):
        src_id, dst_id, edge_data = edge
        if src_id not in wobs or dst_id not in wobs:
            logger.warning(
                f"Skipping edge from '{src_id}' to '{dst_id}': one or both nodes were not created."
            )
            continue

        logger.info(f"Creating edge from '{src_id}' to '{dst_id}'")

        try:
            src = wobs[src_id]
            dst = wobs[dst_id]
            print(f"  MIDs: {src.metadata_id} -> {dst.metadata_id}")

            # Create the basic link first
            miranda.link(ko.sctx, src, dst, verify_api=False)

            # Now, set the detailed attributes for the sockets
            attributes = json.loads(edge_data.get("attributes", "{}"))
            logger.debug(f"Edge '{src_id}'->'{dst_id}' raw data: {edge_data}")
            if attributes:
                miranda.set_edge_attribute(ko.sctx, src, dst, attributes)

            # Retrieve pre-parsed edge graphics data.
            edge_graphics_data = edge_graphics_map.get((src_id, dst_id))

            logger.debug(f"Edge '{src_id}'->'{dst_id}' attributes: {attributes}")
            logger.debug(
                f"Edge '{src_id}'->'{dst_id}' graphics data found: {bool(edge_graphics_data)}"
            )

            if attributes and edge_graphics_data:
                import re

                # Ensure attributes is a dict with exactly one entry for src/dest handles
                if not isinstance(attributes, dict) or len(attributes) != 1:
                    logger.warning(
                        f"Skipping edge segments for '{src_id}'->'{dst_id}': 'attributes' data is not a dict with a single entry. Data: {attributes}"
                    )
                    continue

                src_handle = next(iter(attributes.keys()))
                dest_handle = next(iter(attributes.values()))
                segments = []
                # This regex handles points with or without a namespace prefix (e.g., <y:Point> or <Point>)
                # and both self-closing <.../> and non-self-closing <...></...> tags.
                point_matches = re.findall(
                    r'<(?:[\w-]+:)?Point\s+x="([^"]+)"\s+y="([^"]+)"\s*(?:/>|></(?:[\w-]+:)?Point>)',
                    edge_graphics_data,
                )
                logger.debug(
                    f"Edge '{src_id}'->'{dst_id}': Found {len(point_matches)} points in graphics data from {len(segments)} segments."
                )
                for x_str, y_str in point_matches:
                    try:
                        segments.append({"x": float(x_str), "y": float(y_str)})
                    except (ValueError, TypeError):
                        logger.warning(
                            f"Could not parse point in edge '{src_id}'->'{dst_id}': x={x_str}, y={y_str}"
                        )

                if segments:
                    logger.info(
                        f"Adding {len(segments)} segments for edge '{src_id}'->'{dst_id}'."
                    )
                    edge_segments.append(
                        {
                            "src_id": src.metadata_id,
                            "src_handle": src_handle,
                            "dest_id": dst.metadata_id,
                            "dest_handle": dest_handle[0],
                            "segments": segments,
                        }
                    )
                else:
                    logger.warning(
                        f"Found graphics data for edge '{src_id}'->'{dst_id}', but failed to extract any segment points."
                    )

        except Exception as e:
            logger.error(f"  Could not create edge from '{src_id}' to '{dst_id}': {e}")
            logger.debug(traceback.format_exc())

    # We can't update them in user space so we need to pass them along for an admin to set the values.
    return node_positions, edge_segments
