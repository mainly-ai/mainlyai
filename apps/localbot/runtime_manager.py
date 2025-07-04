import datetime
import json
import logging
import os
import shlex
import shutil
import subprocess
import threading
import ulid2
from mirmod import miranda


class JSONDateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        elif isinstance(obj, datetime.timedelta):
            return (datetime.datetime.min + obj).time().isoformat()

        return super(JSONDateTimeEncoder, self).default(obj)


json_encoder = JSONDateTimeEncoder()


class CallbackThread(threading.Thread):
    def __init__(self, target, args=(), callback=None):
        super().__init__(target=target, args=args, daemon=True)
        self.target = target
        self.args = args
        self.callback = callback  # The callback function to run on completion
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        # Execute the target function
        if self.target:
            self.target(*self.args)
        # If a callback is provided, execute it after the target function
        if self.callback:
            self.callback()


def start_runtime_thread(
    req_sc: miranda.Security_context, ko_id: int, job: dict, payload: dict, config: dict
):
    logging.info("Starting runtime for project %s", ko_id)
    assert isinstance(ko_id, int)
    assert isinstance(job, dict)
    assert isinstance(payload, dict)
    assert "token" in payload
    assert "rtmq_ticket" in payload, "rtmq_ticket is required for user-space runtimes"

    context_path = os.path.join(config["paths"]["contexts"], str(ko_id))
    if not os.path.exists(context_path):
        logging.debug("Creating context directory: %s", context_path)
        os.makedirs(context_path, exist_ok=True)
    else:
        logging.error(
            "Context directory %s already exists, refusing to overwrite it. Ensure that all runtimes are properly stopped.",
            context_path,
        )
        return

    ko = miranda.Knowledge_object(req_sc, id=ko_id)

    assert ko.id != -1
    assert req_sc.user_id() != -1

    # room_name = f"project_{ko.id}"
    ulid = ulid2.generate_ulid_as_base32().lower()

    ob: miranda.Docker_job = miranda.create_wob(
        ko,
        name=payload["name"],
        description=payload["description"],
        wob_type="DOCKER_JOB",
    )
    ob.user_id = req_sc.user_id()
    ob.contianer_id = ulid
    ob.tag = payload["tag"]
    ob.message_id = job["id"]
    ob.crg_id = config["crg_id"]
    ob.workflow_state = "UNINITIALIZED"
    # some of these fields are legacy and not really used anymore
    # but we need to set them to something anyways
    ob.docker_env_vars = ""
    ob.docker_sudo = 0
    ob.docker_network = ""
    ob.gpu_capacity = (
        int(payload["requested_gpus"]) if "requested_gpus" in payload else 0
    )
    ob.cpu_seconds = 0.0
    ob.cpu_capacity = (
        float(payload["requested_cpus"]) if "requested_cpus" in payload else 0.0
    )
    ob.ram_gb_seconds = 0.0
    ob.ram_gb_capacity = (
        float(payload["requested_memory"]) if "requested_memory" in payload else 0.0
    )
    if "run_as_deployed" in payload and bool(payload["run_as_deployed"]):
        ob.is_deployed = 1
    ob.update(req_sc)

    miranda.send_realtime_message(
        req_sc,
        json.dumps(
            {
                "action": "new[DOCKER_JOB]",
                "data": ob.__repr__("jdict"),
            }
        ),
        ticket=payload["rtmq_ticket"],
        ko_id=ko.id,
    )

    logging.info("Created Docker_job object %s %s", ob.id, ob.metadata_id)

    miranda_config = {
        "host": config["db"]["host"],
        "port": config["db"]["port"],
        "database": config["db"]["database"],
        "user": "",
        "password": "",
    }

    if "miranda_config" in payload:
        miranda_config = payload["miranda_config"]

    job["debug_mode"] = True
    env = {
        "PYTHONUNBUFFERED": "1",
        "MIRANDA_LOG_STDIO": "1",
        "MIRANDA_LOGFILE": "mirmod.log",
        "MIRANDA_CONFIG_JSON": json_encoder.encode(miranda_config),
        "WOB_TOKEN": payload["token"],
        "WOB_MESSAGE": json_encoder.encode(job),
        "DOCKER_JOB_ID": str(ob.id),
        "I_AM_IN_AN_ISOLATED_AND_SAFE_CONTEXT": "1",
        "RUST_BACKTRACE": "1",
        "REALTIME_MESSAGE_TICKET": payload["rtmq_ticket"],
        "PYTHON_ENV_PATH": config["paths"]["python_env"],
    }
    env_str = ""
    for k, v in env.items():
        env_str += f"{k}={shlex.quote(v)} "
    logging.debug("Environment variables: %s", env_str)

    cmd = "{} {}/bin/python {}".format(
        config["paths"]["logzod"],
        config["paths"]["python_env"],
        config["paths"]["processor"],
    )
    logging.debug("Executing " + cmd)
    result = subprocess.run(
        cmd,
        shell=True,
        check=True,
        text=True,
        env=env,
        cwd=context_path,
    )
    logging.info("Result: %s", result)


class RuntimeManager:
    def __init__(self, config: dict):
        self.config = config
        self.runtimes = {}

    def get_runtime(self, job_id: str):
        if job_id not in self.runtimes:
            return None
        return self.runtimes[job_id]

    def get_all_runtimes(self):
        return list(self.runtimes.values())

    def create_runtime(
        self, req_sc: miranda.Security_context, ko_id: int, job: dict, payload: dict
    ):
        logging.info("Creating runtime for project %s", ko_id)
        if ko_id in self.runtimes:
            logging.warning("Runtime already exists for project %s", ko_id)
            return

        class Cleaner:
            def __init__(self, runtime_manager: RuntimeManager, ko_id: int):
                self.runtime_manager = runtime_manager
                self.ko_id = ko_id

            def __call__(self):
                logging.info("Cleaning up runtime for project %s", self.ko_id)
                self.runtime_manager.destroy_runtime(self.ko_id)

        cleaner = Cleaner(self, ko_id)
        thd = CallbackThread(
            target=start_runtime_thread,
            args=(req_sc, ko_id, job, payload, self.config),
            callback=cleaner,
        )
        thd.daemon = True
        thd.start()
        self.runtimes[ko_id] = thd

    def destroy_runtime(self, ko_id: int):
        logging.info("Destroying runtime for project %s", ko_id)
        if ko_id not in self.runtimes:
            logging.warning("Runtime does not exist for project %s", ko_id)
            return
        self.runtimes[ko_id].stop()
        context_path = os.path.join(self.config["paths"]["contexts"], str(ko_id))
        if os.path.exists(context_path):
            logging.info("Removing context directory: %s", context_path)
            shutil.rmtree(context_path)
        del self.runtimes[ko_id]
