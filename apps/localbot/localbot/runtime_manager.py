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
            self.target(self._stop_event, *self.args)
        # If a callback is provided, execute it after the target function
        if self.callback:
            self.callback()


def start_runtime_thread(
    stop_event: threading.Event,
    req_sc: miranda.Security_context,
    ko_id: int,
    job: dict,
    payload: dict,
    config: dict,
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
        logging.debug(
            "Context directory %s already exists, ensure processors are stopped correctly.",
            context_path,
        )

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

    logging.debug("Created Docker_job object %s %s", ob.id, ob.metadata_id)

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
        "RABBITMQ_HOST": config["rabbitmq"]["host"],
        "RABBITMQ_PORT": str(config["rabbitmq"]["port"]),
        "RABBITMQ_CAFILE": config["paths"]["ca"],
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

    process = subprocess.Popen(
        cmd,
        shell=True,
        text=True,
        env=env,
        cwd=context_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # event to signal when process completes
    process_done = threading.Event()
    process_result = {"returncode": None, "stdout": None, "error": None}

    def wait_for_process():
        """Thread function to wait for process completion"""
        try:
            stdout, stderr = process.communicate()
            process_result["returncode"] = process.returncode
            process_result["stdout"] = stdout
        except Exception as e:
            process_result["error"] = e
        finally:
            process_done.set()

    # start thread to wait for process
    process_thread = threading.Thread(target=wait_for_process, daemon=True)
    process_thread.start()

    try:
        # wait efficiently for either stop event or process completion
        # Wait for either the stop event or process completion - completely poll-free!
        # This approach uses a race condition between two blocking waits

        # Use a single event to coordinate between the two possible outcomes
        first_to_finish = threading.Event()
        winner = {"source": None}  # Use dict instead of threading.local for simplicity

        def wait_for_stop():
            stop_event.wait()  # Block until stop event is set
            if not first_to_finish.is_set():
                winner["source"] = "stop"
                first_to_finish.set()

        def wait_for_process_done():
            process_done.wait()  # Block until process is done
            if not first_to_finish.is_set():
                winner["source"] = "process"
                first_to_finish.set()

        # Start both waiting threads
        stop_waiter = threading.Thread(target=wait_for_stop, daemon=True)
        process_waiter = threading.Thread(target=wait_for_process_done, daemon=True)

        stop_waiter.start()
        process_waiter.start()

        # Wait for the first one to finish - no polling at all!
        first_to_finish.wait()

        # Check which event won the race
        if stop_event.is_set():
            logging.debug("Stop event triggered, terminating process")
            process.terminate()
            try:
                # wait a bit for graceful shutdown
                if not process_done.wait(timeout=1):
                    logging.warning("Process didn't terminate gracefully, killing it")
                    process.kill()
                process_thread.join(timeout=1)  # wait for thread cleanup
            except Exception:
                logging.warning("Error during graceful shutdown, forcing kill")
                process.kill()
                process_thread.join(timeout=1)

            # Update workflow state to indicate the process has exited
            try:
                ob.workflow_state = "EXITED"
                ob.update(req_sc)
                logging.debug(
                    "Updated workflow state to EXITED for Docker_job %s", ob.id
                )
                miranda.send_realtime_message(
                    req_sc,
                    json.dumps(
                        {
                            "action": "update[DOCKER_JOB]",
                            "data": {"workflow_state": "EXITED", "id": ob.id},
                        }
                    ),
                    ticket=payload["rtmq_ticket"],
                    ko_id=ko.id,
                )
            except Exception as e:
                logging.error("Failed to update workflow state to EXITED: %s", e)
            return

        # process completed normally
        process_thread.join()  # ensure thread cleanup

        if process_result["error"]:
            raise process_result["error"]

        if process_result["returncode"] != 0:
            logging.error(
                "Process failed with return code %d: %s",
                process_result["returncode"],
                process_result["stdout"],
            )
        else:
            logging.debug("Process completed successfully")

        # Update workflow state to indicate the process has exited (normal completion)
        try:
            ob.workflow_state = "EXITED"
            ob.update(req_sc)
            logging.debug("Updated workflow state to EXITED for Docker_job %s", ob.id)
        except Exception as e:
            logging.error("Failed to update workflow state to EXITED: %s", e)

    except Exception as e:
        logging.error("Error during process execution: %s", e)
        if process.poll() is None:
            process.terminate()
            process.wait()
        process_thread.join(timeout=1)

        # Update workflow state to indicate the process has exited (exception case)
        try:
            ob.workflow_state = "EXITED"
            ob.update(req_sc)
            logging.debug("Updated workflow state to EXITED for Docker_job %s", ob.id)
        except Exception as update_e:
            logging.exception("Failed to update workflow state to EXITED: %s", update_e)

    logging.info("Runtime for project %s has exited", ko_id)


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

    def kill_all_runtimes(self):
        runtimes = list(self.runtimes.values())
        for runtime in runtimes:
            try:
                runtime.stop()
            except Exception as e:
                logging.error("Error killing runtime: %s", e)

        logging.info("Waiting for runtimes to exit")
        for runtime in runtimes:
            if runtime is not None and runtime.is_alive():
                try:
                    runtime.join(timeout=10)
                except Exception:
                    pass

    def create_runtime(
        self, req_sc: miranda.Security_context, ko_id: int, job: dict, payload: dict
    ):
        logging.debug("Creating runtime for project %s", ko_id)
        if ko_id in self.runtimes:
            logging.warning("Runtime already exists for project %s", ko_id)
            return

        class Cleaner:
            def __init__(self, runtime_manager: RuntimeManager, ko_id: int):
                self.runtime_manager = runtime_manager
                self.ko_id = ko_id

            def __call__(self):
                logging.debug("Cleaning up runtime for project %s", self.ko_id)
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
        logging.debug("Destroying runtime for project %s", ko_id)
        if ko_id not in self.runtimes:
            logging.warning("Runtime does not exist for project %s", ko_id)
            return
        self.runtimes[ko_id].stop()
        context_path = os.path.join(self.config["paths"]["contexts"], str(ko_id))
        if os.path.exists(context_path):
            logging.debug("Removing context directory: %s", context_path)
            shutil.rmtree(context_path)
        del self.runtimes[ko_id]
