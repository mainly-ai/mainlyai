import ssl
import pika
from enum import Enum
import logging
import time
import json
import threading
from datetime import datetime, timezone
from mirmod import miranda
import signal

logging.getLogger("pika").setLevel(logging.WARNING)

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


class RabbitMQEventHandler:
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
        self.sctx: miranda.Security_context = miranda.create_security_context(
            temp_token=self.auth_token
        )
        self.send_response = Send_real_time_message()
        self.exit_event = threading.Event()
        self.config = config
        self.crg = config["crg_id"]
        self.crg_ob = miranda.Compute_resource_group(self.sctx, id=config["crg_id"])
        self.rabbitmq_host = config["rabbitmq"]["host"]
        self.rabbitmq_port = config["rabbitmq"]["port"]
        self.rabbitmq_cafile = config["paths"].get("ca", None)
        self.rabbitmq_password = config["rabbitmq"].get("password", self.auth_token)
        self.rabbitmq_username = config["rabbitmq"].get(
            "username", self.sctx.current_miranda_user()
        )
        logging.info("Using RabbitMQ user:" + str(self.rabbitmq_username))
        self.rabbitmq_vhost = config["rabbitmq"].get("vhost", "/")
        self.connection = None
        self.channel = None
        self._last_active_thread = None
        self._last_active_stop_event = threading.Event()

    def _update_last_active_periodically(self):
        while not self._last_active_stop_event.is_set():
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

            self._last_active_stop_event.wait(30)

    def _get_connection(self):
        username = self.rabbitmq_username
        assert username is not None, "rabbitmq_username must be set"
        password = self.rabbitmq_password if self.rabbitmq_password is not None else ""
        credentials = pika.PlainCredentials(username, password)

        parameters_kwargs = {
            "host": self.rabbitmq_host,
            "port": self.rabbitmq_port,
            "credentials": credentials,
            "virtual_host": self.rabbitmq_vhost,
            "heartbeat": 600,
            "blocked_connection_timeout": 300,
        }

        if self.rabbitmq_cafile:
            try:
                context = ssl.create_default_context(cafile=self.rabbitmq_cafile)
                context.load_verify_locations(cafile=self.rabbitmq_cafile)
                ssl_options = pika.SSLOptions(context, self.rabbitmq_host)
                ssl_parameters = pika.ConnectionParameters(
                    ssl_options=ssl_options, **parameters_kwargs
                )
                return pika.BlockingConnection(ssl_parameters)
            except ssl.SSLError as e:
                logging.warning(
                    f"SSL connection to RabbitMQ failed: {e}. Attempting non-SSL connection."
                )
            except Exception as e:
                logging.error(f"Failed to connect to RabbitMQ with SSL: {e}")
                raise

        if not self.rabbitmq_cafile:
            logging.warning(
                "rabbitmq_cafile not provided, proceeding with non-SSL connection."
            )

        try:
            parameters = pika.ConnectionParameters(**parameters_kwargs)
            return pika.BlockingConnection(parameters)
        except Exception as e:
            logging.error(f"Non-SSL connection to RabbitMQ failed: {e}")
            raise

    def _process_message(self, ch, method, properties, body):
        logging.debug("Received job from RabbitMQ: %s", body)
        try:
            payload = json.loads(body)
            req_sc = miranda.create_security_context(temp_token=payload["token"])

            if payload["action"] == "destroy":
                docker_job_id = int(payload["docker_job_id"])
                logging.info("Force destroying docker job id= %s", docker_job_id)
                docker_job = miranda.Docker_job(req_sc, id=docker_job_id)
                if docker_job.id == -1:
                    logging.warning(
                        "Failed to find docker job with id %s", docker_job_id
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return
                docker_job.workflow_state = "EXITED"
                docker_job.update(req_sc)

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
                            docker_job_id,
                        )
                except Exception as e:
                    logging.exception("Error finding parent ko: %s", e)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            workflow_id = int(
                payload["project_id"]
            )  # NOTE: Inbound project_id is not a project but workflow
            ko = miranda.Knowledge_object(req_sc, id=workflow_id)
            logging.debug("Found project: %s", ko.__repr__("jdict"))
            if ko.id == -1:
                logging.warning("Failed to find project with id %s", workflow_id)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            if payload["action"] == "create":
                if self.runtime_manager.get_runtime(ko.id) is not None:
                    logging.warning("Runtime already exists for project %s", ko.id)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return
                wob_message = {
                    "id": -1,
                    "wob_id": ko.id,
                    "wob_type": "KNOWLEDGE_OBJECT",
                    "payload": payload,
                }
                self.runtime_manager.create_runtime(req_sc, ko.id, wob_message, payload)
            elif payload["action"] == "destroy":
                if self.runtime_manager.get_runtime(ko.id) is None:
                    logging.warning("Runtime does not exist for project %s", ko.id)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return
                self.runtime_manager.destroy_runtime(ko.id)
            else:
                logging.warning("Unknown action: %s", payload["action"])

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            logging.exception("Error processing job: %s", e)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def wait_for_event(self):
        self._last_active_thread = threading.Thread(
            target=self._update_last_active_periodically
        )
        self._last_active_thread.daemon = True
        self._last_active_thread.start()

        while not self.exit_event.is_set():
            try:
                self.connection = self._get_connection()
                self.channel = self.connection.channel()

                queue_name = (
                    f"{self.crg_ob.table_name.upper()}:{self.crg_ob.metadata_id}"
                )
                logging.info("Consuming from RabbitMQ queue: %s", queue_name)

                self.channel.queue_declare(queue=queue_name, durable=True)
                self.channel.basic_qos(prefetch_count=1)
                self.channel.basic_consume(
                    queue=queue_name, on_message_callback=self._process_message
                )

                self.channel.start_consuming()
            except (
                pika.exceptions.AMQPConnectionError,
                pika.exceptions.StreamLostError,
            ) as e:
                logging.warning(
                    f"Connection to RabbitMQ lost: {e}. Reconnecting in 5s..."
                )
                if self.connection and self.connection.is_open:
                    self.connection.close()
                time.sleep(5)
            except KeyboardInterrupt:
                logging.info("Interrupted by user.")
                break
            except Exception as e:
                logging.exception(f"An unexpected error occurred in event loop: {e}")
                break

        logging.info("Stopping event loop.")
        self._last_active_stop_event.set()
        if self._last_active_thread:
            self._last_active_thread.join()

    def signal_handler(self, sig, frame):
        logging.info("Graceful shutdown initiated.")
        self.exit_event.set()
        if self.channel and self.channel.is_open:
            self.channel.stop_consuming()

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        self.wait_for_event()


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
