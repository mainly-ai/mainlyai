from ..security.security_context import Security_context
from ..orm.base_orm import Base_object_ORM


class Docker_image(Base_object_ORM):
    """A docker image is connected to a knowledge_object and contains the docker image id.
    image_state: 'NEW','BUILDING','PUSHING','MODIFIED','ERROR','READY'
    """

    docker_image_orm = {
        "id": "t.id as id",
        "uri": "t.uri as uri",
        "properties": "t.properties as properties",
        "image_state": "t.image_state as image_state",
        "image_size": "t.image_size as image_size",
        "base_image_uri": "t.base_image_uri as base_image_uri",
        "is_base_image": "t.is_base_image as is_base_image",
        "base_image_id": "t.base_image_id as base_image_id",
        "hosting_crg_id": "t.hosting_crg_id as hosting_crg_id",
    }
    docker_image_orm.update(Base_object_ORM.metadata)

    def __init__(self, sc: Security_context, id=-1, metadata_id=None, user_id=-1):
        self.default_value = {
            "uri": "",
            "properties": '{"requirements": "", "before_install": "", "after_install": ""}',
            "image_state": "NEW",
            "image_size": 0,
            "base_image_uri": "",
            "is_base_image": False,
            "base_image_id": -1,
            "hosting_crg_id": -1,
        }
        self.id = id
        self.sctx = sc
        self.create_mapping(self.docker_image_orm, "docker_image")
        if metadata_id is not None:
            self._load_from_metadata_id(sc, metadata_id, user_id=user_id)
            # logger.info("Loaded docker_image_orm with metadata_id: " + str(metadata_id))
        elif id != -1:
            self._load_from_id(sc, self.id)
            # logger.info("Loaded docker_image_orm with id: " + str(self.id)
