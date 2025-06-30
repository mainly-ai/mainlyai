from ..security.security_context import Security_context
from ..orm.base_orm import Base_object_ORM


class Storage_policy(Base_object_ORM):
    """ """

    sql_storage_policy_ORM = {
        "id": "t.id as id",
        "storage_type": "t.storage_type as storage_type",
        "mount_point": "t.mount_point as mount_point",
        "details": "t.details as details",
        "workflow_state": "t.workflow_state as workflow_state",
    }
    sql_storage_policy_ORM.update(Base_object_ORM.metadata)

    def __init__(self, sc: Security_context, id=-1, metadata_id=None, user_id=-1):
        self.default_value = {
            "storage_type": "VAULT",
            "mount_point": "/tmp/vault",
            "details": None,
            "workflow_state": "UNPROVISIONED",
        }
        self.id = id
        self.sctx = sc
        self.create_mapping(self.sql_storage_policy_ORM, "storage_policy")
        if metadata_id is not None:
            self._load_from_metadata_id(sc, metadata_id, user_id=user_id)
        elif id != -1:
            self._load_from_id(sc, self.id)
