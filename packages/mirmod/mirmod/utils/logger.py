import logging
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_LOG = ROOT_DIR + "/mirmod.log"


class Logger:
    def __init__(self):
        self.logger = self.get_local_logger()

    @staticmethod
    def get_local_logger():
        # Create custom logger with the specified log level
        logger = logging.getLogger("mirmod")
        log_level = logging._nameToLevel[
            os.getenv("MIRMOD_LOG_LEVEL", default="NOTSET")
        ]
        logger.setLevel(log_level)

        # Define format for logs
        log_format = "%(asctime)s - [%(levelname)s]: %(message)s"

        # Create stdout handler for logging to the console
        stdout_handler = logging.StreamHandler()
        stdout_handler.setFormatter(logging.Formatter(log_format))

        # Create file handler for logging to a file
        log_filename = os.getenv("MIRANDA_LOGFILE", default=LOCAL_LOG)
        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(logging.Formatter(log_format))

        # Add both handlers to the logger
        logger.addHandler(stdout_handler)
        logger.addHandler(file_handler)

        return logger

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)


# We initialize a single instance of the logger here that is used by all modules
logger = Logger()
