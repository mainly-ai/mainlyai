from enum import Enum
import logging
import time
import json
import threading
from datetime import datetime, timezone
from mirmod import miranda
import signal

import importlib


class ProcessorStates(str, Enum):
    Uninitialized = "UNINITIALIZED"
    Starting = "STARTING"
    Ready = "READY"
    Running = "RUNNING"
    Error = "ERROR"
    Exited = "EXITED"
    ResumeReady = "RESUMEREADY"
    Killing = "KILLING"
    Queued = "QUEUED"
    Restarting = "RESTARTING"


ACTIVE_STATES = [
    ProcessorStates.Uninitialized,
    ProcessorStates.Starting,
    ProcessorStates.Ready,
    ProcessorStates.Running,
    ProcessorStates.ResumeReady,
    ProcessorStates.Killing,
    ProcessorStates.Queued,
    ProcessorStates.Restarting,
]


class Sleep_time:
    def __init__(self, min=0, max=10, steps=10, exponential=False):
        self.min = min
        self.max = max
        self.steps = steps
        self.count = 0
        self.exponential = exponential

    def reset(self):
        self.count = 0

    def __call__(self):
        """Increment current sleep time so that we reach max in self.steps steps"""
        if self.count >= self.steps:
            return self.max
        if self.exponential:
            """ set count to increase exponentially the """
            p = self.count / (self.steps - 1)
            if p > 1.0:
                p = 1.0

            def f(x):
                return x**4

            rs = self.min + (self.max - self.min) * f(p)
        else:
            rs = self.min + (self.max - self.min) * self.count / self.steps
        self.count += 1
        # time.sleep(rs)
        return rs


class Send_real_time_message:
    def __init__(self):
        pass

    def __call__(self, message: dict):
        pass


class NotifiedEventHandler:
    def __init__(self, config: dict):
        try:
            if "runtime_manager" not in config:
                raise Exception("Runtime manager not specified in config")

            logging.info("Using runtime manager: %s", config["runtime_manager"])
            RuntimeManager = importlib.import_module(
                config["runtime_manager"]
            ).RuntimeManager
            self.runtime_manager = RuntimeManager(config)
        except Exception as e:
            logging.error("Error importing custom runtime manager: %s", e)
            raise e

        self.auth_token = config["auth_token"]
        self.sctx = miranda.create_security_context(temp_token=self.auth_token)
        self.sleep_time = Sleep_time(min=2, max=60 * 2, steps=10, exponential=True)
        self.send_response = Send_real_time_message()
        self.exit_event = threading.Event()
        self.config = config
        self.crg = config["crg_id"]
        self.crg_ob = miranda.Compute_resource_group(self.sctx, id=config["crg_id"])

    def wait_for_event(self):
        wake_up_counter = 0
        while not self.exit_event.is_set():
            con = self.sctx.connect()
            with con.cursor(dictionary=True) as cur:
                didnt_get_any_notification = False
                s = 0
                try:
                    # Wait for a maximum of two minutes.
                    # Note: we're using wob_id here intentionally because policy is that there can only be one
                    # running project per wob_id.
                    s = round(self.sleep_time(), ndigits=1)
                    cur.execute(
                        "SELECT /* WAITING_FOR_EVENT (crg_{}) */ SLEEP({})".format(
                            self.crg, s
                        )
                    )
                    _ = cur.fetchall()
                    didnt_get_any_notification = True
                except Exception as e:
                    # NOTE: Error is 2013: Lost connection to MySQL server during query which is expected.
                    print(e)
                    pass

                if didnt_get_any_notification:
                    logging.info(
                        "Didn't get any notifications after {} seconds. Retrying... ({}))".format(
                            s, wake_up_counter
                        )
                    )
                    time.sleep(1)
                    wake_up_counter += 1
                    if wake_up_counter > 200:
                        logging.warning(
                            "Shutting down the processor due to inactivity. "
                        )
                        exit(0)
            logging.debug("Polling for jobs")
            try:
                self.crg_ob.last_active = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                logging.debug(
                    "Updating last active time (UTC): %s", self.crg_ob.last_active
                )
                self.crg_ob.update(self.sctx)
            except Exception as e:
                logging.error("Error updating last active time: %s", e)
            try:
                job = miranda.get_message(self.sctx, f"crg_{self.crg}>job")
                if job is None:
                    continue
                self.sleep_time.reset()
                logging.debug("Received job: %s", job)
                payload = json.loads(job["payload"])
                project_id = int(job["wob_id"])
                wob_type = job["wob_type"].upper()
                req_sc = miranda.create_security_context(temp_token=payload["token"])

                if payload["action"] == "destroy" and wob_type == "DOCKER_JOB":
                    logging.info(
                        "Force destroying docker job for project %s", project_id
                    )
                    docker_job = miranda.Docker_job(req_sc, id=project_id)
                    if docker_job.id == -1:
                        logging.warning(
                            "Failed to find docker job with id %s", project_id
                        )
                        continue
                    docker_job.workflow_state = "EXITED"
                    docker_job.update(req_sc)

                    # get parent ko from docker job
                    try:
                        ko = next(
                            miranda.find_wob_by_inbound_edges(
                                req_sc,
                                docker_job.metadata_id,
                                filter=lambda x: x is not None,
                            )
                        )
                        logging.debug("Found parent ko: %s", ko.__repr__("jdict"))
                        if ko is not None and ko.id != -1:
                            self.runtime_manager.destroy_runtime(ko.id)
                        else:
                            logging.warning(
                                "Failed to find parent ko for docker job with id %s",
                                project_id,
                            )
                            continue
                    except Exception as e:
                        logging.exception("Error finding parent ko: %s", e)
                        continue
                    continue

                ko = miranda.Knowledge_object(req_sc, id=project_id)
                logging.debug("Found project: %s", ko.__repr__("jdict"))
                if ko.id == -1:
                    logging.warning("Failed to find project with id %s", project_id)
                    continue
                if payload["action"] == "create":
                    if self.runtime_manager.get_runtime(ko.id) is not None:
                        logging.warning("Runtime already exists for project %s", ko.id)
                        continue
                    self.runtime_manager.create_runtime(req_sc, ko.id, job, payload)
                elif payload["action"] == "destroy":
                    if self.runtime_manager.get_runtime(ko.id) is None:
                        logging.warning("Runtime does not exist for project %s", ko.id)
                        continue
                    self.runtime_manager.destroy_runtime(ko.id)
                else:
                    logging.warning("Unknown action: %s", payload["action"])
            except Exception as e:
                logging.exception("Error processing job: %s", e)
                pass
            time.sleep(1)

    def run(self):
        self.wait_for_event()


class PolledEventHandler:
    def __init__(self, config: dict):
        try:
            if "runtime_manager" not in config:
                raise Exception("Runtime manager not specified in config")

            logging.info("Using runtime manager: %s", config["runtime_manager"])
            RuntimeManager = importlib.import_module(
                config["runtime_manager"]
            ).RuntimeManager
            self.runtime_manager = RuntimeManager(config)
        except Exception as e:
            logging.error("Error importing custom runtime manager: %s", e)
            raise e

        self.config = config
        self.sctx = miranda.create_security_context(temp_token=config["auth_token"])
        self.poll_interval = config["poll_interval"]
        self.exit_event = threading.Event()
        self.crg_ob = miranda.Compute_resource_group(self.sctx, id=config["crg_id"])

    def signal_handler(self, sig, frame):
        logging.info("Exiting...")
        try:
            self.runtime_manager.kill_all_runtimes()
            self.exit_event.set()
        except Exception as e:
            logging.exception("Error killing runtimes: %s", e)

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)

        while not self.exit_event.is_set():
            logging.debug("Polling for jobs")
            try:
                self.crg_ob.last_active = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                logging.debug(
                    "Updating last active time (UTC): %s", self.crg_ob.last_active
                )
                self.crg_ob.update(self.sctx)
            except Exception as e:
                logging.error("Error updating last active time: %s", e)
            try:
                job = miranda.get_message(self.sctx, f"crg_{self.config['crg_id']}>job")
                if job is None:
                    self.exit_event.wait(self.poll_interval)
                    continue
                logging.debug("Received job: %s", job)
                payload = json.loads(job["payload"])
                project_id = int(job["wob_id"])
                wob_type = job["wob_type"].upper()
                req_sc = miranda.create_security_context(temp_token=payload["token"])

                if payload["action"] == "destroy" and wob_type == "DOCKER_JOB":
                    logging.info(
                        "Force destroying docker job for project %s", project_id
                    )
                    docker_job = miranda.Docker_job(req_sc, id=project_id)
                    if docker_job.id == -1:
                        logging.warning(
                            "Failed to find docker job with id %s", project_id
                        )
                        continue
                    docker_job.workflow_state = "EXITED"
                    docker_job.update(req_sc)

                    # get parent ko from docker job
                    try:
                        ko = next(
                            miranda.find_wob_by_inbound_edges(
                                req_sc,
                                docker_job.metadata_id,
                                filter=lambda x: x is not None,
                            )
                        )
                        logging.debug("Found parent ko: %s", ko.__repr__("jdict"))
                        if ko is not None and ko.id != -1:
                            self.runtime_manager.destroy_runtime(ko.id)
                        else:
                            logging.warning(
                                "Failed to find parent ko for docker job with id %s",
                                project_id,
                            )
                            continue
                    except Exception as e:
                        logging.exception("Error finding parent ko: %s", e)
                        continue
                    continue

                ko = miranda.Knowledge_object(req_sc, id=project_id)
                logging.debug("Found project: %s", ko.__repr__("jdict"))
                if ko.id == -1:
                    logging.warning("Failed to find project with id %s", project_id)
                    continue
                if payload["action"] == "create":
                    if self.runtime_manager.get_runtime(ko.id) is not None:
                        logging.warning("Runtime already exists for project %s", ko.id)
                        continue
                    self.runtime_manager.create_runtime(req_sc, ko.id, job, payload)
                elif payload["action"] == "destroy":
                    if self.runtime_manager.get_runtime(ko.id) is None:
                        logging.warning("Runtime does not exist for project %s", ko.id)
                        continue
                    self.runtime_manager.destroy_runtime(ko.id)
                else:
                    logging.warning("Unknown action: %s", payload["action"])
            except Exception as e:
                logging.exception("Error processing job: %s", e)
                pass
            self.exit_event.wait(self.poll_interval)
