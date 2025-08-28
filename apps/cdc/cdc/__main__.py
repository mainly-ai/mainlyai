#!/usr/bin/env python

import argparse
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import WriteRowsEvent
import threading
import time
import mysql.connector
from mirmod.security.security_context import get_config
import queue
import re
import logging

# Configure logging for the CDC process
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ReplicationStream:
    """
    Reads binlog events from MySQL for specific schemas and tables.
    """

    def __init__(self, db_config=None, server_id=101, table="wob_message_queue"):
        self.db_config = db_config
        self.server_id = server_id
        self.table = table

    def get_next_event(self):
        """
        Connects to MySQL and yields events from the binlog.
        Only yields WriteRowsEvent events from the 'wob_message_queue' table.
        """
        # Ensure port is an integer
        if "port" in self.db_config:
            self.db_config["port"] = int(self.db_config["port"])

        # Setup binlog stream reader using the passed server_id
        stream = BinLogStreamReader(
            connection_settings=self.db_config,
            server_id=self.server_id,
            only_events=[WriteRowsEvent],
            only_schemas=["miranda"],
            blocking=True,
            freeze_schema=True,
            resume_stream=True,
        )

        # Process binlog events
        for binlogevent in stream:
            for row in binlogevent.rows:
                if isinstance(binlogevent, WriteRowsEvent):
                    if binlogevent.table == self.table:
                        logger.info(
                            "Processing row from table '%s': target=%s wob_id=%s",
                            binlogevent.table,
                            row["values"]["target"],
                            row["values"]["wob_id"],
                        )
                        yield (row["values"]["target"], row["values"]["wob_id"])
        stream.close()


class EventHandler:
    """
    Collects binlog events and processes them. Processing involves checking and killing
    specific MySQL sleep processes that match a given prefix.
    """

    def __init__(self, db_config=None, server_id=101, table="wob_message_queue"):
        self.events = queue.Queue(maxsize=200)
        self.db_config = db_config
        self.server_id = server_id
        self.table = table

    def collect_events(self):
        """
        Continuously collects binlog events and adds them to the internal queue.
        If an error occurs, it logs the error and retries after a delay.
        """
        while True:
            try:
                stream = ReplicationStream(self.db_config, self.server_id, self.table)
                for event in stream.get_next_event():
                    self.events.put(event)
            except Exception as e:
                logger.error("Error collecting events: %s", e)
                time.sleep(5)  # Retry after a delay

    def process_events(self):
        """
        Continuously processes events from the queue. For each event, it constructs
        a search string based on the provided prefix and the event's wob_id to find
        and kill corresponding long-running MySQL sleep processes.

        Note: If multiple CDC instances run concurrently with different prefixes,
        ensure that each prefix is unique. Otherwise, a CDC process might inadvertently
        kill a process that belongs to another queue.
        """
        target = None
        wobid = None
        con = mysql.connector.connect(
            user=self.db_config["user"],
            password=self.db_config["password"],
            port=int(self.db_config["port"]),
            host=self.db_config["host"],
            database="information_schema",
        )
        while True:
            try:
                logger.info("Waiting for new event...")
                if target is None:
                    target, wobid = self.events.get()

                if target is None or wobid is None:
                    continue

                if not con.is_connected():
                    con.reconnect(attempts=5, delay=2)

                # Fist we check the legacy form which didn't include the target in the WAIT_FOR_EVENT
                search_str = r"SELECT /* WAITING_FOR_EVENT (" + str(wobid) + r")"
                sql = (
                    "SELECT id FROM performance_schema.processlist WHERE substring(`INFO`,1,{}) = '{}' "
                    "and db <> 'performance_schema'"
                ).format(len(search_str), search_str)

                if str(target) == "processor":
                    with con.cursor() as cursor:
                        cursor.execute(sql)
                        result = cursor.fetchall()
                        for row in result:
                            logger.info(
                                "Event received - Target: %s, WobID: %s, process: %s",
                                target,
                                wobid,
                                row[0],
                            )
                            cursor.execute("KILL {}".format(row[0]))

                # Second we build the search string using the provided target and the wob_id from event
                if ">" not in target:
                    search_str = (
                        r"SELECT /* WAITING_FOR_EVENT ("
                        + str(wobid)
                        + "-"
                        + str(target)
                        + r")"
                    )
                    sql = (
                        "SELECT conn_id FROM sys.processlist WHERE substring(current_statement, 1, {}) = %s and db = 'miranda' and current_statement is not NULL"
                    ).format(len(search_str))

                    with con.cursor() as cursor:
                        cursor.execute(sql, (search_str,))
                        result = cursor.fetchall()
                        print(sql)
                        for row in result:
                            logger.info(
                                "Event received - Target: %s, WobID: %s, process: %s",
                                target,
                                wobid,
                                row[0],
                            )
                            cursor.execute("KILL {}".format(row[0]))

                # Third we build the search string using the crg target only (needed for crg_X>job messages)
                if ">" in target:
                    crg = target[: target.find(">")]
                    search_str = r"SELECT /* WAITING_FOR_EVENT (" + crg + r")"
                    sql = (
                        "SELECT conn_id FROM sys.processlist WHERE substring(current_statement, 1, {}) = %s and db = 'miranda' and current_statement is not NULL"
                    ).format(len(search_str))

                    with con.cursor() as cursor:
                        cursor.execute(sql, (search_str,))
                        result = cursor.fetchall()
                        print(sql)
                        for row in result:
                            logger.info(
                                "Event received - Target: %s, WobID: %s, process: %s",
                                crg,
                                wobid,
                                row[0],
                            )
                            cursor.execute("KILL {}".format(row[0]))
                # Reset target and wobid for the next event
                target = None
                wobid = None
            except Exception as e:
                logger.error("Error processing event: %s", e)
                logger.info("Retrying in 2 seconds")
                time.sleep(2)  # Retry after a delay

    def __call__(self):
        """
        Allow the instance to be called as a function to start collecting events.
        """
        self.collect_events()


def find_long_running_queries(con):
    """
    Identify long running queries that have been waiting for an event.
    This is done by querying the INFORMATION_SCHEMA.PROCESSLIST and looking for
    processes whose INFO contains a specific annotation and have been running for over 30 seconds.
    Returns a list of tuples containing process ID and the extracted annotation.
    """
    cursor = con.cursor()

    # Query processlist from MySQL's INFORMATION_SCHEMA
    sql = """
    SELECT ID, USER, HOST, DB, COMMAND, TIME, STATE, INFO
    FROM INFORMATION_SCHEMA.PROCESSLIST
    """
    cursor.execute(sql)
    processes = cursor.fetchall()

    long_running_processes = []

    # Filter processes that match the criteria: running for more than 30 seconds and containing an annotation.
    for process in processes:
        process_id, user, host, db, command, time_val, state, info = process
        if info is not None and time_val > 30 and "/*" in info:
            # Extract text inside /* ... */
            annotation_match = re.search(r"/\*(.*?)\*/", info)
            if annotation_match:
                annotation = annotation_match.group(1)
                long_running_processes.append((process_id, annotation))

    cursor.close()
    return long_running_processes


def extract_project_id(message: str) -> int:
    """
    Extracts a numeric project ID from the message, expected to be within parentheses.
    Returns the project ID if found, otherwise returns -1.
    """
    match = re.search(r"\((\d+)\)", message)
    if match:
        return int(match.group(1))
    else:
        return -1


def kill_processes(con, procs):
    """
    Attempts to kill MySQL processes based on a list of process IDs and annotations.
    It first checks if there are any running Docker jobs corresponding to the process ID.
    If not, it issues a KILL command for the process.
    Returns a list of killed process IDs.
    """
    cursor = con.cursor()
    killed_processes = []

    for idx, p in enumerate(procs):
        (process_id, message) = p
        logger.info(
            "Attempting to kill process - Index: %d, ID: %d, Message: '%s'",
            idx,
            process_id,
            message,
        )

        # Extract workflow object ID from the annotation in the process info.
        wob_id = extract_project_id(message)
        if wob_id == -1:
            continue

        # Query to find the metadata ID for the workflow object
        sql = "SELECT m.id FROM metadata m JOIN knowledge_object t ON t.metadata_id = m.id WHERE t.id = %s"
        cursor.execute(sql, (wob_id,))
        rs = cursor.fetchall()
        if not rs:
            continue
        wob_mid = rs[0][0]

        # Check if there are any running docker jobs associated with this metadata ID
        sql = (
            "SELECT m.id, t.workflow_state FROM edges e JOIN docker_job t ON e.dest_id = t.metadata_id "
            "JOIN metadata m on m.id = e.src_id WHERE m.id = %s and t.workflow_state in ('RUNNING','READY','RESUMEREADY')"
        )
        cursor.execute(sql, (wob_mid,))
        rs = cursor.fetchall()

        if len(rs) == 0:
            # No running docker jobs found; attempt to kill the process
            killed = False
            try:
                cursor.execute(f"KILL {process_id};")
                killed_processes.append(process_id)
                killed = True
            except mysql.connector.Error as err:
                logger.error("Failed to kill process %d. Error: %s", process_id, err)
            finally:
                if killed:
                    logger.info("Process %d killed successfully!", process_id)
        logger.info("")

    cursor.close()
    return killed_processes


if __name__ == "__main__":
    # Parse command line arguments to allow control over the prefix and server_id.
    parser = argparse.ArgumentParser(
        description="CDC process to manage and kill long running MySQL queries with a specified prefix."
    )
    parser.add_argument(
        "--server-id",
        type=int,
        default=101,
        help="Unique server_id for the CDC instance.",
    )
    parser.add_argument(
        "--table", type=str, default="wob_message_queue", help="The table we listen to."
    )
    args = parser.parse_args()
    server_id = args.server_id
    table = args.table

    # Obtain database configuration
    miranda_config = get_config()

    # Initialize event handler with the database configuration and server_id
    event_handler = EventHandler(
        db_config=miranda_config, server_id=server_id, table=table
    )
    # Start collecting binlog events in a separate daemon thread
    threading.Thread(target=event_handler, daemon=True).start()

    while True:
        try:
            with mysql.connector.connect(**miranda_config) as con:
                long_running_queries = find_long_running_queries(con)
                if long_running_queries:
                    logger.info("Identified long running queries:")
                    kill_processes(con, long_running_queries)
        except Exception as e:
            logger.error("Error managing long running queries: %s", e)
            time.sleep(1)  # Retry after a delay

        logger.info("Waiting for new wob message events...")
        # Process events
        event_handler.process_events()
