from ..security.security_context import Security_context
from ..orm.base_orm import Base_object_ORM


class Docker_job(Base_object_ORM):
    """A docker job is created and linked to a wob which is currently executing code in a docker container.
    workflow states:
        UNINITIALIZED - The job doesn't exist.
        RUNNING       - The job is currently running in a docker container on a compute host.
        EXITED        - The job is finished and the result is available in the docker container.
        ERROR         - Something went wrong and job might not exist anymore.
    """

    docker_job_orm = {
        "id": "t.id as id",
        "host": "t.host as host",
        "container_id": "t.container_id as container_id",
        "ssh_user": "t.ssh_user as ssh_user",
        "docker_sudo": "t.docker_sudo as docker_sudo",
        "docker_network": "t.docker_network as docker_network",
        "docker_env_vars": "t.docker_env_vars as docker_env_vars",
        "port": "t.port as port",
        "user_id": "t.user_id as user_id",
        "crg_id": "t.crg_id as crg_id",
        "workflow_state": "t.workflow_state as workflow_state",
        "notes": "t.notes as notes",
        "logs": "t.logs as logs",
        "message_id": "t.message_id as message_id",
        "tag": "t.tag as tag",
        "gpu_capacity": "t.gpu_capacity as gpu_capacity",
        "cpu_seconds": "t.cpu_seconds as cpu_seconds",
        "current_cpu": "t.current_cpu as current_cpu",
        "cpu_capacity": "t.cpu_capacity as cpu_capacity",
        "ram_gb_seconds": "t.ram_gb_seconds as ram_gb_seconds",
        "current_ram_gb": "t.current_ram_gb as current_ram_gb",
        "ram_gb_capacity": "t.ram_gb_capacity as ram_gb_capacity",
        "net_rx_gb": "t.net_rx_gb as net_rx_gb",
        "current_net_rx_gb": "t.current_net_rx_gb as current_net_rx_gb",
        "net_tx_gb": "t.net_tx_gb as net_tx_gb",
        "current_net_tx_gb": "t.current_net_tx_gb as current_net_tx_gb",
        "total_cost": "t.total_cost as total_cost",
        "is_deployed": "t.is_deployed as is_deployed",
    }
    docker_job_orm.update(Base_object_ORM.metadata)

    def __init__(self, sc: Security_context, id=-1, metadata_id=None, user_id=-1):
        self.default_value = {
            "order": 0,
            "host": "",
            "container_id": "",
            "ssh_user": "",
            "docker_sudo": False,
            "docker_network": "",
            "docker_env_vars": "",
            "workflow_state": "UNINITIALIZED",
            "message_id": -1,
            "port": 22,
            "tag": -1,
            "user_id": -1,
            "crg_id": 1,
            "gpu_capacity": 0.0,
            "cpu_seconds": 0.0,
            "current_cpu": 0.0,
            "cpu_capacity": 0.0,
            "ram_gb_seconds": 0.0,
            "current_ram_gb": 0.0,
            "ram_gb_capacity": 0.0,
            "net_rx_gb": 0.0,
            "current_net_rx_gb": 0.0,
            "net_tx_gb": 0.0,
            "current_net_tx_gb": 0.0,
            "total_cost": 0.0,
            "is_deployed": 0,
        }
        self.id = id
        self.sctx = sc
        self.create_mapping(self.docker_job_orm, "docker_job")
        if metadata_id is not None:
            self._load_from_metadata_id(sc, metadata_id, user_id=user_id)
            # logger.info("Loaded docker_job with metadata_id: " + str(metadata_id))
        elif id != -1:
            self._load_from_id(sc, self.id)
            # logger.info("Loaded docker_job with id: " + str(self.id))
