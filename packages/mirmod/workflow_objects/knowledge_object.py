from ..orm.base_orm import Base_object_ORM
from ..security.security_context import Security_context


class Knowledge_object(Base_object_ORM):
    """The knowledge object is the over arching document for project which combines
    data sources and models. It also act as a lightweight ORM for the joint table knowledge_object and metadata"""

    sql_knowledge_object_ORM = {"id": "t.id as id", "sdg": "t.sdg as sdg"}
    sql_knowledge_object_ORM.update(Base_object_ORM.metadata)

    def __init__(
        self, sc: Security_context, id: int = -1, metadata_id: int = None, user_id=-1
    ):
        self.default_value = {"id": -1, "metadata_id": -1, "sdg": ""}
        self.buffer = {}  # Storing execution context data. TODO will hook up with library for thread context data
        self.id = id
        self.sctx = sc
        self.create_mapping(self.sql_knowledge_object_ORM, "knowledge_object")
        if metadata_id is not None:
            self._load_from_metadata_id(sc, metadata_id, user_id=user_id)
            # logger.info("Created knowledge object with metadata_id: " + str(metadata_id))
        elif id != -1:
            self._load_from_id(sc, self.id)
            # logger.info("Created knowledge object with id: " + str(self.id))
