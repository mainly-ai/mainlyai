config_schema = {
    "runtime_manager": str,
    "auth_token": str,
    "crg_id": int,
    "poll_mode": bool,
    "poll_interval": int,
    "skip_hw_check": bool,
    "db": {"host": str, "port": str, "database": str},
    "rabbitmq": {"host": str, "port": str},
    "ca_source": str,
    "paths": {
        "logzod": str,
        "python_env": str,
        "processor": str,
        "contexts": str,
        "ca": str,
    },
}
