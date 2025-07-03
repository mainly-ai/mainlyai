import os
from yaml import load, dump

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from .schema import config_schema


def read_config(config_file):
    f = open(config_file, "r")
    c = f.read()
    config = load(c, Loader=Loader)
    validate_config(config, config_schema, "config", None)
    return config


def validate_config(config, schema, dir_level, branch_key):
    if branch_key is not None:
        schema = schema[branch_key]

    for k, v in schema.items():
        if k not in config:
            raise Exception('Missing key on "{}": {}'.format(dir_level, k))
        if type(v) is dict:
            validate_config(config[k], schema, "{}.{}".format(dir_level, k), k)
        elif str(type(config[k])) != str(v):
            raise Exception(
                'Invalid type for "{}" on "{}". Expected {}, got {}'.format(
                    k, dir_level, str(v), str(type(config[k]))
                )
            )


def get_default_config():
    return {
        "auth_token": "",
        "poll_mode": False,
        "poll_interval": 10,
        "db": {
            "host": "localhost",
            "port": 3306,
            "database": "miranda",
        },
        "paths": {
            "logzod": "~/.cargo/bin/logzod",
            "python_env": os.environ.get("PYTHON_ENV_PATH", ""),
            "processor": "-m mirmod.processor",
        },
    }


def merge_config(config, default_config):
    for k, v in default_config.items():
        if k not in config:
            config[k] = v
    return config


def write_config(config, config_file):
    merged = merge_config(config, get_default_config())
    with open(config_file, "w") as f:
        dump(merged, f, Dumper=Dumper)
    return merged
