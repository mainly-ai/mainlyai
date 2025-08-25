from .security.security_context import Security_context
from .miranda_llm import ArgotModelProvider

from .workflow_objects import (
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
)

__all__ = [
    "Security_context",
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
    "miranda",
]

_all_wob_classes = [
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
]

_table_to_object_lookup = {
    "CODE": Code_block,
    "CODE_BLOCK": Code_block,
    "COMPUTE_POLICY": Compute_policy,
    "COMPUTE_RESOURCE_GROUP": Compute_resource_group,
    "DASHBOARD": Dashboard,
    "DEPLOYMENT": Deployment,
    "DOCKER_IMAGE": Docker_image,
    "DOCKER_JOB": Docker_job,
    "KNOWLEDGE_OBJECT": Knowledge_object,
    "MODEL": Model,
    "PROJECT": Project,
    "STORAGE_POLICY": Storage_policy,
}
_object_to_table_lookup = {
    Code_block: "CODE",
    Compute_policy: "COMPUTE_POLICY",
    Compute_resource_group: "COMPUTE_RESOURCE_GROUP",
    Dashboard: "DASHBOARD",
    Deployment: "DEPLOYMENT",
    Docker_image: "DOCKER_IMAGE",
    Docker_job: "DOCKER_JOB",
    Knowledge_object: "KNOWLEDGE_OBJECT",
    Model: "MODEL",
    Project: "PROJECT",
    Storage_policy: "STORAGE_POLICY",
}

assert len(_all_wob_classes) == len(_object_to_table_lookup), (
    "The objects in _all_wob_types must be mapped properly to _object_to_table_loopup"
)


def get_all_edge_classes():
    global _all_wob_classes
    return _all_wob_classes


def is_valid_object_label(label: str):
    return label.upper() in _table_to_object_lookup.keys()


def table_to_object(table):
    global _table_to_object_lookup
    table = table.upper()
    return _table_to_object_lookup[table]


def object_to_table(object):
    global _object_to_table_lookup
    return _object_to_table_lookup[object.__class__]


def wob_class_to_table(wob_class):
    global _object_to_table_lookup
    return _object_to_table_lookup[wob_class]


def get_all_edge_labels():
    return [wob_class_to_table(o) for o in get_all_edge_classes()]


llm = ArgotModelProvider(None, use_async=True)
sync_llm = ArgotModelProvider(None, use_async=False)

# Alias for backwards compatibility
get_all_wob_classes = get_all_edge_classes
