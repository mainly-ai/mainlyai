import logging
import os

from mirmod import miranda

from .event_handler import (
    NotifiedEventHandler,
    PolledEventHandler,
    RabbitMQEventHandler,
)
from . import resource_reporting, cli_args, config


def main():
    args = cli_args.parser.parse_args()
    current_event_handler = None

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - [%(levelname)s]: %(message)s",
        )
        logging.debug("Verbose logging enabled")
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - [%(levelname)s]: %(message)s",
        )

    try:
        cfg = config.read_config("localbot.yml")
    except Exception as e:
        if not args.token:
            logging.error("No auth token provided: {}".format(e))
            return

        cfg = config.write_config(
            {"auth_token": args.token, "crg_id": args.crg_id}, "localbot.yml"
        )

    # ensure ca is downloaded
    if os.path.exists(cfg["paths"]["ca"]):
        logging.debug("Found local CA certificate")
    else:
        config.download_ca_cert(cfg)

    logging.debug(f"Using config: {cfg}")

    logging.debug("Testing sctx")
    sctx = miranda.create_security_context(temp_token=cfg["auth_token"])
    try:
        with sctx.connect() as _:
            id = sctx.renew_id()
            if id is None or int(id) <= 0:
                raise Exception("Invalid id")

    except Exception as e:
        logging.debug("Error renewing id", e)
        logging.error(
            "Failed to create security context. Your auth token may be invalid."
        )
        return

    context_path = os.path.expanduser(cfg["paths"]["contexts"])
    if not os.path.exists(context_path):
        logging.info(f"Context path {context_path} does not exist, creating it")
        os.makedirs(context_path, exist_ok=True)
    else:
        logging.debug(f"Context path: {context_path}")

    crg = miranda.find_object_by_id(sctx, cfg["crg_id"], "COMPUTE_RESOURCE_GROUP")
    if crg is None or crg.id == -1:
        logging.error(
            f"CRG with ID {cfg['crg_id']} does not exist or is not accessible using the provided auth token."
        )
        return
    logging.debug("Loaded CRG: %s", crg.__repr__("jdict"))
    if not cfg["skip_hw_check"] and not args.skip_hw_check:
        logging.info("Performing hardware checks")
        resource_reporting.update_crg_maximum_resources(sctx, crg)
    else:
        logging.info("Skipping hardware checks")

    # if cfg["poll_mode"]:
    #    logging.info("Starting in poll mode")
    #    current_event_handler = PolledEventHandler(cfg)
    #    current_event_handler.run()
    #
    # else:
    #    logging.info("Starting in event mode")
    #    current_event_handler = NotifiedEventHandler(cfg)
    #    current_event_handler.run()
    current_event_handler = RabbitMQEventHandler(cfg)
    current_event_handler.run()


if __name__ == "__main__":
    main()
