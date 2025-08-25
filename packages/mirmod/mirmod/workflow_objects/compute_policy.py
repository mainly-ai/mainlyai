from ..security.security_context import Security_context
from ..orm.base_orm import Base_object_ORM


class Compute_policy(Base_object_ORM):
    """
    This is a WOB that defines the compute policy for a knowledge object.
    cr_group_id: The compute resource group id from which the compute scheduler will select a compute resource
    docker_image_id: The docker image id to be used for the compute resource
    """

    sql_compute_policy_ORM = {
        "id": "t.id as id",
        "order": "t.`order` as `order`",
        "cr_group_id": "t.`cr_group_id` as `cr_group_id`",
        "docker_image_id": "t.`docker_image_id` as `docker_image_id`",
        "requested_gpus": "t.`requested_gpus` as `requested_gpus`",
        "requested_cpus": "t.`requested_cpus` as `requested_cpus`",
        "requested_memory": "t.`requested_memory` as `requested_memory`",
        "bind_http": "t.`bind_http` as `bind_http`",
    }
    sql_compute_policy_ORM.update(Base_object_ORM.metadata)

    def __init__(self, sc: Security_context, id=-1, metadata_id=None, user_id=-1):
        self.default_value = {
            "order": 0,
            "cr_group_id": -1,
            "docker_image_id": -1,
            "bind_http": 1,
            "requested_gpus": 0,
            "requested_cpus": 1.0,
            "requested_memory": 2.0,
        }
        self.id = id
        self.sctx = sc
        self.create_mapping(self.sql_compute_policy_ORM, "compute_policy")
        if metadata_id is not None:
            self._load_from_metadata_id(sc, metadata_id, user_id=user_id)
        elif id != -1:
            self._load_from_id(sc, self.id)
