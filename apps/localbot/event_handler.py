import logging
import time
import json
from mirmod import miranda

from runtime_manager import RuntimeManager


class NotifiedEventHandler:
    def __init__(self, auth_token: str):
        self.auth_token = auth_token
        self.sctx = miranda.create_security_context(temp_token=auth_token)

    def run(self):
        while True:
            time.sleep(1)


class PolledEventHandler:
    def __init__(self, config: dict):
        self.config = config
        self.sctx = miranda.create_security_context(temp_token=config["auth_token"])
        self.poll_interval = config["poll_interval"]
        self.runtime_manager = RuntimeManager(config)

    def run(self):
        while True:
            logging.debug("Polling for jobs")
            try:
                job = miranda.get_message(self.sctx, "crg_1>job")
                if job is None:
                    continue
                logging.debug("Received job: %s", job)
                payload = json.loads(job["payload"])
                project_id = int(job["wob_id"])
                req_sc = miranda.create_security_context(temp_token=payload["token"])
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
            time.sleep(self.poll_interval)
