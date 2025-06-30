from ..orm.base_orm import Base_object_ORM
from ..security.security_context import Security_context


class Deployment(Base_object_ORM):
    """The deployment object, like the Docker_job object is built for the purpose of storing the
    information about the deployment of a workflow object."""

    sql_ORM = {
        "id": "t.id as id",
        "public": "t.public as public",
        "workflow_state": "t.workflow_state as workflow_state",
        "deployed_at": "t.deployed_at as deployed_at",
        "deployed_by": "t.deployed_by as deployed_by",
        "pod_id": "t.pod_id as pod_id",
    }
    sql_ORM.update(Base_object_ORM.metadata)

    def __init__(self, sc: Security_context, id=-1, metadata_id=None, user_id=-1):
        self.default_value = {
            "public": False,
            "workflow_state": "UNDEPLOYED",
            "deployed_at": None,
            "deployed_by": None,
            "pod_id": None,
        }
        self.id = id
        self.sctx = sc
        self.create_mapping(self.sql_ORM, "deployment")
        if metadata_id is not None:
            self._load_from_metadata_id(sc, metadata_id, user_id=user_id)
            # logger.info("Created dashboard with metadata_id: " + str(metadata_id))
        elif id != -1:
            self._load_from_id(sc, self.id)
            # logger.info("Created dashboard object with id: " + str(self.id))
