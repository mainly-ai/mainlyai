from ..security.security_context import Security_context
from ..orm.base_orm import Base_object_ORM


class Compute_resource_group(Base_object_ORM):
    """
    This is a WOB that defines the compute resource group.
    """

    sql_compute_resource_group_ORM = {
        "id": "t.id as id",
        "cpu_capacity": "t.`cpu_capacity` as `cpu_capacity`",
        "cpu_congestion": "t.`cpu_congestion` as `cpu_congestion`",
        "gpu_capacity": "t.`gpu_capacity` as `gpu_capacity`",
        "gpu_congestion": "t.`gpu_congestion` as `gpu_congestion`",
        "ram_capacity": "t.`ram_capacity` as `ram_capacity`",
        "ram_congestion": "t.`ram_congestion` as `ram_congestion`",
        "cost_per_cpu_hour": "t.`cost_per_cpu_hour` as `cost_per_cpu_hour`",
        "cost_per_gpu_hour": "t.`cost_per_gpu_hour` as `cost_per_gpu_hour`",
        "cost_per_gb_hour": "t.`cost_per_gb_hour` as `cost_per_gb_hour`",
        "cost_per_net_rx_gb": "t.`cost_per_net_rx_gb` as `cost_per_net_rx_gb`",
        "cost_per_net_tx_gb": "t.`cost_per_net_tx_gb` as `cost_per_net_tx_gb`",
        "deployment_base_url": "t.deployment_base_url as deployment_base_url",
        "operator_user_id": "t.operator_user_id as operator_user_id",
    }
    sql_compute_resource_group_ORM.update(Base_object_ORM.metadata)

    def __init__(self, sc: Security_context, id=-1, metadata_id=None, user_id=-1):
        self.default_value = {
            "cpu_capacity": 0,
            "cpu_congestion": 0.0,
            "gpu_capacity": 0,
            "gpu_congestion": 0.0,
            "ram_capacity": 0,
            "ram_congestion": 0.0,
            "cost_per_cpu_hour": 0.000,
            "cost_per_gpu_hour": 0.000,
            "cost_per_gb_hour": 0.000,
            "cost_per_net_rx_gb": 0.000,
            "cost_per_net_tx_gb": 0.000,
            "deployment_base_url": None,
            "operator_user_id": -1,
        }
        self.id = id
        self.sctx = sc
        self.create_mapping(
            self.sql_compute_resource_group_ORM, "compute_resource_group"
        )
        if metadata_id is not None:
            self._load_from_metadata_id(sc, metadata_id, user_id=user_id)
        elif id != -1:
            self._load_from_id(sc, self.id)
