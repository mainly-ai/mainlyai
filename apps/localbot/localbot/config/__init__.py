import logging
import os
import platform
import stat
import urllib.request
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
    default_config = get_default_config()
    if branch_key is not None:
        schema = schema[branch_key]
        default_config = default_config[branch_key]

    for k, v in schema.items():
        if k not in config:
            config[k] = default_config[k]
            logging.warning(
                f"Missing key {k} in config, using default value {default_config[k]}"
            )
        if type(v) is dict:
            validate_config(config[k], schema, "{}.{}".format(dir_level, k), k)
        elif str(type(config[k])) != str(v):
            raise Exception(
                'Invalid type for "{}" on "{}". Expected {}, got {}'.format(
                    k, dir_level, str(v), str(type(config[k]))
                )
            )


def which(cmd):
    for path in os.environ["PATH"].split(os.pathsep):
        if os.path.exists(os.path.join(path, cmd)):
            return os.path.join(path, cmd)
    return None


def download_logzod():
    system = platform.system().lower()
    machine = platform.machine().lower()

    asset_map = {
        ("linux", "x86_64"): "logzod-linux-x86_64",
        ("linux", "amd64"): "logzod-linux-x86_64",
        ("darwin", "x86_64"): "logzod-macos-x86_64",
        ("darwin", "amd64"): "logzod-macos-x86_64",
        ("darwin", "arm64"): "logzod-macos-aarch64",
        ("darwin", "aarch64"): "logzod-macos-aarch64",
    }

    asset_name = asset_map.get((system, machine))
    if asset_name is None:
        raise Exception(
            f"Logzod - Unsupported platform: {system} {machine}. "
            "Supported platforms: Linux x86_64, macOS x86_64, macOS ARM64"
        )

    logzod_path = os.path.join(os.getcwd(), "logzod")

    url = f"https://github.com/mainly-ai/logzod/releases/latest/download/{asset_name}"
    try:
        logging.info(f"Downloading logzod from {url}...")
        urllib.request.urlretrieve(url, logzod_path)
    except Exception as e:
        raise Exception(f"Failed to download logzod from {url}: {e}")

    os.chmod(
        logzod_path,
        stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,
    )

    logging.info(f"Downloaded logzod to {logzod_path}")
    return logzod_path


def download_ca_cert(cfg):
    try:
        logging.info(f"Downloading CA cert from {cfg['ca_source']}")
        urllib.request.urlretrieve(cfg["ca_source"], cfg["paths"]["ca"])
    except Exception as e:
        raise Exception(f"Failed to download CA cert from {cfg['ca_source']}: {e}")


def get_default_config():
    python_env = os.environ.get("PYTHON_ENV_PATH", os.environ.get("VIRTUAL_ENV", ""))
    python_bin = which("python3") if python_env == "" else "/bin/python3"
    logzod_bin = which("logzod")
    ca_path = os.environ.get(
        "MAINLY_CA_PATH", os.path.join(os.getcwd(), "mainly_ca.pem")
    )

    if logzod_bin is None:
        try:
            logzod_bin = download_logzod()
        except Exception as e:
            raise Exception(f"logzod not found in PATH and failed to download: {e}")
    return {
        "auth_token": "",
        "crg_id": 0,
        "poll_mode": False,
        "poll_interval": 10,
        "skip_hw_check": False,
        "runtime_manager": "localbot.runtime_manager",
        "ca_source": "https://ca.platform.mainly.ai/public.pem",
        "db": {
            "host": "instance-production-mysql1",
            "port": "3306",
            "database": "miranda",
        },
        "rabbitmq": {
            "host": "rabbitmq-0",
            "port": "5672",
        },
        "paths": {
            "logzod": logzod_bin,
            "python_env": python_env,
            "python": python_bin,
            "ca": ca_path,
            "processor": "-m mirmod.processor",
            "contexts": "./contexts",
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
