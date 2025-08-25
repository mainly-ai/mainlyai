from ..orm.base_orm import Base_object_ORM
from ..security.security_context import Security_context


class Project(Base_object_ORM):
    """A project may link several knowledge objects (graphs) together."""

    sql_project_ORM = {
        "id": "t.id as id",
        "organization_id": "t.organization_id as organization_id",
        "stripe_sub_id": "t.stripe_sub_id as stripe_sub_id",
        "last_paid": "t.last_paid as last_paid",
    }
    sql_project_ORM.update(Base_object_ORM.metadata)

    def __init__(self, sc: Security_context, id=-1, metadata_id=None, user_id=-1):
        self.default_value = {
            "organization_id": -1,
            "stripe_sub_id": "",
            "last_paid": "1970-01-01 00:00:00",
        }
        self.buffer = {}  # Storing execution context data. TODO will hook up with library for thread context data
        self.id = id
        self.sctx = sc
        self.create_mapping(self.sql_project_ORM, "project")
        if metadata_id is not None:
            self._load_from_metadata_id(sc, metadata_id, user_id=user_id)
        elif id != -1:
            self._load_from_id(sc, self.id)
