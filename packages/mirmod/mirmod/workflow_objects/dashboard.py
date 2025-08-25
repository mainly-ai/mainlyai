from ..orm.base_orm import Base_object_ORM
from ..security.security_context import Security_context


class Dashboard(Base_object_ORM):
    """The dashboard is a collection of UIViews and other reports that can provide a quick
    overview of the project. The main attribute is a layout field which provide information to the client
    on how to represent the UIViews."""

    sql_ORM = {
        "id": "t.id as id",
        "layout": "t.layout as layout",
        "workflow_state": "t.workflow_state as workflow_state",
        "type": "t.type as `type`",
    }
    sql_ORM.update(Base_object_ORM.metadata)

    def __init__(self, sc: Security_context, id=-1, metadata_id=None, user_id=-1):
        self.default_value = {"order": 0, "layout": "{}", "type": "DASHBOARD"}
        self.id = id
        self.sctx = sc
        self.create_mapping(self.sql_ORM, "dashboard")
        if metadata_id is not None:
            self._load_from_metadata_id(sc, metadata_id, user_id=user_id)
            # logger.info("Created dashboard with metadata_id: " + str(metadata_id))
        elif id != -1:
            self._load_from_id(sc, self.id)
            # logger.info("Created dashboard object with id: " + str(self.id))
