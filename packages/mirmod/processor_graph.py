import networkx as nx
from collections import deque
from mirmod.workflow_object import Transmitter, Transmitter_field, Receiver_field
import copy
import heapq
import functools


def in_degree(G, key):
    """Returns the number of inbound edges for a node where the key is the metadata_id of the WOB the node represents.
    Because every edge might be connected to one or more ports we also need to count the number of attributes on each edge."""
    E = G.in_edges(key, data=True)
    in_edge = 0
    for e in E:
        if "attributes" not in e[2]:
            print(
                "|=> WARNING: Edge {}->{} doesn't have any attributes".format(
                    e[0], e[1]
                )
            )
        attr = e[2]["attributes"]
        in_edge += len(attr)
    return in_edge


def is_dispatcher_node(G, node_mid, code_cache):
    src_code = code_cache[node_mid]
    count = 0
    for src_transmitter_key in src_code.wob.attributes.keys():
        if src_transmitter_key not in src_code.wob.attributes:
            continue
        transmitter = src_code.wob.attributes[src_transmitter_key]
        if isinstance(transmitter, Transmitter_field):
            count += 1
    if count > 1:
        return True
    return False


def has_transmitter_field(G, node_mid, attr, code_cache):
    src_code = code_cache[node_mid]
    for src_transmitter_key in src_code.wob.attributes.keys():
        if src_transmitter_key not in src_code.wob.attributes:
            continue
        transmitter = src_code.wob.attributes[src_transmitter_key]
        if isinstance(transmitter, Transmitter_field):
            if attr is None:
                return True
            if attr == src_transmitter_key:
                outbound_edges = G.out_edges(node_mid, data=True)
                for edge in outbound_edges:
                    for edge_attr in edge[2]["attributes"]:
                        if "source_transmitter_key" not in edge_attr:
                            continue
                        if edge_attr["source_transmitter_key"] == attr:
                            return True
    return False


def has_transmitter(G, node_mid, attr, code_cache):
    src_code = code_cache[node_mid]
    for src_transmitter_key in src_code.wob.attributes.keys():
        if src_transmitter_key not in src_code.wob.attributes:
            continue
        transmitter = src_code.wob.attributes[src_transmitter_key]
        if isinstance(transmitter, Transmitter):
            if attr is None:
                return True
            if attr == src_transmitter_key:
                outbound_edges = G.out_edges(node_mid, data=True)
                for edge in outbound_edges:
                    for edge_attr in edge[2]["attributes"]:
                        if "source_transmitter_key" not in edge_attr:
                            continue
                        if edge_attr["source_transmitter_key"] == attr:
                            return True
    return False


def has_receiver_field(G, node_mid, attr, code_cache):
    src_code = code_cache[node_mid]
    for key in src_code.wob.attributes.keys():
        if key not in src_code.wob.attributes:
            continue
        receiver = src_code.wob.attributes[key]
        if isinstance(receiver, Receiver_field):
            if attr is None or attr == key:
                return True
    return False


def get_attributes(G, node_mid, code_cache):
    if node_mid not in code_cache:
        return []
    src_code = code_cache[node_mid]
    attributes = src_code.wob.attributes
    return attributes


def get_node_attributes(G: nx.DiGraph, src, dst):
    data = G.get_edge_data(src, dst)
    ret = []
    for attr in data["attributes"]:
        ret.append((attr["source_transmitter_key"], attr["destination_receiver_key"]))
    return ret


def has_connected_edge(G, src_node_mid, transmitter_attribute):
    """Returns the destination node and the receiver attribute if there's a connected edge from the given node mid with the given transmitter attribute."""
    outbound_edges = G.out_edges(src_node_mid, data=True)
    for edge in outbound_edges:
        for edge_attr in edge[2]["attributes"]:
            if "source_transmitter_key" not in edge_attr:
                continue
            if edge_attr["source_transmitter_key"] == transmitter_attribute:
                return (edge[1], edge_attr["destination_receiver_key"])
    return None


def has_connected_transmitter_field(G, node_id, code_cache):
    src_code = code_cache[node_id]
    for src_transmitter_key in src_code.wob.attributes.keys():
        if src_transmitter_key not in src_code.wob.attributes:
            continue
        transmitter = src_code.wob.attributes[src_transmitter_key]
        if isinstance(transmitter, Transmitter_field):
            return has_connected_edge(G, node_id, src_transmitter_key)
    return None


def edge_has_transmitter_field(G, u, v, code_cache):
    """
    Check if the edge between nodes u and v has a transmitter field.

    Parameters:
        G (nx.Graph or nx.DiGraph): The input graph.
        u: Source node.
        v: Target node.
        code_cache: Cache of code objects.

    Returns:
        bool: True if the edge has a transmitter field, False otherwise.
    """
    edge_data = G.get_edge_data(u, v)
    if edge_data and "attr_key" in edge_data:
        attr_key = edge_data["attr_key"]
        if code_cache and u in code_cache:
            src_code = code_cache[u]
            if attr_key in src_code.wob.attributes:
                transmitter = src_code.wob.attributes[attr_key]
                return isinstance(transmitter, Transmitter_field)
    return False


def subgraph_attached_to_node(
    G, n, include_root=False, code_cache=None, only_non_transmitter_edges=False
):
    if n not in G:
        raise ValueError("Node n is not in the graph")

    # Determine neighbors based on graph type and filter by transmitter field if needed
    if G.is_directed():
        if only_non_transmitter_edges and code_cache:
            neighbors = set(
                v
                for v in G.successors(n)
                if not edge_has_transmitter_field(G, n, v, code_cache)
            )
        else:
            neighbors = set(G.successors(n))  # Nodes with edges from n
    else:
        if only_non_transmitter_edges and code_cache:
            neighbors = set(
                v
                for v in G.neighbors(n)
                if not edge_has_transmitter_field(G, n, v, code_cache)
            )
        else:
            neighbors = set(G.neighbors(n))

    # Remove node n (simulate splitting at n)
    H = G.copy()
    H.remove_node(n)

    # Identify components
    if not H.is_directed():
        components = list(nx.connected_components(H))
    else:
        components = list(nx.weakly_connected_components(H))

    # Find all nodes in components that contained any of the neighbors of n
    valid_nodes = set()
    for comp in components:
        if neighbors.intersection(comp):
            valid_nodes.update(comp)

    if include_root:
        valid_nodes.add(n)
        if G.is_directed():
            # Re-add n with only inbound edges
            H = G.subgraph(valid_nodes | {n}).copy()

            # If only_non_transmitter_edges is True, only keep inbound edges without transmitter fields
            if only_non_transmitter_edges and code_cache:
                for pred in list(H.predecessors(n)):
                    if edge_has_transmitter_field(G, pred, n, code_cache):
                        H.remove_edge(pred, n)
            else:
                # Remove all outbound edges
                for succ in list(H.successors(n)):
                    H.remove_edge(n, succ)

            return H

    return H.subgraph(valid_nodes).copy()


def split_graph(
    G: nx.DiGraph, n: int, include_node: bool = False
) -> tuple[nx.DiGraph, nx.DiGraph]:
    """
    Split a directed graph on a node n into left and right subgraphs.

    Parameters:
    -----------
    G : nx.DiGraph
        The input directed graph
    n : int
        The node to split on
    include_node : bool, default=False
        Whether to include node n in both subgraphs

    Returns:
    --------
    tuple[nx.DiGraph, nx.DiGraph]
        A tuple containing (left_subgraph, right_subgraph)
    """
    if n not in G:
        raise ValueError(f"Node {n} not in graph")

    # Initialize sets
    right_set = set()
    left_set = set()

    # 1. Identify all successors to n and mark them as Right_set
    # Using BFS to find all nodes reachable from n
    queue = deque([n])
    visited = {n}

    while queue:
        current = queue.popleft()
        if current != n:  # Don't add n to right_set yet
            right_set.add(current)

        for successor in G.successors(current):
            if successor not in visited:
                visited.add(successor)
                queue.append(successor)

    # 2. Identify all nodes where in_degree==0 and find paths to n
    source_nodes = [node for node in G.nodes() if G.in_degree(node) == 0]

    # Helper function to find all nodes on paths from source to target
    def find_nodes_on_paths(source, target, visited=None):
        if visited is None:
            visited = set()

        if source == target:
            return {source}

        visited.add(source)
        nodes_on_paths = set()

        for successor in G.successors(source):
            if successor not in visited:
                path_nodes = find_nodes_on_paths(successor, target, visited.copy())
                if path_nodes:
                    nodes_on_paths.add(source)
                    nodes_on_paths.update(path_nodes)

        return nodes_on_paths

    # Find nodes on paths from source nodes to n
    for source in source_nodes:
        if source != n:
            path_nodes = find_nodes_on_paths(source, n)
            if path_nodes:
                # Don't include n itself yet
                path_nodes.discard(n)
                left_set.update(path_nodes)

    # 3. For all unmarked source nodes, check if they have paths to Right_set
    unmarked_sources = [
        node
        for node in source_nodes
        if node not in left_set and node not in right_set and node != n
    ]

    for source in unmarked_sources:
        # Check if there's a path from source to any node in right_set
        for right_node in right_set:
            path_nodes = find_nodes_on_paths(source, right_node)
            if path_nodes:
                # Found a path to right_set
                right_set.update(path_nodes)
                break

    # 4. All remaining unmarked nodes go to the Left_set
    all_nodes = set(G.nodes())
    unmarked = all_nodes - right_set - left_set - {n}
    left_set.update(unmarked)

    # 5. Handle the node n based on include_node parameter
    if include_node:
        left_set.add(n)
        right_set.add(n)

    # 6. Create subgraphs
    l_G = G.subgraph(left_set).copy()
    r_G = G.subgraph(right_set).copy()

    return l_G, r_G


def find_dispatcher_node(graph, node, code_cache, visited_nodes=[]):
    subgraph_nodes = set()
    queue = [node]
    dispatcher_node = set()

    while queue:
        current = queue.pop()

        if current in visited_nodes:
            continue  # Stop expanding if we've seen this node before

        if is_dispatcher_node(graph, current, code_cache):
            dispatcher_node.add(node)

        subgraph_nodes.add(current)
        predecessors = set(graph.predecessors(current))

        for pred in predecessors:
            if pred not in subgraph_nodes:
                queue.append(pred)

    return dispatcher_node, graph.subgraph(subgraph_nodes)


def is_connected_with_attribute(G, start_node_mid, node, attribute, code_cache):
    """
    Helper function to check if a node is connected to the start node with the specified attribute.
    Returns True if there is a path from start_node_mid to node that starts with an edge having
    the specified attribute as a transmitter field.
    """
    # Check if there's a direct edge with the attribute
    connected_edge = has_connected_edge(G, start_node_mid, attribute)
    if connected_edge is None:
        return False

    dest_node, receiver_attr = connected_edge

    # If the destination is our target node, return True
    if dest_node == node:
        return True

    # Otherwise, check if there's a path from the destination to our target node
    try:
        path = nx.has_path(G, dest_node, node)
        return path
    except nx.NetworkXError:
        return False


def find_last_reciever_mid(G, start_node_mid, attribute, code_cache):
    """
    Finds the last receiver node that is connected to the start_node_mid through a path
    that begins with an edge having the specified attribute as a transmitter field.

    Args:
        G: NetworkX DiGraph
        start_node_mid: Starting node ID
        attribute: Transmitter field attribute to look for
        code_cache: Dictionary for caching code

    Returns:
        The node ID of the last receiver or None if not found
    """
    # 1. Extract all nodes with out_degree==0
    sink_nodes = [n for n in G.nodes() if G.out_degree(n) == 0]

    # 2. Filter nodes that are connected to start_node_mid with the specified attribute
    connected_sinks = [
        n
        for n in sink_nodes
        if is_connected_with_attribute(G, start_node_mid, n, attribute, code_cache)
    ]

    # 3. Count transmitters and receivers for all paths
    candidates = []
    for sink in connected_sinks:
        # Find all simple paths from start_node_mid to sink
        try:
            paths = list(nx.all_simple_paths(G, start_node_mid, sink))

            for path in paths:
                # Count transmitters and receivers along the path
                transmitters = 0
                receivers = 0

                for node in path:
                    transmitters += (
                        1 if has_transmitter_field(G, node, None, code_cache) else 0
                    )
                    receivers += (
                        1 if has_receiver_field(G, node, None, code_cache) else 0
                    )

                # If transmitters - receivers = 0, mark as candidate
                if transmitters - receivers == 0:
                    candidates.append(sink)
                    break  # Found a valid path for this sink
        except nx.NetworkXNoPath:
            continue

    # 4. Return the first candidate
    return candidates[0] if candidates else None


def find_transmitter_receiver_pairs(
    G: nx.DiGraph, code_cache={}, transmitter_field_branch=None
) -> list[tuple[int, int]]:
    if transmitter_field_branch is not None:
        branch_edge = transmitter_field_branch[0]
        src, dst = (
            branch_edge  # Extract source and destination nodes of the branch edge
        )

        # Extract the branch: all nodes reachable from dst
        connected_nodes = set(
            [n for n in nx.descendants(G, dst) if isinstance(n, int)]
        ) | {dst}

        transmitters = [
            n
            for n in connected_nodes
            if has_connected_transmitter_field(G, n, code_cache)
        ]
        receivers = [n for n in connected_nodes if has_receiver_field(n, code_cache)]

        # Ensure the original transmitter (src) is included
        if src not in transmitters and src in G.nodes:
            transmitters.append(src)
    else:
        transmitters = [
            n for n in G.nodes if has_connected_transmitter_field(G, n, code_cache)
        ]
        receivers = [n for n in G.nodes if has_receiver_field(G, n, None, code_cache)]
    pairs = []
    while True:
        pair_found_this_round = False
        for t in transmitters[:]:
            for r in receivers[:]:
                try:
                    all_paths = nx.all_simple_paths(G, source=t, target=r)
                    valid_path_found = False
                    for path in all_paths:
                        interior_nodes = path[1:-1]
                        if all(
                            n not in transmitters and n not in receivers
                            for n in interior_nodes
                        ):
                            valid_path_found = True
                            break
                    if valid_path_found:
                        pairs.append((t, r))
                        transmitters.remove(t)
                        receivers.remove(r)
                        pair_found_this_round = True
                        break
                except nx.NetworkXNoPath:
                    pass
            if pair_found_this_round:
                break
        if not pair_found_this_round:
            break
    return pairs


def determine_nesting(G: nx.DiGraph, pairs: list[tuple[int, int]]):
    """
    Determines the nesting structure of transmitter-receiver pairs and creates Field_nodes objects.

    Args:
        G: The directed graph.
        pairs: A list of tuples, where each tuple represents a (transmitter_mid, receiver_mid) pair.

    Returns:
        A list of Field_nodes objects with correctly set levels and parent relationships, sorted outermost first.
    """
    field_nodes = {
        transmitter: Field_descriptor(transmitter, None, reciever)
        for transmitter, reciever in pairs
    }
    for transmitter, receiver in pairs:
        field_nodes[transmitter].set_receiver(receiver)

    # Iteratively determine nesting levels and parent relationships
    changed = True
    while changed:
        changed = False
        for node in field_nodes.values():
            for potential_parent in field_nodes.values():
                if node == potential_parent:
                    continue

                # Ensure fields overlap before considering nesting
                if nx.has_path(
                    G, potential_parent.transmitter_mid, node.transmitter_mid
                ) and nx.has_path(G, node.receiver_mid, potential_parent.receiver_mid):
                    if (
                        node.parent_field is None
                        or potential_parent.level + 1 > node.level
                    ):
                        node.parent_field = potential_parent
                        node.level = potential_parent.level + 1
                        changed = True  # Continue iterating if any update occurs

    # Sort the field nodes list based on nesting level (outermost first)
    return sorted(field_nodes.values(), key=lambda x: x.level, reverse=True)


def calculate_start_nodes(G: nx.DiGraph, code_cache):
    # If there's any path from any node in the start nodes to a receiver that doesn't first
    # cross a transmitter, then this start_node belongs to a initialisation branch and should be removed.
    # 1. find all receivers
    # 2. for each receiver find a path to the start node
    # 3. for each node on the path check if it contains a transmitter. If it doesn't: remove the start node

    # Find all dispatcher nodes
    dispatcher_nodes = []
    G_copy = G.copy()
    for node in G.nodes():
        if is_dispatcher_node(G, node, code_cache):
            dispatcher_nodes.append(node)
            _, subgraph = split_graph(
                G_copy, node, include_node=False
            )  # subgraph_attached_to_node(G, node, include_root=False)
            nodes = list(subgraph.nodes())
            G_copy.remove_nodes_from(nodes)

    # Start with nodes that have no inbound edges
    start_nodes = [n for n in nx.topological_sort(G_copy) if G_copy.in_degree(n) == 0]

    # Find all receiver nodes
    receiver_nodes = []
    for node in G_copy.nodes():
        for attr in get_attributes(G_copy, node, code_cache):
            if has_receiver_field(G_copy, node, attr, code_cache):
                receiver_nodes.append(node)
                break

    # Find all transmitter nodes
    transmitter_nodes = []
    for node in G_copy.nodes():
        for attr in get_attributes(G_copy, node, code_cache):
            if has_transmitter_field(
                G_copy, node, attr, code_cache
            ) and not is_dispatcher_node(G_copy, node, code_cache):
                transmitter_nodes.append(node)
                break

    # Create a copy of start_nodes to modify
    valid_start_nodes = set(start_nodes)

    G_reverse = G_copy.reverse()
    # Check each start node
    for start_node in start_nodes:
        if start_node in dispatcher_nodes:
            continue
        if start_node in transmitter_nodes:
            continue
        for receiver_node in receiver_nodes:
            # Check if there's a path from start_node to receiver_node
            if nx.has_path(G_copy, start_node, receiver_node):
                # Trace backwards
                all_paths = nx.all_simple_paths(
                    G_reverse, source=receiver_node, target=start_node
                )
                all_nodes = set()
                for p in all_paths:
                    all_nodes.update(p)
                if len(all_nodes) == 0:
                    continue
                # all_nodes.remove(start_node)
                all_nodes.remove(receiver_node)
                # all_nodes  = all_nodes - set(transmitter_nodes)
                for t in transmitter_nodes:
                    if t not in all_nodes:
                        # There's no transmitter in any of the paths which
                        # means this node is an init node connecting to
                        # a node inside a transmitter-receiver field.
                        if start_node in valid_start_nodes:
                            valid_start_nodes.remove(start_node)
                            continue
    if len(valid_start_nodes) == 0:
        return [start_nodes[0]]
    return list(valid_start_nodes)


class Field_descriptor:
    def __init__(
        self,
        transmitter_mid: int,
        transmitter_attr: str,
        receiver_mid: int = -1,
        receiver_attr: str = None,
    ):
        self.parent_field: Field_descriptor = None
        self.level = 0
        self.contains_fields: list[Field_descriptor] = []
        self.transmitter_mid = transmitter_mid
        self.transmitter_attr = transmitter_attr
        self.receiver_mid = receiver_mid
        self.reciever_attr = receiver_attr
        self.field_nodes = set()
        self.init_nodes = []
        self.current_iterator = None

    def rewrite_field_receiver(self, mid):
        self.receiver_mid = mid

    def id(self):
        # The field is identified by its transmitter
        return "{}:{}".format(self.transmitter_mid, self.transmitter_attr)

    def name(self):
        return "{}:{}-{}:{}".format(
            self.transmitter_mid,
            self.transmitter_attr,
            self.receiver_mid,
            self.reciever_attr,
        )

    def __repr__(self):
        return "{}:{}-{}:{} i:{} n:{} sf:{} lvl:{}".format(
            self.transmitter_mid,
            self.transmitter_attr,
            self.receiver_mid,
            self.reciever_attr,
            len(self.init_nodes),
            len(self.field_nodes),
            len(self.contains_fields),
            self.level,
        )


# def get_dispatches(G, mid):
#   return G.nodes[mid].get("dispatches",None)


class Execution_node:
    def __init__(self, G: nx.DiGraph, node_mid, code_cache, wob_cache):
        self.node_mid = node_mid
        self.is_part_of_field = {}
        self.is_part_of_dispatch = None
        self.dispatches = []
        self.code_cache = code_cache
        self.wob_cache = wob_cache
        self.graph = G

    def __eq__(self, other):
        if isinstance(other, Execution_node):
            return self.node_mid == other.node_mid
        return False

    def __hash__(self):
        return hash(self.node_mid)  # Only relevant if using sets/dicts

    def __repr__(self):
        info = ""
        # if "is_part_of_field" in self.graph.nodes[self.node_mid]:
        #    info += "{} ".format(self.field() or "")
        if len(self.is_part_of_field) > 0:
            info += "{} ".format(self.field() or "")
        if len(self.dispatches) > 0:
            info += "dispatches: {}".format(len(self.dispatches))
        return "{} ({}) : [{}]".format(
            self.wob_cache[self.node_mid].name, self.node_mid, info
        )

    def field(self, attr="-"):
        return self.is_part_of_field.get(attr, None)

    def get_dispatches(self):
        return self.dispatches

    def copy(self, deep=False):
        if deep:
            return copy.deepcopy(self)
        return copy.copy(self)

    def __copy__(self):
        # Shallow copy: keep references to the same graph, code_cache, and wob_cache.
        new_obj = type(self)(self.graph, self.node_mid, self.code_cache, self.wob_cache)
        new_obj.is_part_of_field = self.is_part_of_field
        new_obj.is_part_of_dispatch = self.is_part_of_dispatch
        # Create a shallow copy of dispatches (if it exists)
        new_obj.dispatches = self.dispatches[:] if self.dispatches else []
        return new_obj


def get_next_neighbour(neighbourhood: dict):
    edge = next(neighbourhood["out_edges"])
    return edge[1]


def get_prev_neighbour(neighbourhood: dict):
    return next(neighbourhood["previous"])


class Default_node_iterator:
    """Perform a BFS topological sort in a directed graph and return each node in dependency order
    with beginning in any node that is not connected to a field and has no inbound edges."""

    def __init__(self, G: nx.DiGraph, wob_cache, code_cache, execution_planner):
        self.graph = G
        self.wob_cache = wob_cache
        self.code_cache = code_cache
        self.start_node_mid = None
        self.start_node = None
        self.execution_planner = execution_planner
        self.sorted_nodes = []
        self.current_index = 0
        self.encountered_transmitter = False
        self.neighbourhood = {"out_edges": iter([])}

    def get_start_node(self):
        return self.start_node

    def domain_exit(self, G, node_mid):
        pass

    def check_domain(self, G, node_mid, attr=None):
        # Rule 1: If we're already inside a Default_node_iterator, return true until we hit a node with at least one transmitter
        transmitter_attrs = [
            attr
            for attr in get_attributes(G, node_mid, self.code_cache)
            if has_transmitter_field(G, node_mid, attr, self.code_cache)
        ]

        if self.encountered_transmitter:
            return False

        if "is_dispatcher" in G.nodes[node_mid]:
            return False  # This is a processed Dispatcher_node

        if len(transmitter_attrs) > 0:
            self.encountered_transmitter = True
            return False

        return True

    def set_start_node(self, node_mid, neighbourhood={}):
        self.start_node_mid = node_mid
        self.sorted_nodes = []
        self.encountered_transmitter = False
        self.transmitter_receiver_count = 0  # Reset the counter

        _, subgraph = split_graph(self.graph.copy(), node_mid, include_node=True)

        subgraph = self.graph.subgraph(subgraph.nodes)

        # Perform a topological sort on the induced subgraph.
        # remove all init nodes.
        tr_pairs = find_transmitter_receiver_pairs(subgraph, self.code_cache)
        if len(tr_pairs) > 0:
            outermost_pairs = find_outermost_pair(subgraph, tr_pairs)

            G = self.graph.copy()
            for pair in outermost_pairs:
                a, r_G = split_graph(G.copy(), pair[1], include_node=True)
                l_G, b = split_graph(G.copy(), pair[0], include_node=True)
                nodes = r_G.nodes() | l_G.nodes()
                G = self.graph.subgraph(nodes).copy()
                G.add_edge(pair[0], pair[1])
            self.sorted_nodes = list(nx.topological_sort(G))
        else:
            # Eliminate nodes and paths not connected to the start node.
            component_sets = nx.weakly_connected_components(self.graph)
            for component in component_sets:
                if self.start_node_mid in component:
                    self.sorted_nodes = list(
                        nx.topological_sort(self.graph.subgraph(component))
                    )
                    break
        try:
            self.current_index = self.sorted_nodes.index(self.start_node_mid)
        except Exception:
            pass
        self.transmitter_receiver_count = 0  # Reset counter again for iteration
        self.start_node = Execution_node(
            self.graph, self.start_node_mid, self.code_cache, self.wob_cache
        )
        self.neighbourhood = {
            "out_edges": iter([n for n in self.graph.out_edges(self.start_node_mid)]),
            "previous": self.start_node_mid,
        }

    def __iter__(self):
        if not self.sorted_nodes:
            self.set_start_node(self.start_node_mid, self.neighbourhood)
        self.current_index = 0
        return self

    def __next__(self):
        self.current_index += 1
        if self.current_index >= len(self.sorted_nodes):
            return Execution_node(
                self.graph,
                get_next_neighbour(self.neighbourhood),
                self.code_cache,
                self.wob_cache,
            )
        node = self.sorted_nodes[self.current_index]
        en = Execution_node(self.graph, node, self.code_cache, self.wob_cache)
        self.neighbourhood = {
            "out_edges": iter([n for n in self.graph.out_edges(en.node_mid)]),
            "previous": [],
        }
        return en


def count_pairs(G, node, code_cache, stop=None):
    """
    Count transmitters and receivers in the path of successors to the given node.
    Returns:
    1 if transmitters > receivers
    -1 if transmitters < receivers
    0 if transmitters == receivers
    """
    # Initialize counters
    transmitters = 0
    receivers = 0

    # Create a queue for BFS traversal and a visited set to avoid cycles
    queue = deque([node])
    visited = set([node])

    # Check the starting node
    if has_transmitter_field(G, node, None, code_cache):
        transmitters += 1
    if has_receiver_field(G, node, None, code_cache):
        receivers += 1

    # BFS to explore all successors
    while queue:
        current = queue.popleft()
        if stop == current:
            break
        # Check all successors of the current node
        for successor in G.successors(current):
            if successor not in visited:
                visited.add(successor)
                queue.append(successor)

                # Count if the successor is a transmitter or receiver
                if has_transmitter_field(G, successor, None, code_cache):
                    transmitters += 1
                if has_receiver_field(G, successor, None, code_cache):
                    receivers += 1

    # Compare counts and return result
    if transmitters > receivers:
        return 1
    elif transmitters < receivers:
        return -1
    else:  # transmitters == receivers
        return 0


class Graph_DFS_iterator:
    """
    Produce a topological ordering of nodes (starting from start_node) using a modified DFS.
    When multiple successors are available, non‑transmitter nodes are prioritized over transmitter nodes.

    The DFS collects nodes in post‑order; reversing that order yields a valid topological sort.
    """

    def __init__(self, G: nx.DiGraph, start_node_mid, code_cache):
        self.G = G
        self.start_node = start_node_mid
        self.code_cache = code_cache
        self.visited = set()
        self.sorted_nodes = []
        # Run the modified DFS starting from the start_node.
        self.modified_dfs(self.start_node)
        # Reverse postorder to get a valid topological order.
        self.sorted_nodes.reverse()
        self.index = 0

    def modified_dfs(self, node):
        """
        Recursively visit nodes. When choosing the next node, sort successors so that
        non‑transmitter nodes are processed before transmitter nodes.
        """
        self.visited.add(node)
        # Get successors. If necessary, you could filter here to only include descendants of start_node.
        successors = list(self.G.successors(node))

        # Sort successors: non-transmitters get priority (priority 0) over transmitters (priority 1).
        def ct(n):
            count = count_pairs(self.G, n, self.code_cache)
            if count > 0:
                return 1
            if count < 0:
                return 0
            if count == 0:
                return 2

        if len(successors) > 1:
            successors.sort(key=lambda n: ct(n))
        for neighbor in successors:
            if neighbor not in self.visited:
                self.modified_dfs(neighbor)
        # Append after processing all descendants (post-order).
        self.sorted_nodes.append(node)

    def __iter__(self):
        return self

    def __next__(self):
        # print ("DFS iterator: self.sorted_nodes= ", self.sorted_nodes)
        if self.index < len(self.sorted_nodes):
            node = self.sorted_nodes[self.index]
            self.index += 1
            return node
        raise StopIteration


class Graph_BFS_iterator:
    """
    Produce a topological order of nodes (starting from start_node)
    but when multiple nodes are available, non-transmitter nodes are
    chosen before transmitter nodes.

    A node is considered a transmitter if has_transmitter_field(G, node, None, code_cache)
    returns True.
    """

    def __init__(self, G: nx.DiGraph, start_node_mid, code_cache):
        self.G = G
        self.start_node = start_node_mid
        self.code_cache = code_cache
        self.sorted_nodes = self.modified_topological_sort()
        self.index = 0

    def node_priority(self, node):
        # Non-transmitter nodes get priority 0, transmitter nodes 1.
        # Lower numbers are higher priority.
        return 0 if has_transmitter_field(self.G, node, None, self.code_cache) else 1

    def modified_topological_sort(self):
        # Build the subgraph of the start node and its descendants.
        descendants = nx.descendants(self.G, self.start_node)
        descendants.add(self.start_node)
        subgraph = self.G.subgraph(descendants)

        # Compute in-degrees in the subgraph.
        in_degree = {node: subgraph.in_degree(node) for node in subgraph.nodes()}

        # Use a heap (priority queue) to select nodes.
        # Each entry is a tuple (priority, counter, node)
        # The counter is used to break ties (preserving a consistent order).
        pq = []
        counter = 0
        for node, deg in in_degree.items():
            if deg == 0:
                heapq.heappush(pq, (self.node_priority(node), counter, node))
                counter += 1

        sorted_nodes = []
        while pq:
            _, _, node = heapq.heappop(pq)
            sorted_nodes.append(node)
            for neighbor in subgraph.successors(node):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    heapq.heappush(
                        pq, (self.node_priority(neighbor), counter, neighbor)
                    )
                    counter += 1
        return sorted_nodes

    def __iter__(self):
        return self

    def __next__(self):
        if self.index < len(self.sorted_nodes):
            node = self.sorted_nodes[self.index]
            self.index += 1
            return node
        else:
            raise StopIteration


def is_nested(G: nx.DiGraph, outer_node, inner_node) -> bool:
    """
    Checks if one field node is nested within another.

    Args:
        G: The directed graph.
        outer_node: The potential outer field node.
        inner_node: The potential inner field node.

    Returns:
        True if inner_node is nested within outer_node, False otherwise.
    """
    try:
        # Check if there's a path from the outer transmitter to the inner transmitter AND
        # a path from the inner receiver to the outer receiver. This confirms nesting.
        path1 = list(nx.all_simple_paths(G, source=outer_node, target=inner_node))
        path2 = list(nx.all_simple_paths(G, source=inner_node, target=outer_node))
        return bool(path1 and path2)
    except nx.NetworkXNoPath:
        return False


def find_outermost_pair(graph: nx.DiGraph, tr_pairs):
    @functools.lru_cache(maxsize=1024)
    def calculate_field(n1, n2):
        # Start with endpoints
        field = {n1, n2}

        # Perform a BFS starting from n1 (avoiding n2) to get connected nodes
        visited = {n1}
        queue = deque([n1])
        while queue:
            node = queue.popleft()
            for neighbor in graph.neighbors(node):
                if neighbor not in visited and neighbor != n2:
                    visited.add(neighbor)
                    queue.append(neighbor)
        field.update(visited)

        # Try to add the shortest path between n1 and n2 if it exists
        try:
            path = nx.shortest_path(graph, source=n1, target=n2)
            field.update(path)
        except nx.NetworkXNoPath:
            pass

        # Optionally, add paths to leaves (nodes of degree 1)
        leaves = [
            node
            for node in graph.nodes()
            if node not in {n1, n2} and graph.degree(node) == 1
        ]
        for leaf in leaves:
            try:
                path = nx.shortest_path(graph, source=n1, target=leaf)
                if n2 not in path:  # Only add paths that do not cross n2
                    field.update(path)
            except nx.NetworkXNoPath:
                continue

        return field

    # Precompute the field for every pair in tr_pairs
    pair_to_field = {}
    for pair in tr_pairs:
        pair_to_field[pair] = calculate_field(pair[0], pair[1])

    outermost_pairs = []
    # Check each candidate pair to see if it is nested within any other pair.
    # We say that a pair p = (n1, n2) is nested if there exists another pair q such that
    # both n1 and n2 are inside the field of q.
    for pair in tr_pairs:
        is_nested = False
        for other_pair in tr_pairs:
            if pair == other_pair:
                continue
            field_other = pair_to_field[other_pair]
            if pair[0] in field_other and pair[1] in field_other:
                is_nested = True
                break
        if not is_nested:
            outermost_pairs.append(pair)

    return outermost_pairs


def find_enveloping_tr_pair(graph, mid, tr_pairs, inner_most=True, _field_cache={}):
    @functools.lru_cache(maxsize=1024)
    def calculate_field(n1, n2):
        # Check if already in cache
        pair = (n1, n2)
        if pair in _field_cache:
            return _field_cache[pair]

        field = {n1, n2}  # Include endpoints

        # Use BFS to find all nodes in the field more efficiently
        visited = {n1}
        queue = deque([n1])

        while queue:
            node = queue.popleft()
            for neighbor in graph.neighbors(node):
                if neighbor not in visited and neighbor != n2:
                    visited.add(neighbor)
                    queue.append(neighbor)

        # Add path between n1 and n2
        try:
            path = nx.shortest_path(graph, source=n1, target=n2)
            field.update(path)
        except nx.NetworkXNoPath:
            pass

        # Add paths to leaves
        leaves = [
            node
            for node in graph.nodes()
            if node not in {n1, n2} and graph.degree(node) == 1
        ]
        for leaf in leaves:
            try:
                path = nx.shortest_path(graph, source=n1, target=leaf)
                if n2 not in path:  # Discard paths that include n2
                    field.update(path)
            except nx.NetworkXNoPath:
                continue

        field.update(visited)
        _field_cache[pair] = field
        return field

    @functools.lru_cache(maxsize=1024)
    def is_node_in_field(n1, n2, n):
        field = calculate_field(n1, n2)
        return n in field

    # If inner_most is False, return the first matching pair
    if not inner_most:
        for p in tr_pairs:
            if is_node_in_field(p[0], p[1], mid):
                return p
        return None

    # Pre-calculate all fields for all pairs
    fields = {}
    for p in tr_pairs:
        field = calculate_field(p[0], p[1])
        fields[p] = field

    # Find matching pairs
    matching_pairs = [(p, len(field)) for p, field in fields.items() if mid in field]

    if matching_pairs:
        return min(matching_pairs, key=lambda x: x[1])[0]
    return None


class Field_iterator:
    """1. Extract all paths from transmitter to receiver.
    2. Expand the graph to include all leaf node branches.
    3. Sort the graph in topological order but put the receiver node last.
    4. Iterate the list and return each node id.
    5. If the current node id is a transmitter field then push a Field_descriptor on the stack and
     and start tracking the next nested field.
    6. If a node in the field has inbound edges we import this subgraph and store it as a topologically sorted list of nodes in the current_field.init_nodes list.
    """

    def __init__(
        self,
        G: nx.DiGraph,
        wob_cache,
        code_cache,
        execution_planner,
        dispatch_field: Field_descriptor = None,
    ):
        self.graph = G
        self.wob_cache = wob_cache
        self.code_cache = code_cache
        self.start_node_mid = None
        self.execution_planner = execution_planner
        self.field_stack = []
        self.processed_fields = {}  # all field pairs as Field_descriptors.
        self.is_done = False
        self.last_node_mid = None  # the last node id we processed. At the end it will be a receiver node mid.
        # self.current_iterator = None
        self.nesting_level = 0
        self.start_node = None
        self.last_node_in_field = False
        self.dispatch_field = dispatch_field

    def get_start_node(self):
        return self.start_node

    def domain_exit(self, G, node_mid):
        pass

    def check_domain(self, G, node_mid, attr=None):
        # Rule 2: If we're inside a Field_iterator, return true as long as nesting level is zero
        # If not inside a Field_iterator, return true if node has only one transmitter attribute

        if len(self.field_stack) > 0:
            return True
        elif self.last_node_in_field:
            self.last_node_in_field = False
            return True
        # elif has_receiver_field(G, node_mid, attr, self.code_cache):
        #   return True
        else:  # We're not inside a Field_iterator
            transmitter_attrs = [
                attr for attr in get_attributes(G, node_mid, self.code_cache)
            ]
            transmitter_attrs = [
                attr
                for attr in transmitter_attrs
                if has_transmitter_field(G, node_mid, attr, self.code_cache)
            ]
            return len(transmitter_attrs) == 1

    def set_start_node(self, node_mid, neighbourhood={}):
        self.start_node_mid = node_mid
        self.last_node_mid = node_mid
        self.nesting_level = 0
        self.is_done = False
        self.visited = set()
        self.neighbourhood = neighbourhood

        G = self.graph.copy()
        # print ([n for n in nx.ancestors(G, self.start_node_mid)])
        G.remove_nodes_from(nx.ancestors(G, self.start_node_mid))
        # Create a field descriptor
        if self.dispatch_field is not None:
            field = self.dispatch_field
            self.field_stack.append(field)
            # We still need to calculate the tr_pairs for the dispatcher which means we need to
            self.tr_pairs = find_transmitter_receiver_pairs(G, self.code_cache)
            last_receiver_mid = find_last_reciever_mid(
                self.graph,
                field.transmitter_mid,
                field.transmitter_attr,
                self.code_cache,
            )
            assert last_receiver_mid is not None, (
                "Every dispatch graph must end in a field receiver."
            )
            self.tr_pairs.append((field.transmitter_mid, last_receiver_mid))
            assert len(self.tr_pairs) != 0, "No transmitter-receiver pairs detected."
        else:
            self.tr_pairs = find_transmitter_receiver_pairs(G, self.code_cache)
            assert len(self.tr_pairs) != 0, "No transmitter-receiver pairs detected."
            # print ("DEBUG: pairs: ",','.join([str(p) for p in self.tr_pairs]))
            enveloping_pair = find_enveloping_tr_pair(
                self.graph, self.start_node_mid, self.tr_pairs
            )
            field = Field_descriptor(self.start_node_mid, "-", enveloping_pair[1])
            self.field_stack.append(field)
        if "is_part_of_field" in self.graph.nodes[node_mid]:
            self.graph.nodes[self.start_node_mid]["is_part_of_field"]["-"] = field
            if self.dispatch_field:
                self.graph.nodes[self.start_node_mid]["is_part_of_field"][
                    field.transmitter_attr
                ] = field
        else:
            self.graph.nodes[self.start_node_mid]["is_part_of_field"] = {"-": field}
            if self.dispatch_field:
                self.graph.nodes[self.start_node_mid]["is_part_of_field"] = {
                    field.transmitter_attr: field
                }

        self.visited.add(self.start_node_mid)
        self.start_node = Execution_node(
            self.graph, self.start_node_mid, self.code_cache, self.wob_cache
        )
        inbound_nodes = list(self.graph.predecessors(self.start_node.node_mid))
        self.process_inbound_nodes(field, inbound_nodes)
        self.start_node.is_part_of_field["-"] = field
        if self.dispatch_field:
            self.start_node.is_part_of_field[field.transmitter_attr] = field
        self.current_iterator = Graph_DFS_iterator(
            G, self.start_node_mid, self.code_cache
        )
        # That is it! We are now in a field as long as there's a Field_descriptor on the stack!

    def __iter__(self):
        self.set_start_node(self.start_node_mid, self.neighbourhood)
        self.nesting_level = 0
        self.is_done = False
        return self

    def process_inbound_nodes(self, current_field, inbound_nodes):
        for inbound_node in inbound_nodes:
            # Check if this inbound node is already part of the field
            if inbound_node in current_field.field_nodes:
                continue

            # Check if there's a path from the current transmitter to this inbound node
            # If there is, it's not an initialization node
            if nx.has_path(self.graph, current_field.transmitter_mid, inbound_node):
                continue

            # Check if the inbound node has a path to any node already visited by the execution planner
            # Get the nodes already visited by the execution planner
            visited_nodes = {
                exec_node.node_mid
                for exec_node in self.execution_planner.execution_plan
            }

            # Check if there's a path from the inbound node to any visited node
            # Use any() with a generator expression for efficiency
            if any(
                nx.has_path(self.graph, inbound_node, visited_node)
                for visited_node in visited_nodes
            ):
                # This inbound node has a path to a node already visited by the execution planner
                # We should skip it to avoid backtracking
                continue

            # This is an initialization node - collect its subgraph
            init_subgraph_nodes = {inbound_node}

            init_subgraph_nodes.update(nx.ancestors(self.graph, inbound_node))

            # Create a subgraph for initialization
            init_subgraph = self.graph.subgraph(init_subgraph_nodes)
            # print ("DEBUG: init_subgraph.nodes= ", init_subgraph.nodes())

            # Create a temporary execution planner for this subgraph
            temp_planner = Generate_execution_plan(
                self.code_cache, self.wob_cache, compile_subgraph=True
            )

            # Generate an execution plan for the initialization subgraph
            # print ("---------- Field_iterator: Generate execution plan for subgraph")
            init_execution_plan = temp_planner(init_subgraph)
            # print ("---------- Field_iterator: Done generating execution plan for subgraph")

            for k, v in temp_planner.transmitter_mid_to_field_descriptor.items():
                self.execution_planner.transmitter_mid_to_field_descriptor[k] = v
            for k, v in temp_planner.receiver_mid_to_field_descriptor.items():
                self.execution_planner.receiver_mid_to_field_descriptor[k] = v

            for u, v, data in temp_planner.execution_graph.edges(data=True):
                if self.graph.has_edge(u, v):
                    self.graph[u][v].update(data)  # Efficiently update edge attributes
            for tnode, data in temp_planner.execution_graph.nodes(data=True):
                if self.graph.has_node(tnode):
                    self.graph.nodes[tnode].update(
                        data
                    )  # Efficiently update node attributes

            # If this is connected to nodes outside of the field we might get some duplicates; lets remove them
            visited = set([e.node_mid for e in self.execution_planner.execution_plan])
            filtered = [e for e in init_execution_plan if e.node_mid not in visited]
            # Add the execution nodes to our initialization nodes list
            current_field.init_nodes.extend(filtered)
            # Add these nodes to the field so we don't process them again
            # current_field.field_nodes.update(init_subgraph_nodes)

    def __next__(self):
        if len(self.field_stack) == 0:
            # If we don't have a Field_descriptor on the stack we're done with the Field_iterator.
            # When we're done, let the execution planner know the last node ID
            self.execution_planner.last_node_mid = self.last_node_mid
            raise StopIteration

        try:
            current_field = self.field_stack[-1]
            # Get the next node from the current iterator
            node = next(self.current_iterator)
            while node in self.visited or node in current_field.field_nodes:
                node = next(self.current_iterator)
            self.visited.add(node)
            self.last_node_mid = node
            if "is_part_of_field" not in self.graph.nodes[node]:
                self.graph.nodes[node]["is_part_of_field"] = {}
            if self.dispatch_field:
                self.graph.nodes[node]["is_part_of_field"][
                    self.dispatch_field.transmitter_attr
                ] = current_field
            self.graph.nodes[node]["is_part_of_field"]["-"] = current_field

            # Get all inbound edges to this node
            inbound_nodes = list(self.graph.predecessors(node))
            self.process_inbound_nodes(current_field, inbound_nodes)

            # Check if this node is a transmitter for a nested field
            tr_pair = find_enveloping_tr_pair(self.graph, node, self.tr_pairs)
            if tr_pair is None:
                # print ("INIT NODE: ",node)
                en = Execution_node(self.graph, node, self.code_cache, self.wob_cache)
                en.is_part_of_field["-"] = current_field
                if self.dispatch_field:
                    en.is_part_of_field[self.dispatch_field.transmitter_attr] = (
                        current_field
                    )
                self.last_node_mid = node
                return en

            if tr_pair[0] != current_field.transmitter_mid:
                # This is a transmitter for a nested field
                # Increment nesting level
                current_field: Field_descriptor = Field_descriptor(
                    tr_pair[0], "-", tr_pair[1]
                )
                if "is_part_of_field" in self.graph.nodes[node]:
                    self.graph.nodes[node]["is_part_of_field"]["-"] = current_field
                    if self.dispatch_field:
                        self.graph.nodes[node]["is_part_of_field"][
                            self.dispatch_field.transmitter_attr
                        ] = current_field
                else:
                    self.graph.nodes[node]["is_part_of_field"] = {"-": current_field}
                    if self.dispatch_field:
                        self.graph.nodes[node]["is_part_of_field"] = {
                            self.dispatch_field.transmitter_attr: current_field
                        }
                if self.field_stack:
                    current_field.parent_field = self.field_stack[-1]
                    current_field.parent_field.contains_fields.append(current_field)
                self.field_stack.append(current_field)
                self.nesting_level += 1
                current_field.level = self.nesting_level

                # Create a new DFS iterator for this nested field
                # self.current_iterator = nx.topological_sort(self.graph.subgraph(nx.descendants(self.graph,node))) #Graph_DFS_iterator(self.graph, node)

            # Check if this node is a receiver that matches our transmitters
            receiver_attrs = [
                attr
                for attr in get_attributes(self.graph, node, self.code_cache)
                if has_receiver_field(self.graph, node, attr, self.code_cache)
            ]

            if receiver_attrs:
                assert node == tr_pair[1], (
                    "The receiver {} doesn't match the pair {}".format(node, tr_pair)
                )

                # Check if this receiver completes the current field
                # For simplicity, we'll use the first receiver attribute
                receiver_attr = receiver_attrs[0]

                # Check if this is a valid receiver for our current field
                # In a real implementation, you'd need to check if this receiver actually
                # corresponds to the current transmitter

                # Pop the field from the stack
                self.field_stack.pop()
                self.nesting_level -= 1

                current_field.receiver_mid = node
                current_field.reciever_attr = receiver_attr
                self.processed_fields[current_field.transmitter_mid] = current_field
                # Update dictionaries in the execution planner
                self.execution_planner.register_transmitter_field(current_field)
                self.last_node_in_field = True  # this is used in check_domain()

            if current_field:
                current_field.field_nodes.add(node)
            en = Execution_node(self.graph, node, self.code_cache, self.wob_cache)
            en.is_part_of_field["-"] = current_field
            return en

        except StopIteration:
            if len(self.field_stack) > 0:
                current_field = self.field_stack[-1]
                # print ("DEBUG : We exhausted the BFS search but we still have the following fields on the stack:")
                # for f in self.field_stack:
                #   print (f)
                raise StopIteration
            else:
                # No more fields to process
                self.is_done = True
                raise StopIteration


def collect_inbound_set(G: nx.DiGraph, edge, ignore: set):
    """
    Collects the set of nodes that can reach the source of the given edge,
    along with all their successors, excluding nodes in the ignore set.

    Parameters:
    -----------
    G : nx.DiGraph
        A directed graph
    edge : tuple
        An edge in the graph, represented as (source, target)
    ignore : set
        A set of nodes to ignore during traversal

    Returns:
    --------
    set
        A set of nodes that can reach the source of the edge and their successors
    """
    source, _ = edge

    # Skip if source is in ignore set
    if source in ignore:
        return set()

    # Find all nodes that can reach the source (predecessors)
    inbound_nodes = set({source})

    def collect_predecessors(node):
        for pred in G.predecessors(node):
            if pred not in ignore and pred not in inbound_nodes:
                inbound_nodes.add(pred)
                collect_predecessors(pred)

    # Start collecting predecessors from the source
    collect_predecessors(source)

    # For each discovered node, add all its successors
    result_set = set(inbound_nodes)

    return result_set


class Dispatch_iterator:
    """The dispatch iterator is activated when a node has several transmitter attributes.
    When the iterator is initialised it:
    1. Collect each subgraph originating from each of the transmitter attributes.
    2. When iterating use a Default_node_iterator or a Field_iterator to traverse each subgraph
    """

    def __init__(self, G: nx.DiGraph, wob_cache, code_cache, execution_planner):
        self.graph = G
        self.dispatch_graph = None
        self.wob_cache = wob_cache
        self.code_cache = code_cache
        self.start_node_mid = None
        self.start_node = None
        self.execution_planner: Generate_execution_plan = execution_planner
        self.subgraph_iterators = []
        self.current_iterator = None
        self.all_branches_iterated = False
        self.is_done = False
        self.last_node_mid = None
        self.exit_nodes = set()
        self.exit_node_itr = None
        self.dispatches: list = []  # {"plan": dispatch_plan}
        self.commit_node = False
        self.init_nodes: list = []

    def get_start_node(self):
        # print ("+++ Get Dispatch start node")
        return self.start_node

    def get_dispatches(self):
        return self.dispatches

    def domain_exit(self, G, node_mid):
        dispatch_nodes = set()
        for dispatcher in self.get_dispatches():
            for node in dispatcher["plan"]:
                dispatch_nodes.add(node.node_mid)
        # self.execution_planner.execution_graph[self.start_node_mid]["dispatch_graph"] = self.graph.subgraph(dispatch_nodes)
        # dispatch_graph = self.graph.subgraph(dispatch_nodes.union([self.start_node_mid])).copy()
        self.execution_planner.execution_graph.remove_nodes_from(dispatch_nodes)

    def check_domain(self, G, node_mid, attr=None):
        # Rule 3: If we're inside a Dispatch_iterator, return true only when all subgraph branches have been iterated
        # If not inside a Dispatch_iterator, return true only if current node is a transmitter with more than one transmitter attributes

        if self.commit_node:
            self.commit_node = False
            return True
        if self.subgraph_iterators:
            return self.all_branches_iterated
        elif "is_dispatcher" in G.nodes[node_mid]:
            return True
        else:  # We're not inside a Dispatch_iterator
            transmitter_attrs = [
                attr
                for attr in get_attributes(G, node_mid, self.code_cache)
                if has_transmitter_field(G, node_mid, attr, self.code_cache)
            ]
            return len(transmitter_attrs) > 1

    def set_start_node(
        self, node_mid, neighbourhood={"out_edges": iter([]), "previous": []}
    ):
        self.start_node_mid = node_mid
        if self.all_branches_iterated is True:
            self.exit_node_itr = iter(self.exit_nodes)  # reset exit node iterator
            return
        self.all_branches_iterated = False
        self.is_done = False
        self.start_node = Execution_node(
            self.graph, self.start_node_mid, self.code_cache, self.wob_cache
        )
        dispatch_graph = self.graph.copy()
        self.neighbourhood = neighbourhood

        # Find all transmitter attributes for this node
        transmitter_attrs = [
            attr
            for attr in get_attributes(self.graph, node_mid, self.code_cache)
            if has_transmitter_field(self.graph, node_mid, attr, self.code_cache)
            and node_mid
        ]

        # if len(transmitter_attrs) <= 1:
        #  return

        # Collect subgraphs for each transmitter attribute
        self.subgraph_iterators = []
        field_graph: nx.DiGraph = None
        for attr in transmitter_attrs:
            # Find all nodes connected to this transmitter attribute
            for src, dst, data in self.graph.out_edges(node_mid, data=True):
                dispatch_field = Field_descriptor(node_mid, attr)
                edge_attrs = get_node_attributes(self.graph, node_mid, dst)
                if edge_attrs and any(edge_attr[0] == attr for edge_attr in edge_attrs):
                    l_G, r_G = split_graph(dispatch_graph, dst, include_node=True)
                    # There might be inbound nodes to dst which we must include
                    G_inbound_set = set()
                    for e in dispatch_graph.in_edges(dst):
                        if e[0] == src:
                            continue
                        G_inbound_set.update(
                            collect_inbound_set(dispatch_graph, e, set())
                        )

                    G_inbound_set.update(r_G.nodes())
                    field_graph = self.graph.subgraph(G_inbound_set).copy()
                    field_graph.add_node(node_mid)
                    field_graph.nodes[node_mid]["is_part_of_field"] = {}
                    field_graph.add_edge(
                        node_mid, dst, **self.graph.edges[node_mid, dst]
                    )

                    # Generate an execution plan from this subgraph.
                    temp_planner = Generate_execution_plan(
                        self.code_cache,
                        self.wob_cache,
                        start_node_id=dst,
                        dispatch_field=dispatch_field,
                    )
                    # print ("---------- Dispatch_iterator: Generate execution plan for subgraph")
                    plan = temp_planner(field_graph)
                    # print ("---------- Dispatch_iterator: Done generating execution plan for subgraph")
                    dispatch = {
                        "plan": plan,
                        "dispatch": attr,
                        "transmitter_mid": node_mid,
                        "start_node_mid": dst,
                        "graph": dispatch_graph,
                        "field": dispatch_field,
                    }
                    self.dispatches.append(dispatch)
                    dispatch_field.receiver_mid = plan[
                        -1
                    ].node_mid  # Last field is the receiver field per definition.
                    # print ("DEBUG: dispatch_field.receiver_mid=", dispatch_field.receiver_mid)
                    self.init_nodes.extend(dispatch_field.init_nodes)
                    dispatch_field.field_nodes = [n.node_mid for n in plan]
                    # print ("DEBUG: start_node.is_part_of_field= ",dispatch_field)
                    self.start_node.is_part_of_field[attr] = dispatch_field
                    for en in plan:
                        en.is_part_of_dispatch = dispatch
                        self.graph.nodes[en.node_mid]["dispatch"] = dispatch
                        if attr not in en.is_part_of_field:
                            en.is_part_of_field[attr] = dispatch_field
                        if "-" not in en.is_part_of_field:
                            en.is_part_of_field["-"] = dispatch_field
                self.execution_planner.register_transmitter_field(dispatch_field)
        self.start_node.dispatches = self.dispatches
        self.all_branches_iterated = True

    def __iter__(self):
        if not self.subgraph_iterators:
            self.set_start_node(self.start_node_mid)
        self.is_done = False
        return self

    def __next__(self):
        if len(self.init_nodes) > 0:
            # inject init nodes in execution plan
            last_node = self.execution_planner.execution_plan.pop()
            assert last_node.node_mid == self.start_node.node_mid, (
                "Dispatcher node not in execution plan."
            )
            self.execution_planner.execution_plan.extend(self.init_nodes)
            self.execution_planner.execution_plan.append(last_node)
            self.init_nodes = []
        try:
            return Execution_node(
                self.graph,
                get_next_neighbour(self.neighbourhood),
                self.code_cache,
                self.wob_cache,
            )
        except StopIteration:
            self.is_done = True
            self.commit_node = True
            raise StopIteration


class Generate_execution_plan:
    def __init__(
        self,
        code_cache: dict,
        wob_cache: dict,
        start_node_id=None,
        dispatch_field: Field_descriptor = None,
        compile_subgraph=False,
    ):
        self.code_cache = code_cache
        self.wob_cache = wob_cache
        self.execution_plan = []
        self.execution_graph = None
        self.next_node_itr = None
        self.transmitter_mid_to_field_descriptor = {}  # dict->list
        self.receiver_mid_to_field_descriptor = {}
        self.last_node_mid = None
        self.start_node_id = start_node_id
        self.dispatch_field: str = dispatch_field
        self.dispatcher: dict = {}
        self.compile_subgraph = False

    def register_transmitter_field(self, field):
        if field.transmitter_mid not in self.transmitter_mid_to_field_descriptor:
            self.execution_graph.nodes[field.transmitter_mid]["is_part_of_field"][
                field.transmitter_attr
            ] = field
            self.execution_graph.nodes[field.transmitter_mid]["is_part_of_field"][
                "-"
            ] = field
            self.transmitter_mid_to_field_descriptor[field.transmitter_mid] = [field]
        else:
            self.transmitter_mid_to_field_descriptor[field.transmitter_mid].append(
                field
            )
        self.receiver_mid_to_field_descriptor[field.receiver_mid] = field

    def select_iterator_strategy(self, node_mid: int):
        # First check if the current iterator can handle the node
        if self.next_node_itr and self.next_node_itr.check_domain(
            self.execution_graph, node_mid
        ):
            return self.next_node_itr

        # Try each iterator type to see which one can handle this node
        iterators = [
            Default_node_iterator(
                self.execution_graph, self.wob_cache, self.code_cache, self
            ),
            Field_iterator(self.execution_graph, self.wob_cache, self.code_cache, self),
        ]

        for iterator in iterators:
            if (
                iterator.check_domain(self.execution_graph, node_mid)
                or node_mid in self.dispatcher
            ):
                if node_mid in self.dispatcher:
                    iterator = self.dispatcher[node_mid]
                # print ("** SWITCH: ", type(iterator))
                iterator.set_start_node(node_mid)
                # issue a signal to the current iterator that we're leaving
                if self.next_node_itr:
                    self.next_node_itr.domain_exit(self.execution_graph, node_mid)
                return iterator

        # If no specific iterator can handle it, use the default
        default_iterator = Default_node_iterator(
            self.execution_graph, self.wob_cache, self.code_cache, self
        )
        default_iterator.set_start_node(node_mid)
        return default_iterator

    def __call__(self, G: nx.DiGraph):
        self.execution_graph = G
        self.execution_plan = []  # list(Execution_node)
        self.transmitter_mid_to_field_descriptor = {}
        self.receiver_mid_to_field_descriptor = {}

        # Update start_nodes with the valid ones
        start_node = None
        if self.start_node_id is None:
            start_nodes = calculate_start_nodes(G, self.code_cache)
            start_node = start_nodes[0]
            if start_nodes is None:
                # If there are no nodes with no inbound edges, pick any node
                if self.execution_graph.nodes():
                    start_node = list(self.execution_graph.nodes())[0]
                else:
                    return self.execution_plan  # Empty graph
        else:
            start_node = self.start_node_id

        # Find all Dispatcher nodes and run those.
        if self.dispatch_field is None:
            dispatcher_nodes = [
                n
                for n in self.execution_graph.nodes()
                if is_dispatcher_node(self.execution_graph, n, self.code_cache)
            ]
            for n in dispatcher_nodes:
                dn = Dispatch_iterator(
                    self.execution_graph, self.wob_cache, self.code_cache, self
                )
                dn.set_start_node(n)
                dn.domain_exit(self.execution_graph, n)
                dn.neighbourhood = {
                    "out_edges": iter(
                        [mid for mid in self.execution_graph.out_edges(n)]
                    ),
                    "previous": self.last_node_mid,
                }
                self.dispatcher[n] = dn
                self.execution_graph.nodes[n]["is_dispatcher"] = True
            # Initialize with default iterator
            self.next_node_itr = self.select_iterator_strategy(start_node)
        elif not self.compile_subgraph:
            # We're in the dispatcher. Start iterator is a Field_iterator because each Dispatch is a field.
            # print ("** Switch to Field_iterator in a dispatch.")
            self.next_node_itr = Field_iterator(
                G,
                self.wob_cache,
                self.code_cache,
                self,
                dispatch_field=self.dispatch_field,
            )
        else:
            # Initialize with default iterator
            self.next_node_itr = self.select_iterator_strategy(start_node)
        self.next_node_itr.set_start_node(start_node)
        # Add to execution plan
        exec_node = self.next_node_itr.get_start_node()
        self.last_node_mid = exec_node.node_mid
        # print ("** COMMIT: ",exec_node)
        self.execution_plan.append(exec_node)
        visited_nodes = set()

        try:
            while True:
                try:
                    n = next(self.next_node_itr)
                    # print ("** NEXT = ", n)
                    if n in visited_nodes:
                        continue
                except StopIteration:
                    new_itr = self.select_iterator_strategy(self.last_node_mid)
                    # We should get_start_node() and then commit?
                    if new_itr != self.next_node_itr:
                        self.next_node_itr = new_itr
                        n = (
                            self.next_node_itr.get_start_node()
                        )  # if we fail here all nodes are done.
                    else:
                        n = next(self.next_node_itr)
                    while n.node_mid == self.last_node_mid:
                        n = next(self.next_node_itr)
                # print ("** NEXT = ", n)

                if n in visited_nodes:
                    continue
                # Check if we need to change iterator strategy for the next nodes
                # print ("** CHECK = ", n)
                if not self.next_node_itr.check_domain(G, n.node_mid):
                    self.next_node_itr = self.select_iterator_strategy(n.node_mid)
                    n = self.next_node_itr.get_start_node()

                visited_nodes.add(n)
                self.last_node_mid = n.node_mid

                # Add to execution plan
                # print ("** COMMIT: ",n)
                self.execution_plan.append(n)
                try:
                    n = next(self.next_node_itr)
                    # print ("** NEXT = ", n)
                except StopIteration:
                    new_itr = self.select_iterator_strategy(self.last_node_mid)
                    if new_itr != self.next_node_itr:
                        self.next_node_itr = new_itr
                        n = (
                            self.next_node_itr.get_start_node()
                        )  # if we fail here all nodes are done.
                    else:
                        n = next(self.next_node_itr)
                    # print ("** NEXT = ", n)
                    while n.node_mid == self.last_node_mid:
                        n = next(self.next_node_itr)
                    # print ("** NEXT = ", n)

                if n in visited_nodes:
                    continue

                # print ("** CHECK = ",n)
                if not self.next_node_itr.check_domain(G, n.node_mid):
                    self.next_node_itr = self.select_iterator_strategy(n.node_mid)
                    n = self.next_node_itr.get_start_node()

                # Add to execution plan
                visited_nodes.add(n)
                self.last_node_mid = n.node_mid
                # print ("** COMMIT: ",n)
                self.execution_plan.append(n)
        except StopIteration:
            # We've processed all nodes
            # print ("** DONE")
            pass

        plan_with_init_nodes = []
        for n in self.execution_plan:
            fields = n.is_part_of_field
            f = fields.get("-", None)
            if f is not None and f.transmitter_mid == n.node_mid:
                plan_with_init_nodes.extend(f.init_nodes)
            plan_with_init_nodes.append(n)
        self.execution_plan = plan_with_init_nodes
        return self.execution_plan
