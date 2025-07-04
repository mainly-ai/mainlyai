config_schema = {
    "auth_token": str,
    "crg_id": int,
    "poll_mode": bool,
    "poll_interval": int,
    "db": {"host": str, "port": str, "database": str},
    "paths": {
        "logzod": str,
        "python_env": str,
        "processor": str,
        "contexts": str,
    },
}
