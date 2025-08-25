#
# Copyright (c) 2023,2024,2025 MainlyAI - contact@mainly.ai
#
from mirmod import miranda, workflow_object
from mirmod import processor_graph as pg
from mirmod.execution_context import (
    Execution_context_api,
    set_current_execution_context,
)
from mirmod.controls import Notice
from mirmod.storage import get_storage_interface_from_ecx
from mirmod.workflow_object import (
    Receiver,
    Transmitter,
    Transmitter_field,
    Receiver_field,
    WOB,
)
from mirmod.miranda_exceptions import MirandaStopCurrentIterator
import json
import dill as pickle
import traceback
import bdb
import inspect
import time
import base64

import networkx as nx
import sys
import os
from mirmod.utils.logger import logger
import importlib.util
import re
import subprocess
from datetime import datetime
import copy
import asyncio
import nest_asyncio

pickle.settings["recurse"] = True
pickle.load_types(pickleable=True, unpickleable=True)
nest_asyncio.apply()


_the_global_context = {"process_context": {}, "web_server_thread": None}
##########################
# execute_node() exit codes.
E_PROCEED_TO_NEXT_NODE = 0  # normal execution; mark node as executed and move instr ptr
E_MODIFIED_PLAN = 1  # execution plan is modified
E_SKIP_NODE = 2  # node was already executed. Move to next.
##########################


def write_process_context_to_disk():
    global _the_global_context
    with open("process_context.pickle", "wb") as file:
        pickle.dump(_the_global_context["process_context"], file)


def read_process_context_from_disk():
    global _the_global_context
    try:
        with open("process_context.pickle", "rb") as file:
            _the_global_context["process_context"] = pickle.load(file)
    except FileNotFoundError:
        print("|=> No process context exists yet.")
    except Exception as e:
        print(f"|=> The process context could not be read: {e}")


def delete_process_context_keys_with_suffix(suffix: str):
    """Delete all files with the given suffix"""
    global _the_global_context
    delete_list = []
    for k, v in _the_global_context["process_context"].items():
        if k.endswith(suffix):
            # logging.debug ("*** {} ends with {}".format(k, suffix))
            delete_list.append(k)
    for e in delete_list:
        print("|=> Removing {} from process context.".format(e))
        try:
            del _the_global_context["process_context"][e]
        except Exception as e:
            print("|=> ERROR: ", e)


class CodeCacheException(Exception):
    def __init__(self, wob_key, exception):
        self.wob_key = wob_key
        self.exception = exception


class Sleep_time:
    def __init__(self, min=0, max=10, steps=10, exponential=False):
        self.min = min
        self.max = max
        self.steps = steps
        self.count = 0
        self.exponential = exponential

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


class Default_storage_policy:
    def __init__(self):
        self.save_url = ""
        self.load_url = ""
        self.mount_path = "./"
        self.type = "LOCAL_STORE"

    def upload_file(self, file_path, destination_path="."):
        pass

    def download_file(self, file_path, destination_path="."):
        pass

    def list_files(self):
        # Return a list of all files in the current working directory
        return [f for f in os.listdir(self.mount_path) if os.path.isfile(f)]


DEFAULT_STORAGE_POLICY = Default_storage_policy()
INJECTED_HEADER_SIZE = (
    4  # The number of lines we inject in each code block before executing it.
)
WOB_FILE_TEMPLATE_PATH = "WOB-{}.py"  # NOTE: if changed; fix replace_wob_patterns()

has_executed_setup = {}


def load_plugin(plugin_path, plugin_name):
    spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
    plugin_module = importlib.util.module_from_spec(spec)
    sys.modules[plugin_name] = plugin_module
    spec.loader.exec_module(plugin_module)
    return plugin_module


def load_plugin_from_string(plugin_code, plugin_name):
    spec = importlib.util.spec_from_loader(plugin_name, loader=None)
    plugin_module = importlib.util.module_from_spec(spec)
    sys.modules[plugin_name] = plugin_module
    # Compile with a custom filename to trace back to the wob_key
    compiled_code = compile(plugin_code, filename=plugin_name, mode="exec")
    exec(compiled_code, plugin_module.__dict__)
    # exec(plugin_code, plugin_module.__dict__)
    return plugin_module


def make_wob_runtime_code(wob, wob_key):
    # Create wrapper for running a blend file
    print(
        "|=> ERROR: Unsupported code type {} for wob '{}'".format(
            wob.code_type, wob.name
        )
    )
    return ""


def process_traceback(T, compiler=False):
    # Capture the formatted traceback
    formatted_traceback = traceback.format_exc()

    # Regular expression to find entries with "File '<string>'"
    pattern2 = r"( \(detected at line )(\d+)\).*"
    pattern = r"(.*File \"<string>\", line )(\d+).*"
    pattern3 = r"(.*File .*, line )(\d+), in.*"

    # Function to subtract T from the line numbers
    def subtract_line_number(match):
        line_number = int(match.group(2))
        new_line_number = line_number - T
        return f"{match.group(1)}{new_line_number}"

    # Replace the matched entries with updated line numbers
    updated_traceback = re.sub(pattern, subtract_line_number, formatted_traceback)

    # Do a second pass to substitute any "detected at line" with the correct line number
    updated_traceback = re.sub(pattern2, subtract_line_number, updated_traceback)

    if compiler:
        # Do a third pass to substitute any "detected at line" with the correct line number
        updated_traceback = re.sub(pattern3, subtract_line_number, updated_traceback)

    return updated_traceback


# ---------------------------------------------------------------------------------------------

ALL_PROCESSOR_COMMANDS = {
    "break": "Insert a break point. Format: break <node id>:<line number>",
    "clear": "Clear all breakpoints",
    "stop": "Stop execution",
    "start": "Start or resstart execution of graph.",
    "restart": "Hard restart execution of graph which means the graph is reloaded and reinitialized.",
    "compile": "Compile a code block. Format: compile <code block id>",
    "info": "Information about the current execution state.",
    "git-pull": "Pull the latest version of the node code from the git repository.",
    "git-push": "Push the latest version of the node code to the git repository.",
    "git-soft-pull": "Pull the latest version of the code from the git repository without updating the nodes.",
    "run-setup": "Run setup sequence for the nodes in the graph.",
}


class CommandActorBase:
    def input(self, prompt):
        assert False, "Not implemented"

    def send_response(self, response):
        assert False, "Not implemented"


class MirandaDebuggerStopException(Exception):
    pass


class MirandaExecutionError(Exception):
    pass


class CommandActorDbg(CommandActorBase):
    """Use this class with the MirandaDebugger when developing the debugger."""

    def __init__(self, sc, docker_job, wob_id):
        self.commands = {
            "next": "Step to the next line of code",
            "step": "Step inside function.",
            "continue": "Continue execution until next breakpoint",
            "clear": "Clear all breakpoints",
            "stop": "Stop execution",
        }
        self.command = None

    def validate(self, command: str):
        command = command.strip()
        if " " in command:
            cmd, param = command.split(" ")
        else:
            cmd = command
        # print ("|=> DEBUG2: cmd = {}, param = {}".format(cmd, param))
        if cmd not in self.commands.keys():
            self.send_response(
                "Invalid command. These are valid commands:\n{}".format(
                    "\n".join(
                        ["  {}: {}".format(k, v) for k, v in self.commands.items()]
                    )
                )
            )
            return None
        return command

    def input(self, prompt):
        i = input(prompt)
        self.command = self.validate(i)
        return self.command

    def send_response(self, message):
        print("|=> {}".format(message))


class CommandActor(CommandActorBase):
    def __init__(
        self,
        sc: miranda.Security_context,
        docker_job,
        ko: miranda.Knowledge_object,
        deployed=False,
    ):
        self.commands = {
            "next": "Step to the next line of code",
            "step": "Step inside function.",
            "continue": "Continue execution until next breakpoint",
            "clear": "Clear all breakpoints",
            "stop": "Stop execution",
            "start": "Start or restart execution of graph. <mid> is the metadata id of the node to start from. <enc> is an encoded string containing breakpoints",
            "restart": "Restart execution of graph.",
            "info": "Information about the current execution state.",
        }
        self.command = None
        self.sctx = sc
        self.wob_id = ko.id
        self.wob_mid = ko.metadata_id
        self.tag = None
        self.ready_signal = "RESUMEREADY"
        self.docker_job = docker_job
        self.trigger_run = False
        self.deployed = deployed
        k = "{}_RUN".format(ko.id)
        self.trigger_run = k in _the_global_context["process_context"]
        if self.trigger_run:
            del _the_global_context["process_context"][k]
        write_process_context_to_disk()

    def validate(self, command: str):
        command = command.strip()
        if " " in command:
            cmd, param = command.split(" ")
        else:
            cmd = command
        if cmd not in self.commands.keys():
            self.send_response(
                "Invalid command. These are valid commands:\n{}".format(
                    "\n".join(
                        ["  {}: {}".format(k, v) for k, v in self.commands.items()]
                    )
                )
            )
            return None
        return command

    def clear_command_queue(self):
        # To avoid out-of-sync issues we clear the queue before we enter the waiting loop.
        # We also delete all old messages which also has been read and are older than 1 day.
        # with self.sctx.connect() as con:
        con = self.sctx.connect()
        with con.cursor(dictionary=True) as cur:
            cur.callproc("clear_wob_messages_for_processor", (self.wob_id,))
            con.commit()
            # Collect resultset from callproc
            for result in cur.stored_results():
                _ = result.fetchall()

    def wait_for_event(self, sleep_time, debug_prompt=""):
        wake_up_counter = 0
        rows = []
        while True:
            print("|=> ", debug_prompt)
            # with self.sctx.connect() as con:
            con = self.sctx.connect()
            with con.cursor(dictionary=True) as cur:
                # print ("DEBUG: get_wob_message_for_processor({})".format(self.wob_id))
                cur.callproc("get_wob_message_for_processor", (self.wob_id,))
                con.commit()
                # Collect resultset from callproc
                for result in cur.stored_results():
                    rows = result.fetchall()
                if rows is not None and len(rows) > 0:
                    return rows
                didnt_get_any_notification = False
                self.send_response({"status": self.ready_signal})
                s = 0
                try:
                    # with sc.connect() as con2:
                    #  with con2.cursor(dictionary=True) as cur2:
                    # Wait for a maximum of two minutes.
                    # Note: we're using wob_id here intentionally because policy is that there can only be one
                    # running project per wob_id.
                    s = round(sleep_time(), ndigits=1)
                    cur.execute(
                        "SELECT /* WAITING_FOR_EVENT ({}) */ SLEEP({})".format(
                            self.wob_id, s
                        )
                    )
                    _ = cur.fetchall()
                    didnt_get_any_notification = True
                except Exception:
                    # NOTE: Error is 2013: Lost connection to MySQL server during query which is expected.
                    if len(debug_prompt) > 0:
                        print("|=> Woke up from sleep.", debug_prompt)
                    else:
                        print("|=> Woke up from sleep.")

                if didnt_get_any_notification:
                    print(
                        "|=> Didn't get any notifications after {} seconds. Retrying... ({} {}))".format(
                            s, wake_up_counter, debug_prompt
                        )
                    )
                    time.sleep(1)
                    wake_up_counter += 1
                    if wake_up_counter > 20:
                        print(
                            "|=> WARNING: Shutting down the processor due to inactivity. ",
                            debug_prompt,
                        )
                        self.send_response({"status": "EXITED"})
                        exit(0)

    def input(self, prompt):
        """Get a debug command from the message queue."""
        if self.trigger_run:
            self.trigger_run = False
            self.command = "start"
            self.send_response({"status": "RUNNING"})
            return self.command
        self.send_response({"status": self.ready_signal})
        rows = None
        self.clear_command_queue()
        print("|=> Waiting for debug command...")
        sleep_time = Sleep_time(min=2, max=60 * 60 * 2, steps=20, exponential=True)
        rows = self.wait_for_event(sleep_time)
        self.send_response({"status": "RUNNING"})
        # We get here only if we got a result set.
        rs = json.loads(rows[0]["payload"])
        self.tag = rs.get("tag", None)
        i = rs["command"]
        # print ("|=> Received command: {}".format(i))
        self.command = self.validate(i)
        return self.command

    def send_response(self, message):
        if self.deployed:
            return
        if isinstance(message, str):
            message = {"log": message}
        if "status" in message:
            j = {
                "action": "update[DOCKER_JOB]",
                "data": {"id": self.docker_job.id, "workflow_state": message["status"]},
            }
            if self.tag is not None:
                j["data"]["tag"] = self.tag
            miranda.notify_gui(self.sctx, json.dumps(j))
            self.docker_job.workflow_state = message["status"]
            self.docker_job.update(self.sctx)
        else:
            if self.tag is not None:
                if "data" not in message:
                    message["data"] = {}
                message["data"]["tag"] = self.tag
            try:
                miranda.notify_gui(self.sctx, json.dumps(message))
            except Exception as e:
                print("DEBUG: notify_gui failed: ", e)
            # print ("|=> {}".format(message))

    def close(self):
        self.send_response({"status": "EXITED"})


class MirandaDebugger(bdb.Bdb):
    def __init__(
        self,
        command_actor: CommandActorBase = None,
        execution_context: Execution_context_api = None,
    ):
        super().__init__()
        self.breakpoints = {}
        self.current_frame = None
        self.ca: CommandActorBase = command_actor
        self.tracing = False
        self.current_source_code = None
        self.quit = False
        self.wob_key = -1
        self.execution_context = execution_context
        #
        # The source code is in a document stored as a code block. The code currently executing is a function in
        # that code block. We need to be able to calculate the relative line number given a line number in the code block source.
        self.offset = 0

    def set_current_source_code(self, src):
        self.current_source_code = src

    def clear_all_breakpoints(self):
        self.breakpoints.clear()

    def set_wob_key(self, wob_key):
        self.wob_key = wob_key

    def set_breakpoint(self, func, line):
        """Set a breakpoint at the given line in the given function."""
        self.breakpoints[(func.__name__, line)] = True

    def set_codeblock_src_offset(self, offset):
        self.offset = offset

    def to_relative_line_number(self, lineno):
        return lineno - self.offset

    def user_line(self, frame):
        func_name = frame.f_code.co_name
        line = frame.f_lineno - frame.f_code.co_firstlineno - 1
        hit_breakpoint = (func_name, line) in self.breakpoints
        jaction = {"action": "break", "data": {}}
        header_offset = INJECTED_HEADER_SIZE
        if hit_breakpoint or self.tracing:
            try:
                jaction["data"] = {
                    "line_number": frame.f_lineno - header_offset,
                    "locals": self.get_locals(frame),
                    "wob_key": self.wob_key,
                    "source_code": inspect.getframeinfo(frame).code_context[0].strip(),
                }
                self.ca.send_response(jaction)
            except Exception:
                if self.current_source_code is not None:
                    src_line = self.current_source_code.split("\n")[line]
                    jaction["data"] = {
                        "line_number": frame.f_lineno - header_offset,
                        "locals": self.get_locals(frame),
                        "wob_key": self.wob_key,
                        "source_code": src_line,
                    }
                    self.ca.send_response(jaction)
            # self.ca.send_response("Local variables: {}".format(frame.f_locals))
            self.print_locals(frame)
            self.current_frame = frame
            self.tracing = True
            cmd: str = None
            while cmd is None:
                cmd = self.ca.input("> ")
            if cmd == "clear":
                self.clear_all_breakpoints()
                # self.tracing = False
            elif cmd == "next":
                self.set_next(frame)
            elif cmd == "step":
                self.set_step()
            elif cmd.startswith("continue"):
                if " " in cmd:
                    _, param = cmd.split(" ")
                    # We have a base64 encoded payload containg all future breakpoints.
                    # converting into bytes from base64 system
                    convertedbytes = base64.b64decode(param)
                    # decoding the ASCII characters into alphabets
                    init_breakpoints = convertedbytes.decode()
                    jbreakpoints = json.loads(init_breakpoints)
                    # print ("DECODED BREAKPOINTS: {}".format(jbreakpoints["breakpoints"]))
                    self.breakpoints = {}
                    for bp in [int(bp) for bp in jbreakpoints["breakpoints"]]:
                        lineno = self.to_relative_line_number(bp)
                        self.breakpoints[(func_name, lineno)] = True
                self.current_frame = None
                self.tracing = False
                if len(self.breakpoints) == 0:
                    # Disable debugging and continue execution. This exploits the underlying implementation of Bdb.
                    self.set_continue()
            elif cmd == "stop":
                self.quit = True
                self.execution_context.stop_debugger = True
                # raise MirandaDebuggerStopException() # WE can't catch this exception for some reason.
                self.set_quit()
            elif cmd == "info":
                jaction = {
                    "action": "info",
                    "data": {
                        "wob_key": self.wob_key,
                        "line_number": frame.f_lineno - header_offset,
                        "locals": self.get_locals(frame),
                    },
                }
                self.ca.send_response(jaction)

    def get_locals(self, frame):
        variables = {}
        if "self" in frame.f_locals:
            for k, v in frame.f_locals["self"].__dict__.items():
                try:
                    if (
                        k
                        not in [
                            "sctx",
                            "has_loaded_artefacts",
                            "executed",
                            "attributes",
                            "_init",
                            "_execute",
                        ]
                        and not isinstance(v, Transmitter)
                        and not isinstance(v, Receiver)
                        and not isinstance(v, Transmitter_field)
                        and not isinstance(v, Receiver_field)
                    ):
                        variables[k] = "{}".format(str(v)[:256])
                except Exception:
                    variables[k] = "<unprintable>"
        return variables

    def print_locals(self, frame):
        variables = self.get_locals(frame)
        self.ca.send_response({"locals": variables})


def cache_wobs(sc, G, all_wobs=False):
    """The graph contains the metadata id of each code block, but we need to load the entire code block into memory in order
    to get API and code body so we can later call the transmitters and receivers."""
    cached_wobs: dict = {}
    order_of_execution = list(G.nodes)
    for ob in order_of_execution:
        if G.nodes[int(ob)]["type"] == "code":
            cached_wobs[int(ob)] = miranda.Code_block(sc, metadata_id=int(ob))
            setattr(cached_wobs[int(ob)], "executed", False)
    return cached_wobs


def construct_property_edge_list(sc, NG, cache):
    """Set the edge property if the NG graph."""
    for e in NG.edges():
        src_ob = cache[e[0]]
        if src_ob.id == -1:
            print(
                '|=> WARNING: Skipping edge with source metadata_id "{}" because it doesn\'t exist in the database'.format(
                    e[0]
                )
            )
            continue  # Ignore all but the basic Code_blocks
        dst_ob = cache[e[1]]
        assert dst_ob.id != -1, (
            "Can't find destination object with metadata_id {}".format(e[1])
        )
        attr: dict = miranda.get_edge_attribute(sc, src_ob, dst_ob)
        if attr is not None:
            for receiver in attr.keys():
                tr = attr[receiver]
                a = {
                    "source_transmitter_key": tr[0],
                    "destination_receiver_key": receiver,
                    "kind": tr[1],
                }
                if "attributes" not in NG.edges[e[0], e[1]]:
                    NG.edges[e[0], e[1]]["attributes"] = []
                NG.edges[e[0], e[1]]["attributes"].append(a)


def cache_code_and_init_nodes(NG, cached_wobs):
    """Compile all code and initialize all nodes."""
    code_cache: dict = {}
    for i, wob in enumerate(cached_wobs.values()):
        api = wob.api
        wob_key = int(wob.metadata_id)
        if wob_key not in NG.nodes:
            # print ("|=> Skipping code block \"{}\" ({}) because it doesn't exist in the graph".format(wob.name,wob.metadata_id))
            continue
        if api is None:
            print(
                '|=> WARNING: Skipping code block "{}" ({}) because it doesn\'t have an API'.format(
                    wob.name, wob.metadata_id
                )
            )
            continue
        api = json.loads(api)
        dyn_attrs = {}
        if "attributes" in api and api["attributes"] is not None:
            for attr in api["attributes"]:
                if (
                    attr is not None
                    and "value" in attr
                    and "name" in attr
                    and attr["value"] is not None
                ):
                    dyn_attrs[attr["name"]] = attr["value"]
        # If the code block doesn't include the header we add it here.
        preamble = (
            f'from mirmod.workflow_object import WOB\nwob = WOB("""{wob.name}""")'
        )
        dyn_attr_str = f"_DYNAMIC_NODE_ATTRS = {json.dumps(dyn_attrs)}"
        self_id_str = f"_THIS_WOB_ID = {wob.id}"
        runtime_code = f"{dyn_attr_str}\n{self_id_str}\n{preamble}\n{wob.body}"
        if len(runtime_code) < 5:
            print(
                '|=> WARNING: Skipping code block "{}" ({}) because it is too short'.format(
                    wob.name, wob.metadata_id
                )
            )
            continue
        if wob_key not in code_cache:
            try:
                if wob.update_policy == "SUBSCRIBE":
                    # fetch body attribute from the wob with the metadata_id = wob.cloned_from_id
                    # check cache if the clone wob already exists in the cache
                    # TODO why can't the compiled code be deepcopied?
                    # if wob.cloned_from_id in code_cache:
                    # use cached code block
                    #  code_cache[wob_key] = code_cache[wob.cloned_from_id]
                    #  code_cache[wob_key].wob = copy.deepcopy(code_cache[wob.cloned_from_id].wob)
                    # else:
                    # load the clone into the code cache and use it
                    if wob.code_type != "PYTHON":
                        runtime_code = make_wob_runtime_code(wob, wob_key)
                    else:
                        org_wob = miranda.Code_block(sc, metadata_id=wob.cloned_from_id)
                        runtime_code = f"{dyn_attr_str}\n{preamble}\n{org_wob.body}"
                    code_cache[wob_key] = load_plugin_from_string(
                        runtime_code, WOB_FILE_TEMPLATE_PATH.format(wob.metadata_id)
                    )
                elif wob.code_type == "PYTHON":
                    code_cache[wob_key] = load_plugin_from_string(
                        runtime_code, WOB_FILE_TEMPLATE_PATH.format(wob.metadata_id)
                    )
                else:
                    code_cache[wob_key] = load_plugin_from_string(
                        make_wob_runtime_code(wob, wob_key),
                        WOB_FILE_TEMPLATE_PATH.format(wob.metadata_id),
                    )
            except Exception:
                print(
                    '|=> WARNING: Skipping code block "{}" ({}) because it failed to compile'.format(
                        wob.name, wob.metadata_id
                    )
                )
                print(process_traceback(INJECTED_HEADER_SIZE))
                continue
            src_WOB: WOB = code_cache[wob_key].wob
            try:
                src_WOB._init(src_WOB)
            except Exception as e:
                raise CodeCacheException(wob_key, e)
            code_cache[wob_key].__dict__["__file__"] = os.path.abspath(
                WOB_FILE_TEMPLATE_PATH.format(wob.metadata_id)
            )
            with open(WOB_FILE_TEMPLATE_PATH.format(wob.metadata_id), "w") as f:
                f.write(runtime_code)
    return code_cache


def load_default_values(G, cached_wobs, code_cache):
    """Loads the default values of the attributes into the WOBs and also increase order if the word 'policy' in in the name."""
    for wob_key in G.nodes():
        if wob_key not in code_cache:
            continue
        wob_code = code_cache[int(wob_key)]
        wob = cached_wobs[int(wob_key)]
        # policies are executed first
        lname = wob.name.lower()
        if lname.find("policy") != -1:
            wob.order += 100

        wob_attr: dict = wob_code.wob.attributes
        for attr in wob_attr.keys():
            default_value = wob.get_attribute(attr)
            if (
                default_value is None
                or default_value["value"] is None
                or not isinstance(wob_attr[attr], Receiver)
            ):
                continue
            receiver: Receiver = wob_attr[attr]
            value = default_value["value"]
            # print ("|=> DEBUG: Value = '{}', receiver.kind = '{}'".format(value, receiver.kind.lower()))
            if receiver.kind.lower() == "number":
                if isinstance(value, bool):
                    pass
                elif isinstance(value, str) and (
                    value.lower() == "false" or value.lower() == "true"
                ):
                    value = value.lower() == "true"
                elif isinstance(value, str) and value.find(".") == -1:
                    value = int(value)
                elif isinstance(value, str) and value.find(".") != -1:
                    value = float(value)
            try:
                receiver.receive(wob_code.wob, value)
            except Exception:
                print(
                    '|=> WARNING: Failed to set default value \'{}\' for attribute "{}" in code block "{}" ({})'.format(
                        value, attr, wob.name, wob.metadata_id
                    )
                )
                print(process_traceback(INJECTED_HEADER_SIZE))
                pass


# -------------- BEGIN EXECUTION CONTEXT -----------------------------

execution_stack = []


class _Execution_context(Execution_context_api):
    def __init__(
        self,
        docker_job,
        ko,
        sc: miranda.Security_context,
        execution_plan=[],
        cached_wobs: dict = {},
        code_cache: dict = {},
        start_idx: int = 0,
        target_wob_mid=-1,
        execution_graph=None,
        deployed=False,
    ):
        global _the_global_context
        self.deployed = deployed
        self.debugger: MirandaDebugger = MirandaDebugger(
            CommandActor(sc, docker_job, ko, deployed=deployed), self
        )
        self.reset(
            sc,
            execution_plan,
            ko,
            cached_wobs,
            code_cache,
            start_idx,
            execution_graph=execution_graph,
        )
        self.breakpoints: dict = {}  # a dictionary of wobid -> list of line numbers
        self.init_breakpoints: dict = {}  # a list of breakpoints to use when an execution is starting
        self.debug_mode: bool = False
        self.reload_graph: bool = False  # HACK: used by the debugger to signal that we need to reload the graph
        self.stop_debugger: bool = False  # HACK: used by the debugger to signal that we stop the inner loop of debugging
        self.inbound_message = None
        """Currently only one storage policy can be in affect, but in the future we might support multiple policies."""
        self.current_storage_policy = DEFAULT_STORAGE_POLICY
        self.docker_job = docker_job
        self.web_server_thread = _the_global_context[
            "web_server_thread"
        ]  # points to a web server which might survive graph reloads
        self.global_context = _the_global_context  # points to a global context which suvives graph reloads
        self.process_context = _the_global_context["process_context"]
        self.caught_wob_error = (
            -1
        )  # True if we caught an error in a wob and we're in debug mode.
        self.requirements = []  # List of python modules to be installed before first execution.
        self.target_wob_mid = target_wob_mid  # Indication on how the graph was executed; needed for restarts after setup

    def find_node_by_mid(self, mid):
        idx = self._execution_plan_index.get(mid, None)
        if idx is not None:
            return self.execution_plan[idx]
        # for en in self.execution_plan:
        #  if en.node_mid == mid:
        #    return en
        return None

    def is_dispatcher(self, dst_wob_key):
        return "dispatches" in self.execution_graph.nodes[dst_wob_key]

    def check_field_is_exhausted(self):
        if self.active_iterator_field:
            return self.field_is_exhausted[self.active_iterator_field.id()]
        return False

    def get_web_server_thread(self):
        return self.web_server_thread.get("web_server_thread", None)

    def set_web_server_thread(self, i):
        self.web_server_thread["web_server_thread"] = i

    def get_global_context(self):
        return self.global_context

    def set_global_context(self, i):
        self.global_context = i

    def get_process_context(self):
        return self.process_context

    def reset(
        self,
        sc: miranda.Security_context,
        execution_plan=None,
        ko=None,
        cached_wobs=None,
        code_cache=None,
        start_idx: int = 0,
        execution_graph=None,
    ):
        """A dictionary mapping a node id to a functor which will run the _init() function of the code block."""
        self.delayed_reinitialize = {}
        """The current index in the execution plan."""
        self.current_node_idx: int = 0
        """A signal to determine if a generator-collector pair should be restarted."""
        self.restart_loop: bool = False
        """The execution plan is a list of metadata_ids in the order of execution."""
        self.execution_plan: list[pg.Execution_node] = None
        if execution_plan is not None:
            if len(execution_plan) == 0:
                raise Exception(
                    "Execution plan is empty. A graph must consist of at least two connected nodes."
                )
            self.set_execution_plan(execution_plan)
            """The current node is the metadata_id of the current node in the execution plan."""
            self.current_node: pg.Execution_node = self.execution_plan[
                self.current_node_idx
            ]
        """The stage is the name of the current stage of the execution, but it isn't used at the moment :) """
        self.stage = "Not initialized"
        """The previous node is the metadata_id of the previous node in the execution plan."""
        self.previous_node: pg.Execution_node = None
        """A dictionary of all nodes that have been executed. The key is the metadata_id of the node."""
        self._has_executed: dict = {}
        """A dictionary of the number of edges that have been received for each node. The key is the metadata_id of the node."""
        self.received_count: dict = {}
        """A dictionary determining if an interator belonging to a collector has been exhausted. """
        self.field_is_exhausted = {}
        """A dictionary of iterators for each out edge on the transmitter field. """
        self.iterators: dict = {}
        """A DiGraph of all the nodes. Edge attributes are stored in the "attributes" property of the edge."""
        if execution_graph is not None:
            self.execution_graph: nx.DiGraph = execution_graph
        """If fields are used then the current_execute_graph reflects the subroutine currently being executed."""
        self.current_execution_graph = 0
        """ A signal that the execution plan has reached the end."""
        self.eof = False
        """ A dictionary of all cached wobs (the nodes in the graph) where the key is the mid."""
        if cached_wobs is not None:
            self.cached_wobs: dict = cached_wobs

        """ The active_transmitter_field is the Field_descriptor of the receiver field that is currently being processed."""
        self.active_iterator_field = None
        """ When a generator-collector is nested inside another generator-collector, the outer pair is pushed onto the iterator stack. """
        self.iterator_stack = []

        """ The exexcution context can be accessed in the code if the nodes of the executing graph."""
        set_current_execution_context(self)

        """The security context controlls authentication to the database."""
        self.security_context = sc

        """The parent project inside which the graph lives. """
        if ko is not None:
            self.knowledge_object = ko
        """All compiled code of a wob is stored in this dictionary."""
        if code_cache is not None:
            self.code_cache = code_cache

        self.cached_iterator_response = {}

        """The current exception handler"""
        self.current_exception_handler = None

        """The field excepton handler stack"""
        self.active_exception_handlers = {}

    def enable_debug_mode(self):
        self.debug_mode = True

    def remaining_wobs(self, wob_cache):
        remaining_nodes = [
            k for k in self.executable_nodes if not self._has_executed.get(k, False)
        ]
        return len(remaining_nodes)

    def mark_as_executed(self, mid):
        self._has_executed[mid] = True

    def has_executed(self, mid):
        if mid not in self._has_executed:
            return False
        return self._has_executed[mid]

    def set_execution_plan(self, execution_plan):
        self.execution_plan = execution_plan
        self._execution_plan_index = {
            n.node_mid: i for i, n in enumerate(execution_plan)
        }
        self.executable_nodes = set([n.node_mid for n in execution_plan])
        self.current_node_idx = 0
        self.current_node = execution_plan[self.current_node_idx]
        self.send_execution_plan()

    def stop_current_iterator(self):
        self.restart_loop = False
        s = self.active_iterator_field
        for mid in [n for n in s.field_nodes if n != s.transmitter_mid]:
            self._has_executed[mid] = False
            self.received_count[mid] = 0
        asyncio.get_running_loop().run_until_complete(
            self.cleanup_current_iterator(no_execution=False)
        )
        self.move_instruction_pointer()
        raise MirandaStopCurrentIterator

    async def cleanup_current_iterator(self, no_execution=False):
        if self.active_iterator_field is not None:
            rmid = self.active_iterator_field.receiver_mid
            wob_code = self.code_cache[rmid]
            receiver_attribute = self.active_iterator_field.reciever_attr
            receiver = None
            if receiver_attribute != "-":
                receiver = wob_code.wob.attributes[receiver_attribute]
            else:
                for attr, func in wob_code.wob.attributes.items():
                    if isinstance(func, Receiver_field):
                        receiver = func
                        break
            receiver.receive(wob_code.wob, miranda.StopIterationToken)
            self.field_is_exhausted[self.active_iterator_field.id()] = True
            self.restart_loop = False

            # pop exception handler stack
            if self.active_iterator_field.id() in self.active_exception_handlers:
                del self.active_exception_handlers[self.active_iterator_field.id()]
            self.current_exception_handler = None

            # receive from all other edges
            in_edges = in_edges = self.execution_graph.in_edges(rmid, data=True)
            for E in in_edges:
                src_wob_key = E[0]
                dst_wob_key = E[1]
                attr: list = (
                    E[2]["attributes"]
                    if E[2] is not None and "attributes" in E[2]
                    else []
                )
                src_wob = self.cached_wobs[src_wob_key]
                src_code = self.code_cache[src_wob_key]
                dst_wob = self.cached_wobs[dst_wob_key]
                dst_code = self.code_cache[dst_wob_key]
                for e in attr:
                    src_transmitter_key = e["source_transmitter_key"]
                    dst_receiver_key = e["destination_receiver_key"]
                    # receive from all other edges but the receiver edge that triggered this call.
                    if dst_receiver_key == receiver_attribute:
                        continue
                    if await process_edge(
                        src_wob,
                        src_transmitter_key,
                        dst_wob,
                        dst_receiver_key,
                        src_code,
                        dst_code,
                        self,
                    ):
                        # a stop debug command was initiated. We need to return to the top of the loop.
                        return
            jaction = {
                "action": "running_node",
                "data": {"metadata_id": dst_wob.metadata_id},
            }
            self.debugger.ca.send_response(jaction)
            if not no_execution:
                try:
                    self.current_node_idx = self._execution_plan_index[rmid]
                    self.current_node = self.execution_plan[self.current_node_idx]
                    await execute_node(dst_code, dst_wob, dst_wob_key, self)
                except Exception as e:
                    dst_code.wob.executed["has_executed"] = False
                    handle_code_exception(self, dst_wob_key, e)
                    self.caught_wob_error = dst_wob_key
            # Make sure we're not executing this node again in this execution context.
            self.mark_as_executed(rmid)
            self.field_is_exhausted[self.active_iterator_field.id()] = True
            idx = self._execution_plan_index[rmid]
            self.move_instruction_pointer(absolute_idx=idx)  # Jump to receiver field.
            restore_execution_context(self)

    def current_node_has_been_executed(self):
        return self.has_executed(self.current_node.node_mid)

    def get_current_execution_plan(self):
        """Returns an array of metadata_ids in the order of execution."""
        return self.execution_plan

    def get_cached_wobs(self):
        """Returns a dictionary of all cached wobs where the key is the mid."""
        return self.cached_wobs

    def get_code_cache(self):
        return self.code_cache

    def get_current_wob_metadata_id(self):
        """Returns the metadata_id of the current node."""
        return self.current_node.node_mid

    def get_instruction_pointer(self):
        """The instruction pointer is the index of the current node mid in the execution plan."""
        return self.current_node_idx

    def get_current_wob(self):
        """Returns the current wob."""
        return self.cached_wobs[self.current_node.node_mid]

    def get_execution_graph(self):
        return self.execution_graph

    def get_stage(self):
        return self.stage

    def move_instruction_pointer(self, absolute_idx: int = -1):
        if absolute_idx == -1:
            self.current_node_idx += 1
            if self.current_node_idx >= len(self.execution_plan):
                self.eof = True
                #  print ("|=> Instruction pointer: EOF")
                # else:
                #  print ("|=> Instruction pointer: {} ({})".format(self.current_node_idx,self.cached_wobs[self.execution_plan[self.current_node_idx]].name))
                return None
        else:
            if absolute_idx >= len(self.execution_plan):
                self.eof = True
                raise Exception(
                    "Trying to move instruction pointer to an index {} that is out of bounds (max {})".format(
                        absolute_idx, len(self.execution_plan)
                    )
                )
            self.current_node_idx = absolute_idx
        self.current_node: pg.Execution_node = self.execution_plan[
            self.current_node_idx
        ]
        self.send_execution_plan()

    def send_execution_plan(self):
        if self.debugger is None or self.debugger.ca is None:
            return

        jaction = {"action": "plan", "data": {"plan": []}}
        for i in range(len(self.execution_plan)):
            # todo: i need to figure out how to use localbot again
            jaction["data"]["plan"].append(i > self.current_node_idx)
        self.debugger.ca.send_response(jaction)

    def get_security_context(self):
        return self.security_context

    def get_storage_policy(self):
        print(
            "WARN: get_storage_policy() is deprecated. Use get_storage_interface() instead."
        )
        return self.current_storage_policy

    def set_storage_policy(self, ob):
        print("WARN: set_storage_policy() is deprecated.")
        self.current_storage_policy = ob

    def get_knowledge_object(self):
        return self.knowledge_object

    def get_storage_interface(self):
        return get_storage_interface_from_ecx(self)

    def get_inbound_message(self):
        """Return the inbound message"""
        return self.inbound_message

    def get_docker_job(self):
        """Each session has an associated Docker_job object."""
        return self.docker_job

    def set_docker_job(self, docker_job):
        self.docker_job = docker_job

    def get_wob_file_template_path(self):
        return WOB_FILE_TEMPLATE_PATH.format(self.get_current_wob().id)

    def get_name(self):
        """Returns the name of the current node."""
        return self.cached_wobs[self.current_node.node_mid].name

    def set_name(self, new_name):
        """Set the name of the current node."""
        self.get_current_wob().name = new_name
        self.get_current_wob().update(self.get_security_context())

    async def execute_wob(self, wob):
        """Execute the wob."""
        old_current_node = self.current_node
        # Set the current node to the wob we're executing and use the global execution graph as context
        self.current_node = pg.Execution_node(
            self.execution_graph, wob.metadata_id, self.code_cache, self.cached_wobs
        )
        code = self.code_cache[wob.metadata_id]
        await code.wob._execute(code.wob)
        # Restore the current node to the previous value (the executer)
        self.current_node = old_current_node

    def get_requirements(self):
        return self.requirements

    def set_requirements(self, r):
        self.requirements = r

    def copy(self):
        """
        Return a deep‐copy of this execution context, sharing only:
          - security_context
          - docker_job (if it’s not deep‐copyable)
          - web_server_thread, global_context, process_context
        Everything else (plans, caches, graphs, iterators, etc.) is deep‐copied.
        """
        # 1) Create a brand‐new context (new debugger, same SC)
        new_ctx = _Execution_context(
            docker_job=self.docker_job,
            ko=self.knowledge_object,
            sc=self.security_context,
            execution_plan=self.execution_plan,
            cached_wobs=self.cached_wobs,
            code_cache=self.code_cache,
            # __init__ ignores start_idx internally, so we'll patch it below
            start_idx=0,
            target_wob_mid=self.target_wob_mid,
            execution_graph=self.execution_graph,
            deployed=self.deployed,
        )

        # 2) Copy over all mutable state except SC/thread/global
        new_ctx.breakpoints = self.breakpoints
        new_ctx.init_breakpoints = self.init_breakpoints
        new_ctx.debug_mode = self.debug_mode
        new_ctx.reload_graph = self.reload_graph
        new_ctx.stop_debugger = self.stop_debugger
        new_ctx.inbound_message = self.inbound_message
        new_ctx.current_storage_policy = self.current_storage_policy

        # share these (not deep‐copyable or meant to be shared)
        new_ctx.web_server_thread = self.web_server_thread
        new_ctx.global_context = self.global_context
        new_ctx.process_context = self.process_context

        new_ctx.caught_wob_error = self.caught_wob_error
        new_ctx.requirements = list(self.requirements)

        new_ctx.stage = self.stage
        new_ctx.previous_node = self.previous_node

        new_ctx._has_executed = {}
        new_ctx.received_count = {}
        new_ctx.field_is_exhausted = {}
        new_ctx.iterators = {}

        # fix up plan‐index and current‐node
        new_ctx.current_node_idx = self.current_node_idx
        new_ctx.current_node = self.current_node

        new_ctx.current_execution_graph = self.current_execution_graph
        new_ctx.eof = self.eof
        new_ctx.active_iterator_field = copy.copy(self.active_iterator_field)
        new_ctx.iterator_stack = copy.copy(self.iterator_stack)
        new_ctx.cached_iterator_response = {}
        set_current_execution_context(new_ctx)
        return new_ctx


# ----------------- END: Execution context -----------------#


def set_active_iterator(
    transmitter_mid, attribute_key, execution_context: _Execution_context
):
    en: pg.Execution_node = execution_context.find_node_by_mid(transmitter_mid)
    if len(en.get_dispatches()) > 0:
        execution_context.active_iterator_field = en.field(attr=attribute_key)
        if (
            execution_context.active_iterator_field
            not in execution_context.iterator_stack
        ):
            execution_context.iterator_stack.append(
                execution_context.active_iterator_field
            )
        if (
            execution_context.active_iterator_field.id()
            not in execution_context.field_is_exhausted
        ):
            execution_context.field_is_exhausted[
                execution_context.active_iterator_field.id()
            ] = False
        return execution_context.active_iterator_field

    field: pg.Field_descriptor = en.field()
    assert field is not None, "Transmitter node {} has no field.".format(en)
    # print ("|=> DEBUG: Active field: {}".format(field))
    execution_context.active_iterator_field = field
    if execution_context.active_iterator_field not in execution_context.iterator_stack:
        execution_context.iterator_stack.append(execution_context.active_iterator_field)
    if (
        execution_context.active_iterator_field.id()
        not in execution_context.field_is_exhausted
    ):
        execution_context.field_is_exhausted[
            execution_context.active_iterator_field.id()
        ] = False
    return execution_context.active_iterator_field


def restore_execution_context(execution_context: _Execution_context):
    """Resets various properties of the execution context."""
    if execution_context.active_iterator_field is None:
        return  # don't trigger a instruction pointer jump.

    s = execution_context.active_iterator_field
    iterator_key = s.id()
    if iterator_key not in execution_context.iterators:
        # print ("DEBUG: restore_execution_context: iterator_key= {} not in iterator!".format(iterator_key))
        # print ("DEBUG: len(iterator_stack)= {} ".format(len(execution_context.iterator_stack)))
        return
    if iterator_key is not None:
        del execution_context.iterators[iterator_key]
    # If we have a nested iterator we can pop the iterator stack to restore the previously active transmitter field
    # and trigger an instruction pointer jump.
    if len(execution_context.iterator_stack) == 0:
        return
    previous_active_iterator_field = execution_context.iterator_stack.pop()
    if len(execution_context.iterator_stack) == 0:
        execution_context.active_iterator_field = None
        return
    else:
        execution_context.active_iterator_field = execution_context.iterator_stack[-1]

    class Reinit:
        def __init__(self, wob_code, wob):
            self.wob_code = wob_code
            self.wob = wob

        def __call__(self):
            self.wob_code.wob._init(
                self.wob_code.wob
            )  # reinitialize the collector. TODO there should be a reset API for this
            wob_attr: dict = self.wob_code.wob.attributes

            for attr in wob_attr.keys():
                default_value = self.wob.get_attribute(attr)
                if (
                    default_value is None
                    or default_value["value"] is None
                    or not isinstance(wob_attr[attr], Receiver)
                ):
                    continue
                receiver: Receiver = wob_attr[attr]
                value = default_value["value"]
                receiver.receive(self.wob_code.wob, value)

    wob_code = execution_context.code_cache[previous_active_iterator_field.receiver_mid]
    wob = execution_context.cached_wobs[previous_active_iterator_field.receiver_mid]
    execution_context.delayed_reinitialize[
        previous_active_iterator_field.transmitter_mid
    ] = Reinit(wob_code, wob)
    if previous_active_iterator_field.id() in execution_context.field_is_exhausted:
        execution_context.field_is_exhausted[previous_active_iterator_field.id()] = (
            False
        )
    execution_context.received_count[previous_active_iterator_field.transmitter_mid] = 0
    for node in previous_active_iterator_field.field_nodes:
        execution_context._has_executed[node] = False

    # We need to recursively loop over all subroutines
    def recursive_restore(s: pg.Field_descriptor):
        execution_context.field_is_exhausted[s.id()] = False
        if s.id() in execution_context.cached_iterator_response:
            del execution_context.cached_iterator_response[s.id()]
        for mid in s.field_nodes:
            execution_context._has_executed[mid] = False
            execution_context.received_count[mid] = 0
            # print ("|=> DEBUG: Resetting execution flag for {}".format(mid))
        for ss in s.contains_fields:
            recursive_restore(ss)

    recursive_restore(previous_active_iterator_field)


class Get_wob_source_details_functor:
    def __init__(self, sc, cached_wobs, execution_context):
        self.sc = sc
        self.cached_wobs = cached_wobs
        self.execution_context = execution_context
        self.exception_points = []

    def __call__(self, wob_mid, line_number, func_name):
        wob = self.cached_wobs[int(wob_mid)]
        src_code = wob.body
        # Find the line number in the source code
        lines = src_code.split("\n")
        enumerated_lines = {i: line for i, line in enumerate(lines, start=1)}
        offset = INJECTED_HEADER_SIZE
        line_number = line_number - offset
        if line_number not in enumerated_lines:
            print(
                "|=> WARNING: Line number {} not found in wob {}".format(
                    line_number, wob.name
                )
            )
            return f"WOB('{wob.name}', {wob.id}), line {line_number}, in {func_name})"
        else:
            line = enumerated_lines[line_number]
            self.exception_points.append(
                {
                    "wob_key": wob.metadata_id,
                    "wob_name": wob.name,
                    "wob_id": wob.id,
                    "line_number": line_number,
                    "function_name": func_name,
                }
            )
            return (
                f"('{wob.name}', {wob.id}), line {line_number} ({func_name}) : {line}"
            )


def replace_wob_patterns(trace, get_wob_source_details):
    def replacement(match):
        wob_mid = match.group(1)
        line_number = int(match.group(2))
        func_name = match.group(3)
        return get_wob_source_details(wob_mid, line_number, func_name)

    # Find and replace WOB-xxxx patterns with the function call
    # NOTE: sub must correspond to the WOB_FILE_TEMPLATE_PATH
    return re.sub(r'File "WOB-(\d+).py", line (\d+), in (\w*)', replacement, trace)


def handle_code_exception(execution_context, src_wob_key, e):
    print("|=> ERROR: {}".format(e))
    trace = traceback.format_exc()
    func = Get_wob_source_details_functor(
        execution_context.get_security_context(),
        execution_context.cached_wobs,
        execution_context,
    )
    try:
        trace = replace_wob_patterns(trace, func)
        print("|=> ERROR:", trace)
        # print ("|=> ERROR: {}".format(traceback.format_exc()))
        print(
            '|=> ERROR: Exception in node "{}" ({})'.format(
                execution_context.cached_wobs[src_wob_key].name, src_wob_key
            )
        )
        ca = execution_context.debugger.ca
        if ca is not None:
            ca = execution_context.debugger.ca
        if ca is not None:
            ep = func.exception_points[-1]
            jaction = {
                "action": "exception",
                "data": {
                    "wob_key": ep["wob_key"],
                    "line_number": ep["line_number"],
                    "funcname": ep["function_name"],
                    "traceback": trace,
                },
            }
            ca.send_response(jaction)

    except Exception:
        print(
            "|=> ERROR: There were problems in identifying where in the source the exception occurred."
        )
        print(trace)


def get_value_from_iterator(
    subr,
    transmitter,
    src_code,
    execution_context: _Execution_context,
    transmitter_key,
    wob,
):
    """Returns a tuple of the value and a boolean indicating if the iterator is exhausted."""
    value = None
    exception_handler = None
    if subr.id() in execution_context.cached_iterator_response:
        # The iterator response is the same for every adjacent node to the field socket.
        # Don't mix this with the iterator itself which is a generator that produce the response
        # which is cached.
        return execution_context.cached_iterator_response[subr.id()]
    if subr.id() not in execution_context.iterators:
        it_value = transmitter.transmit(src_code.wob)
        if not isinstance(it_value, tuple):
            raise Exception(
                'Transmitter field "{}" in node "{}" did not return a proper iterator. The field iterator must be a tuple: (None | ExceptionHandler, iter())'.format(
                    transmitter_key, wob.name
                )
            )
        # Every branch needs their own iterator, we store this in the execution context and the content is copied on a push.
        execution_context.iterators[subr.id()] = it_value
        exception_handler, get_value = it_value
    else:
        exception_handler, get_value = execution_context.iterators[subr.id()]
    if exception_handler is not None:
        if execution_context.current_exception_handler != exception_handler:
            execution_context.active_exception_handlers[subr.id()] = (
                execution_context.current_exception_handler
            )

    execution_context.current_exception_handler = exception_handler

    value = next(get_value)
    execution_context.cached_iterator_response[subr.id()] = value
    return value


def dbug_execute(execution_context: _Execution_context, wob_key: int, code) -> bool:
    """returns True if the execution should stop."""
    cached_wobs = execution_context.cached_wobs
    dbg = execution_context.debugger
    if (
        wob_key in execution_context.breakpoints
        and len(execution_context.breakpoints[wob_key]) > 0
    ):
        # We need to find the offset position for the execute function.
        offset: int = cached_wobs[wob_key].body.find("@wob.execute")
        offset += cached_wobs[wob_key].body[offset:].find("\n")
        offset += cached_wobs[wob_key].body[offset:].find("\n") + 1
        source_code = cached_wobs[wob_key].body[offset:]
        dbg.set_current_source_code(source_code)
        line_offset = len(cached_wobs[wob_key].body[:offset].split("\n"))
        dbg.set_codeblock_src_offset(line_offset)
        dbg.set_wob_key(wob_key)
        for bp in execution_context.breakpoints[wob_key]:
            # lines = ["{}: {}".format(i,l) for i,l in enumerate(cached_wobs[wob_key].body[offset:].split("\n"))]
            # print ("|=> Trigger breakpoint ofn {}:{}: {}".format(wob_key,bp, lines[bp]))
            dbg.set_breakpoint(code.wob._execute, bp)
        dbg.runcall(code.wob._execute, code.wob)
        if dbg.quit or execution_context.stop_debugger:
            execution_context.stop_debugger = False
            return True
    else:
        code.wob._execute(code.wob)
    return False


async def process_edge(
    src_wob,
    src_transmitter_key,
    dst_wob,
    dst_receiver_key,
    src_code,
    dst_code,
    execution_context: _Execution_context,
    do_execute=True,
) -> bool:
    # print ("|=> Processing edge  [{} : {}] -> [{} : {}] ".format(src_wob.name,src_transmitter_key, dst_wob.name, dst_receiver_key))
    # If the transmitter node has no inbound edges and hasn't been executed yet, execute it.
    src_wob_key = src_wob.metadata_id
    execution_context.mark_as_executed(src_wob_key)

    # TRANSMIT -------------------------------------------------
    if src_transmitter_key not in src_code.wob.attributes:
        print(
            "|=> ERROR: Node {} doesn't have a transmitter field "
            '"named "{}"\nMaybe you have a ghost edge?'.format(
                src_wob.name, src_transmitter_key
            )
        )
        return False  # Skip this edge as it is a ghost edge
    transmitter = src_code.wob.attributes[src_transmitter_key]
    receiver = dst_code.wob.attributes[dst_receiver_key]
    # If this is a transmitter field then the the output is an iterator and we need
    # to extract the value before we transmit it to the receiver.
    try:
        if isinstance(transmitter, Transmitter_field):
            # is there a delayed initialization associated with this field?
            if src_wob_key in execution_context.delayed_reinitialize:
                # yes there is! This will clean up the collector in case we're in a nested field.
                execution_context.delayed_reinitialize[src_wob_key]()
                del execution_context.delayed_reinitialize[src_wob_key]
                s = execution_context.current_node.field()
                execution_context._has_executed[s.receiver_mid] = False
                execution_context.received_count[s.receiver_mid] = 0

            # Look up transmitter to get the responsible collector. If the transmitter is the
            # first transmitter in the chain, push the execution context.
            s = set_active_iterator(src_wob_key, src_transmitter_key, execution_context)
            if execution_context.check_field_is_exhausted():
                return
            value = get_value_from_iterator(
                s,
                transmitter,
                src_code,
                execution_context,
                src_transmitter_key,
                src_wob,
            )
        else:
            # This is just regular transmitter and a value is returned directly.
            value = transmitter.transmit(src_code.wob)

        # RECEIVE -------------------------------------------
        receiver.receive(dst_code.wob, value)
        # if execution_context.active_iterator_field == None:
        #  print ("DEBUG: process_edge: active_iterator_field is None. ")
        if (
            execution_context.active_iterator_field
            and isinstance(receiver, Receiver_field)
            and execution_context.active_iterator_field.id() is not None
            and not execution_context.field_is_exhausted[
                execution_context.active_iterator_field.id()
            ]
        ):
            execution_context.restart_loop = True
            execution_context.cached_iterator_response = {}
    except StopIteration:
        # We get here if we either failed to peek ahead or if the field was empty to begin with.
        await execution_context.cleanup_current_iterator()
        execution_context.move_instruction_pointer()
        # Translate StopIteration exception to bypass the special translation rule in PEP 479.
        raise MirandaStopCurrentIterator
    except MirandaStopCurrentIterator:
        pass  # A receiver field was forcefully stopped.
    except Exception as e:
        handle_code_exception(execution_context, dst_wob.metadata_id, e)
        raise e
    return False  # continue processing


async def execute_if_no_inbound_edges(
    src_wob, src_code, execution_context: _Execution_context
):
    src_wob_key = src_wob.metadata_id
    if len(
        execution_context.execution_graph.in_edges(src_wob_key)
    ) == 0 and not execution_context.has_executed(src_wob_key):
        # print ("|=> Executing \"{}\" because it has no inbound edges.".format(src_wob.name))
        # hack - update execution context so that current wob mid is set correctly
        old_current_node = execution_context.current_node
        execution_context.current_node = pg.Execution_node(
            execution_context.execution_graph,
            src_wob_key,
            execution_context.code_cache,
            execution_context.cached_wobs,
        )
        try:
            res = await execute_node(src_code, src_wob, src_wob_key, execution_context)
            if res == E_SKIP_NODE:
                # node was already executed; move to next node.
                execution_context.current_node = old_current_node
                return True
        except MirandaDebuggerStopException:
            execution_context.current_node = old_current_node
            return True  # stop processing
        except StopIteration as e:
            raise e
        except StopAsyncIteration as e:
            raise e
        except Exception as e:
            handle_code_exception(execution_context, src_wob_key, e)
            execution_context.caught_wob_error = src_wob_key
            raise e
        execution_context.mark_as_executed(src_wob_key)
        execution_context.current_node = old_current_node


async def execute_dispatches(dispatcher_mid, execution_context: _Execution_context):
    en: pg.Execution_node = execution_context.find_node_by_mid(dispatcher_mid)
    dispatches = en.get_dispatches()
    executed_atleast_one_plan = True
    old_execution_plan_index = execution_context.current_node_idx
    old_execution_plan = execution_context.execution_plan
    old_has_executed = execution_context._has_executed.copy()
    old_execution_graph = execution_context.execution_graph
    while executed_atleast_one_plan:
        executed_atleast_one_plan = False
        for dispatch in dispatches:
            # print ("|=> INFO: Running dispatch {}:{}".format(dispatcher_mid,dispatch["dispatch"]))
            plan = dispatch["plan"]
            # en.graph = dispatch["graph"]
            plan = [en] + plan
            execution_context.execution_graph = dispatch["graph"]
            execution_context._has_executed = {dispatcher_mid: True}
            # dispatch
            if len(plan) == 0:
                print(
                    "|=> WARNING: Execution plan for dispatch {}:{} was empty.".format(
                        dispatcher_mid, dispatch["dispatch"]
                    )
                )
                continue
            execution_context.set_execution_plan(plan)

            # start transmitter node has several attributes and we need to rewrite the active field for each
            fields = en.is_part_of_field
            field = fields[dispatch["dispatch"]]
            if field is None:
                print(
                    "|=> ERROR: Dispatch {}:{} doesn't have a field.".format(
                        dispatcher_mid, dispatch["dispatch"]
                    )
                )
                continue
            execution_context.executable_nodes = set([n.node_mid for n in plan])
            execution_context.executable_nodes.add(dispatcher_mid)
            # print ("field_exhausted= ", execution_context.field_is_exhausted)
            if not execution_context.field_is_exhausted.get(field.id(), False):
                await execute_plan(
                    execution_context,
                    execution_context.cached_wobs,
                    execution_context.code_cache,
                    in_dispatch=True,
                )
                executed_atleast_one_plan = True
            # Reset the execution context for next dispatch
            for disp_node in plan:
                if disp_node.node_mid == dispatcher_mid:
                    continue
                execution_context.received_count[disp_node.node_mid] = 0
            execution_context.cached_iterator_response = {}
            execution_context.set_execution_plan(old_execution_plan)
            execution_context.current_node_idx = 0
            execution_context.restart_loop = True
        print("|=> INFO: Next round of dispatches.")
    # print ("|=> INFO: Done all dispatches.")
    execution_context.set_execution_plan(old_execution_plan)
    execution_context.execution_graph = old_execution_graph
    execution_context._has_executed = old_has_executed
    execution_context.current_node_idx = old_execution_plan_index


def async_execute_plan(
    execution_context: _Execution_context, cached_wobs, code_cache, in_dispatch=False
):
    coroutine_object = execute_plan(
        execution_context, cached_wobs, code_cache, in_dispatch
    )
    try:
        loop = asyncio.get_running_loop()
        print(
            f"|=> INFO: An event loop is already running: {loop}. Attempting to run coroutine on it."
        )
        # This relies on the loop supporting re-entrant run_until_complete
        # (e.g., if nest_asyncio has been applied, common in Jupyter).
        result = loop.run_until_complete(coroutine_object)
        print(f"|=> INFO: Async execution result (on existing loop): {result}")

    except RuntimeError as e:
        if "no running event loop" in str(e).lower():
            # No event loop is running. Use asyncio.run().
            print("|=> INFO: No event loop running. Using asyncio.run().")
            result = asyncio.run(coroutine_object)
            print(f"|=> INFO: Async execution result (via asyncio.run): {result}")
        elif "already running" in str(e).lower():
            # This means get_running_loop() succeeded, but loop.run_until_complete failed
            # because the loop is strictly non-re-entrant (nest_asyncio not active).
            print(
                f"|=> ERROR: Event loop {loop} is already running and does not support re-entrant "
                "execution for synchronous blocking (e.g., nest_asyncio is not active)."
            )
            # Depending on policy, you might raise, log, or attempt a fallback.
            # For this example, we'll re-raise as it's a significant issue for this path.
            raise
        else:
            raise  # Re-raise other RuntimeErrors


async def execute_plan(
    execution_context: _Execution_context, cached_wobs, code_cache, in_dispatch=False
):
    set_current_execution_context(execution_context)
    order_of_execution = execution_context.execution_plan
    while True:
        if execution_context.caught_wob_error > -1:
            break
        if execution_context.current_node_idx >= len(execution_context.execution_plan):
            print("|=> INFO: DONE!")
            break
        execution_context.current_node = order_of_execution[
            execution_context.current_node_idx
        ]
        if execution_context.current_node_has_been_executed():
            # Is it a dispatch node? If so this is an opportune moment to execute it.
            d = execution_context.current_node.get_dispatches()
            if not in_dispatch and len(d) > 0:
                await execute_dispatches(
                    execution_context.current_node.node_mid, execution_context.copy()
                )
            execution_context.move_instruction_pointer()
            continue  # Skip nodes which has already been executed

        # Use global graph when determining the in-edges
        in_edges = execution_context.execution_graph.in_edges(
            execution_context.current_node.node_mid, data=True
        )
        # print (execution_context.current_node.node_mid,in_edges)
        if len(in_edges) == 0:
            # print ("|=> DEBUG: No incoming edges, skipping")
            # Instruction mover uses local subroutine graph
            # Is it a dispatch node? If so this is an opportune moment to execute it.
            d = execution_context.current_node.get_dispatches()
            if len(d) > 0 and not in_dispatch:
                src_wob = cached_wobs[execution_context.current_node.node_mid]
                src_code = code_cache[execution_context.current_node.node_mid]
                await execute_if_no_inbound_edges(src_wob, src_code, execution_context)
                await execute_dispatches(
                    execution_context.current_node.node_mid, execution_context.copy()
                )
            execution_context.move_instruction_pointer()
            continue
        execution_context.restart_loop = False

        for E in in_edges:
            dst_wob_key = E[1]
            execution_context.received_count[dst_wob_key] = 0

        try:
            for E in in_edges:
                src_wob_key = E[0]
                dst_wob_key = E[1]
                attr: list = (
                    E[2]["attributes"]
                    if E[2] is not None and "attributes" in E[2]
                    else []
                )
                src_wob = cached_wobs[src_wob_key]
                src_code = code_cache[src_wob_key]
                res = await execute_if_no_inbound_edges(
                    src_wob, src_code, execution_context
                )
                if res:
                    return

                dst_wob = cached_wobs[dst_wob_key]
                dst_code = code_cache[dst_wob_key]

                for e in attr:
                    src_transmitter_key = e["source_transmitter_key"]
                    dst_receiver_key = e["destination_receiver_key"]
                    res = await process_edge(
                        src_wob,
                        src_transmitter_key,
                        dst_wob,
                        dst_receiver_key,
                        src_code,
                        dst_code,
                        execution_context,
                    )
                    if res:
                        # a stop debug command was initiated. We need to return to the top of the loop.
                        return
                    #
                    # We need to keep track on how many inbound edges we have received from
                    # so that we can trigger the node execution.
                    #
                    execution_context.received_count[dst_wob_key] += 1
                    ############################## END for attr

                    # All attributes are processed. Check if we processed all inbounded edges for this node.
                    # print ("|=> DEBUG: in_degree({}) = {}, received_count[{}] = {}".format(dst_wob_key, in_degree(NG, dst_wob_key), dst_wob_key, execution_context.received_count[dst_wob_key]))
                    ## END FOR
                if (
                    pg.in_degree(execution_context.execution_graph, dst_wob_key)
                    <= execution_context.received_count[dst_wob_key]
                ):
                    node_exec_result = E_PROCEED_TO_NEXT_NODE
                    if execution_context.restart_loop:
                        s = execution_context.active_iterator_field
                        for mid in [n for n in s.field_nodes if n != s.transmitter_mid]:
                            execution_context._has_executed[mid] = False
                            execution_context.received_count[mid] = 0
                        idx = execution_context._execution_plan_index[s.transmitter_mid]
                        execution_context.move_instruction_pointer(absolute_idx=idx)
                        execution_context.restart_loop = False
                    else:
                        try:
                            node_exec_result = await execute_node(
                                dst_code, dst_wob, dst_wob_key, execution_context
                            )
                            if (
                                node_exec_result == E_SKIP_NODE
                            ):  # Node has already been executed.
                                execution_context.move_instruction_pointer()
                                continue
                        except MirandaStopCurrentIterator as e:
                            raise e
                        except Exception as e:
                            if in_dispatch:
                                raise e
                            dst_code.wob.executed["has_executed"] = False
                            handle_code_exception(execution_context, dst_wob_key, e)
                            execution_context.caught_wob_error = dst_wob_key
                            break  # Don't mark this node as executed and exit edge loop
                        # Make sure we're not executing this node again in this execution context.
                        if node_exec_result == E_PROCEED_TO_NEXT_NODE:
                            # Only mark the node as executed if execution plan hasn't changed.
                            execution_context.mark_as_executed(dst_wob_key)
                        d = execution_context.current_node.get_dispatches()
                        if not in_dispatch and len(d) > 0:
                            await execute_dispatches(
                                execution_context.current_node.node_mid,
                                execution_context.copy(),
                            )
                        # If the executing node was a Receiver_field and the iterator stack isn't empty we pop it.
                        # Note that this happens regardless of node execution result because it isn't allowed to
                        # change the execution plan at this point.
                        if (
                            pg.has_receiver_field(
                                execution_context.execution_graph,
                                dst_wob_key,
                                None,
                                execution_context.code_cache,
                            )
                            and len(execution_context.iterator_stack) > 0
                        ):
                            restore_execution_context(execution_context)
                            execution_context.move_instruction_pointer()
                            break  #
            if node_exec_result == E_PROCEED_TO_NEXT_NODE:
                # Only move the instruction pointer if the current node is marked as been executed
                # and we haven't modified the execution plan during node execution.
                if execution_context.has_executed(
                    execution_context.get_current_wob_metadata_id()
                ):
                    execution_context.move_instruction_pointer()
        except StopIteration:
            # Because we issued a StopIteration during process_edge (but not execute) we did not move_instruction_pointer()
            # This means the instruction pointer now points on the receiver field as a consequence of the
            # iterator clean up routine. This should be made more implicit as it is hard to track in the code.
            pass
        except MirandaStopCurrentIterator:
            pass  # A receiver field was forcefully stopped.
        # continue with while loop
        # print ("DEBUG loop")

    if execution_context.caught_wob_error > -1:
        print("|=> ERROR: Execution was interrupted due to an error WOB code.")
    else:
        print(
            "|=> INFO: Successfully executed {} nodes.".format(len(order_of_execution))
        )
    # print ("|=> Nodes executed in the following order:")
    # for i, msg in enumerate(execution_log):
    #  print ("|=>   {}: {}".format(i, msg))


async def f_next_element(execution_context: _Execution_context):
    # print("f_next_element")
    s = execution_context.active_iterator_field
    for mid in [n for n in s.field_nodes if n != s.transmitter_mid]:
        execution_context._has_executed[mid] = False
        execution_context.received_count[mid] = 0
    idx = execution_context._execution_plan_index[s.transmitter_mid]
    execution_context.cached_iterator_response = {}  # clear cache to force new iteration
    execution_context.move_instruction_pointer(absolute_idx=idx)


async def f_exit(execution_context: _Execution_context):
    # print("f_exit")
    execution_context.stop_current_iterator()


async def f_restart(execution_context: _Execution_context):
    # print ("f_restart")
    cur_itr_field = execution_context.active_iterator_field

    # Make sure all nodes in the field can re-execute.
    execution_context._has_executed[cur_itr_field.transmitter_mid] = False
    execution_context.received_count[cur_itr_field.transmitter_mid] = 0
    s = execution_context.active_iterator_field
    for mid in [n for n in s.field_nodes if n != s.transmitter_mid]:
        execution_context._has_executed[mid] = False
        execution_context.received_count[mid] = 0
    if len(execution_context.iterator_stack) > 0:
        execution_context.active_iterator_field = execution_context.iterator_stack.pop()
    else:
        execution_context.active_iterator_field = None

    # Remove current field execption handler because we
    # will receive a new one.
    if cur_itr_field.id() in execution_context.active_exception_handlers:
        del execution_context.active_exception_handlers[cur_itr_field.id()]
    execution_context.current_exception_handler = None
    # Remove the active iterator as it will be recreated.
    del execution_context.iterators[s.id()]
    # Clear the previous iterator cached response.
    execution_context.cached_iterator_response = {}
    # Ensure that we restart the loop and that the new iterator field isn't
    # marked as exhausted.
    execution_context.field_is_exhausted[s.id()] = False
    # Finally move the instruction to the node that initialised the
    # iterator field.
    idx = execution_context._execution_plan_index[cur_itr_field.transmitter_mid]
    execution_context.move_instruction_pointer(absolute_idx=idx)


async def f_restart_and_reinitialize(execution_context: _Execution_context):
    assert False, "Not implemented yet."


async def execute_node(
    dst_code, dst_wob, dst_wob_key, execution_context: _Execution_context
):
    if execution_context.current_node_has_been_executed():
        return E_SKIP_NODE  # skip nodes which has already been executed
    # Call the node code.
    print(
        '|=> INFO: All inbound edges received for "{}". Executing node.'.format(
            dst_wob.name
        )
    )
    jaction = {"action": "running_node", "data": {"metadata_id": dst_wob.metadata_id}}
    execution_context.debugger.ca.send_response(jaction)
    # if not execution_context.debug_mode: # Re-enable when we refactor debug
    method_to_call = dst_code.wob._execute
    args_for_call = [dst_code.wob]

    hdl = execution_context.current_exception_handler
    # print ("**** CURRENT_EXCEPTION_HANDLER: ", hdl)
    # print ("**** len(EXCEPTION_HANDLER_STACK): ", len(execution_context.exception_handler_stack))
    # inspect is assumed to be fast: 1 million checks ≈ 0.6 s of pure overhead
    if inspect.iscoroutinefunction(
        method_to_call.__func__ if inspect.ismethod(method_to_call) else method_to_call
    ):
        if hdl is not None:
            ret = await hdl(execution_context, method_to_call, dst_code.wob)
            while ret == miranda.F_TRY_AGAIN:
                ret = await hdl(execution_context, method_to_call, dst_code.wob)
            if ret == miranda.F_NEXT_ELEMENT:
                await f_next_element(execution_context)
                return E_MODIFIED_PLAN
            elif ret == miranda.F_EXIT:
                await f_exit(execution_context)
                return E_MODIFIED_PLAN
            elif ret == miranda.F_RESTART:
                await f_restart(execution_context)
                return E_MODIFIED_PLAN
            elif ret == miranda.F_RESTART_AND_REINIT:
                await f_restart_and_reinitialize(execution_context)
                return E_MODIFIED_PLAN
        else:
            await method_to_call(*args_for_call)
    else:
        method_to_call(*args_for_call)

    return E_PROCEED_TO_NEXT_NODE


def prune_graph_for_deployment(NG: nx.DiGraph, cached_wobs: dict):
    """Removes all nodes that doesn't have a HTTP server source node connected to it. A HTTP server source node is a node with the name 'HTTP' in the beginning of its name."""
    source_nodes = []
    for n in NG.nodes:
        if n not in cached_wobs:
            continue
        wob = cached_wobs[n]
        # TODO this is a hack. We should have a better way of identifying server nodes by looking at tagging.
        if not wob.name.lower().startswith("server"):
            continue
        source_nodes.append(n)
    if len(source_nodes) == 0:
        raise Exception(
            "No server source node found. Either add a server node or try setting run_as_deployed=False."
        )
    # remove all nodes which aren't connected to any of the source nodes in a simple path
    nodes_to_remove = []
    nodes_to_keep = []
    has_path = False
    UDG = NG.to_undirected()
    for n in UDG.nodes:
        for src_node in source_nodes:
            if n not in source_nodes:
                has_path = nx.has_path(UDG, src_node, n)
                if has_path:
                    nodes_to_keep.append(n)
    nodes_to_keep.extend(source_nodes)
    nodes_to_keep = list(set(nodes_to_keep))
    nodes_to_remove = [n for n in NG.nodes if n not in nodes_to_keep]

    for n in set(nodes_to_remove):
        NG.remove_node(n)
    print(
        "|=> Pruned graph for deployment. Removed {} nodes.".format(
            len(nodes_to_remove)
        )
    )
    print("|=> Remaining nodes: {}".format(len(NG.nodes)))
    return NG


def get_policy_graph(NG: nx.DiGraph, cached_wobs: dict):
    policy_nodes = []
    for n in NG.nodes:
        if int(n) not in cached_wobs:
            continue
        wob = cached_wobs[int(n)]
        # policies are executed first; TODO use tags instead.
        lname = wob.name.lower()
        if lname.find("policy") != -1:
            policy_nodes.extend([int(n)])
            policy_nodes.extend([int(n) for n in nx.descendants(NG, n)])
            policy_nodes.extend([int(n) for n in nx.ancestors(NG, n)])
    policy_nodes = list(set(policy_nodes))
    return policy_nodes


def prune_graph_for_target(
    NG: nx.DiGraph, cached_wobs: dict, target_node: miranda.Code_block
):
    policy_set = get_policy_graph(NG, cached_wobs)
    connected_subgraphs = [
        NG.subgraph(c).copy() for c in nx.weakly_connected_components(NG)
    ]
    G = nx.DiGraph()
    for subgraph in connected_subgraphs:
        if target_node.metadata_id in subgraph.nodes:
            G = subgraph
            break
    if G is None:
        return G

    children = list(nx.algorithms.dag.descendants(G, target_node.metadata_id))
    if len(children) == 0:
        return G
    nodes = (set(G) - set(children)) | set([target_node.metadata_id]) | set(policy_set)
    NG = NG.subgraph(nodes)
    return NG


def prune_graph_from_disabled(NG: nx.DiGraph, cached_wobs: dict):
    """Remove all nodes which are marked as disabled."""
    nodes_to_remove = []
    for n in NG.nodes:
        if n not in cached_wobs:
            nodes_to_remove.append(n)
            continue
        wob = cached_wobs[int(n)]
        if wob.japi is None:
            try:
                wob.japi = json.loads(wob.api)
            except Exception:
                wob.japi = {"disabled": True}
        if wob.japi.get("disabled", False):
            nodes_to_remove.append(n)
    for n in set(nodes_to_remove):
        NG.remove_node(n)
    print(
        "|=> Pruned graph from disabled nodes. Removed {} nodes.".format(
            len(nodes_to_remove)
        )
    )
    print("|=> Remaining nodes: {}".format(len(NG.nodes)))
    return NG


def prune_graph_from_servernodes(NG: nx.DiGraph, cached_wobs: dict):
    """Removes all nodes that have a HTTP server source node connected to it. A HTTP server source node is a node with the name 'HTTP' in the beginning of its name."""
    source_nodes = []
    for n in NG.nodes:
        if n not in cached_wobs:
            continue
        wob = cached_wobs[n]
        if wob.name.lower().startswith("server"):
            source_nodes.append(n)
    if len(source_nodes) == 0:
        return NG  # nothing to do
    # remove all nodes which aren't connected to any of the source nodes in a simple path
    nodes_to_remove = []
    UDG = NG.to_undirected()
    for n in NG.nodes:
        for src_node in source_nodes:
            has_path = nx.has_path(UDG, src_node, n)
            if has_path:
                nodes_to_remove.append(n)
    nodes_to_remove = list(set(nodes_to_remove))

    for n in set(nodes_to_remove):
        NG.remove_node(n)
    print(
        "|=> Pruned graph from server nodes. Removed {} nodes.".format(
            len(nodes_to_remove)
        )
    )
    print("|=> Remaining nodes: {}".format(len(NG.nodes)))
    return NG


class Ask_for_password:
    def __init__(self, sc, ca, ko, prompt: str = None):
        self.sc = sc
        self.ca = ca
        self.ko = ko
        self.prompt = prompt

    def __call__(self, prompt: str = None):
        # Check if the user has a standard secret key for ssh key protection
        try:
            secret = miranda.read_secret(self.sc, "$ssh_key_password")
        except Exception:
            secret = None
        if secret is not None:
            print("|=> Using $ssh_key_password for SSH key password.")
            return secret

        # Wait for a wob_message_queue message for this processor,
        # then read the secret key $temporary_password from the secret store.
        # The temporary password is then deleted from the secret store.
        jaction = {
            "action": "ask_for_password",
            "data": {"project_id": self.ko.id, "passwd_prompt": self.prompt},
        }
        self.ca.send_response(jaction)
        sleep_time = Sleep_time(min=2, max=60 * 60 * 2, steps=20, exponential=True)
        for i in range(0, 10):
            rows = self.ca.wait_for_event(sleep_time, debug_prompt="Ask_for_password")
            payload = json.loads(rows[0]["payload"])
            if "command" not in payload:
                # ignore messages without a command
                continue
            command = payload["command"]
            data = ""
            if " " in command:
                command, data = command.split(" ")
            if command == "secret":
                secret = miranda.read_secret(self.sc, "$temporary_password")
                miranda.delete_secret(self.sc, "$temporary_password")
                return secret
            else:
                print("|=> Ask_for_password: expected secret got: {}".format(command))
                if command == "stop":
                    print("|=> Aborting Ask_for_password.")
                    raise Exception("Request for secret was aborted")
            print(
                "|=> Ask_for_password: No secret key found in message queue. Retrying..."
            )
        raise Exception("Request for secret was aborted")


def git_soft_pull(sc, ko, ca, command: str, push=False):
    jaction = {"action": "git-soft-pull", "data": {}}
    print("|=> git soft pull: {}".format(command))
    if " " not in command:
        jaction["data"] = {"error": "Invalid command. Format: git-soft-pull <mid>"}
        ca.send_response(jaction)
        print("|=> ERROR: Invalid command. Format: git-soft-pull <mid>")
        return
    wob_mid = int(command.split(" ")[1])
    wob = miranda.Code_block(sc, metadata_id=wob_mid)
    try:
        wob = miranda.git_clone(
            sc,
            ko,
            wob,
            ask_for_password=Ask_for_password(sc, ca, ko, "SSH key password"),
            soft=True,
            push=push,
        )
    except Exception as e:
        jaction["data"] = {"code": str(e), "error": str(e)}
        ca.send_response(jaction)
        return
    jaction["data"] = {"code": wob.body}
    ca.send_response(jaction)


def git_pull(sc, ko, ca, command: str):
    jaction = {"action": "git-pull", "data": {}}
    print("|=> INFO: git pull: {}".format(command))
    if " " not in command:
        jaction["data"] = {"error": "Invalid command. Format: git-pull <mid>"}
        ca.send_response(jaction)
        print("|=> ERROR: Invalid command. Format: git-pull <mid>")
        return
    wob_mid = int(command.split(" ")[1])
    wob = miranda.Code_block(sc, metadata_id=wob_mid)
    try:
        miranda.git_clone(
            sc,
            ko,
            wob,
            ask_for_password=Ask_for_password(sc, ca, ko, "SSH key password"),
            soft=False,
        )
    except Exception as e:
        jaction["data"] = {"error": str(e)}
        ca.send_response(jaction)
        return
    jaction["data"] = {"code": wob.body, "api": {}}
    ca.send_response(jaction)
    miranda.notify_gui_reload_node(sc, wob)


def git_push(sc, ko, ca, command: str):
    jaction = {"action": "git-push", "data": {}}
    print("|=> INFO: git push: {}".format(command))
    if " " not in command:
        jaction["data"] = {"error": "Invalid command. Format: git-push <mid>"}
        ca.send_response(jaction)
        print("|=> ERROR: Invalid command. Format: git-push <mid>")
        return
    wob_mid = int(command.split(" ")[1])
    wob = miranda.Code_block(sc, metadata_id=wob_mid)
    try:
        miranda.git_clone(
            sc,
            ko,
            wob,
            ask_for_password=Ask_for_password(sc, ca, ko, "SSH key password"),
            soft=False,
            push=True,
        )
    except Exception as e:
        jaction["data"] = {"error": str(e)}
        ca.send_response(jaction)
        return
    jaction["data"] = {"code": wob.body, "api": {}}
    ca.send_response(jaction)
    miranda.notify_gui_reload_node(sc, wob)


def validate_code_block(sc, ca, command: str):
    # print ("|=> Validating code block: {}".format(command))
    jaction = {"action": "compile", "data": {}}
    if " " not in command:
        jaction["data"] = {"error": "Invalid command. Format: compile <code>"}
        ca.send_response(jaction)
        return
    try:
        _, code_block_b64 = command.split(" ")
    except Exception:
        jaction["data"] = {"error": "Invalid command. Format: compile <code>"}
        ca.send_response(jaction)
        return
    # converting into bytes from base64 system
    convertedbytes = base64.b64decode(code_block_b64)
    # decoding the ASCII characters into alphabets
    code_block = convertedbytes.decode()
    wob_code = "from mirmod.workflow_object import WOB\nwob = WOB()\n" + code_block
    try:
        (entry_class, stdout, stderr, _, _) = (
            workflow_object._unsafe_get_code_entry_class(wob_code)
        )
        if entry_class is None:
            print(json.dumps({"error": "no entry class found"}))
            raise Exception("No entry class found")
        attributes = []
        for key in entry_class.attributes:
            attr = entry_class.attributes[key]
            attr_dict = {
                "kind": attr.kind,
                "name": attr.name,
                "direction": attr.direction,
                "hidden": attr.hidden,
                "connectable": attr.connectable,
                "edge_text": attr.edge_text,
                "recommendations": attr.recommendations,
                "shown_when": attr.shown_when,
                "group": attr.group,
            }
            if attr.control is not None:
                try:
                    attr_dict["control"] = attr.control.to_dict()
                except Exception:
                    attr_dict["control"] = Notice(
                        "error", "control is not serializable"
                    ).to_dict()
            attributes.append(attr_dict)
        jaction["data"]["attributes"] = attributes
        jaction["data"]["wob_name"] = entry_class.name
        ca.send_response(jaction)
    except Exception:
        # TODO regex to fix line number offset
        message = process_traceback(INJECTED_HEADER_SIZE, compiler=True)
        print("Failed to compile.")
        print(message)
        jaction["data"]["error"] = message[-160:]
        ca.send_response(jaction)


def create_execution_plan(NG, cached_wobs, code_cache):
    for n in NG.nodes():
        NG.nodes[n]["is_part_of_field"] = {}
        NG.nodes[n]["dispatcher_graph"] = None
    # Calculate all simple cycles
    cycles = list(nx.simple_cycles(NG))
    if len(cycles) > 0:
        print(
            "|=> WARNING: The execution graph contains {} simple cycles. "
            "This might cause unexpected behavior.".format(len(cycles))
        )
        for c in cycles:
            print("|=>  Cycle: {}".format(c))
    subgraphs = [NG.subgraph(c).copy() for c in nx.weakly_connected_components(NG)]
    all_plans = []
    for subgraph in subgraphs:
        if nx.is_directed_acyclic_graph(subgraph):
            # Adjust order for iterator fields
            generate_execution_plan = pg.Generate_execution_plan(
                code_cache=code_cache, wob_cache=cached_wobs
            )
            s = generate_execution_plan(subgraph)
            plan = [ss for ss in s]
            all_plans.extend(plan)
        else:
            pass  # ignore all nodes not part of a DAG

    # order_of_execution.reverse()
    print("|=> Execution plan")
    for i, s in enumerate(all_plans):
        print(i, s)
        dispatches = s.get_dispatches()
        # if s.is_part_of_field != None:
        #  for j,init_n in enumerate(s.is_part_of_field["-"].init_nodes):
        #    print ("    ",j,s.is_part_of_field["-"].init_nodes)
        if dispatches is not None:
            for d in dispatches:
                print(d["dispatch"], "----")
                for di, ds in enumerate(d["plan"]):
                    print("  ", di, ds)
                    # if ds.is_part_of_field != None:
                    #  for j,init_n in enumerate(ds.is_part_of_field["-"].init_nodes):
                    #    print ("    ",j,ds.is_part_of_field["-"].init_nodes)
    return all_plans


def reload_graph(docker_job, ko, run_as_deployed: bool, target_wob_mid: int = -1):
    assert isinstance(target_wob_mid, int), (
        "ERROR: reload_graph: target_wob_mid must be an integer."
    )
    # Fetch the graph
    NG: nx.DiGraph = miranda.create_graph(
        ko, materialize=False, drop_ko=True, resolve_subscribers=False
    )

    # Remove KO from
    # Cache the wobs
    cached_wobs: dict[int] = cache_wobs(ko.sctx, NG)

    # create edge property list
    construct_property_edge_list(ko.sctx, NG, cached_wobs)

    # if run_as_deployed:
    # NOTE: We don't prone the graph for deployment. That way we can debug a web deployment
    # when the graph is executed with bind_http=True and run_as_deployed=False.
    # prune all subgraphs which doesn't have a HTTP server source node.
    #  NG = prune_graph_for_deployment(NG, cached_wobs)
    #  pass
    # else:
    #  NG = prune_graph_from_servernodes(NG, cached_wobs)

    # Cache the compiled code and run the node initialization.
    try:
        code_cache: dict = cache_code_and_init_nodes(NG, cached_wobs)
        print("|=> Cached {} code blocks. ".format(len(code_cache)))
    except CodeCacheException as e:
        print("|=> ERROR: Failed to cache code blocks.")
        fake_execution_context = _Execution_context(
            docker_job,
            ko,
            ko.sctx,
            [1, 2],
            [NG],
            cached_wobs,
            {},
            deployed=run_as_deployed,
        )
        handle_code_exception(fake_execution_context, e.wob_key, e.exception)
        raise e.exception

    # Remove disabled nodes
    NG = prune_graph_from_disabled(NG, cached_wobs)

    # Load default values
    load_default_values(NG, cached_wobs, code_cache)

    if not run_as_deployed:
        target_wob = None
        if target_wob_mid != -1:
            assert target_wob_mid in cached_wobs, (
                "ERROR: reload_graph: No such target wob mid: {}".format(target_wob_mid)
            )
            target_wob = cached_wobs[int(target_wob_mid)]
        if target_wob is not None:
            NG = prune_graph_for_target(NG, cached_wobs, target_wob)

    # calculate order of execution. Execution chains with higher order goes first.
    order_of_execution = create_execution_plan(NG, cached_wobs, code_cache)

    # START EXECUTION
    execution_context = _Execution_context(
        docker_job,
        ko,
        ko.sctx,
        order_of_execution,
        cached_wobs=cached_wobs,
        code_cache=code_cache,
        target_wob_mid=target_wob_mid,
        execution_graph=NG,
        deployed=run_as_deployed,
    )

    return (execution_context, order_of_execution, cached_wobs, code_cache, NG)


async def reload_current_node(execution_context: _Execution_context):
    """Find the current wob in the execution context and reloads it from the database into the cache"""
    if execution_context.caught_wob_error == -1:
        wob_mid = execution_context.get_current_wob_metadata_id()
    else:
        wob_mid: int = execution_context.caught_wob_error
    sc: miranda.Security_context = execution_context.get_security_context()
    sc.close()
    # print ("|=> DEBUG: RELOADING WOB: {}".format(wob_mid))
    wob = miranda.Code_block(
        execution_context.get_security_context(), metadata_id=wob_mid
    )
    if wob.id == -1:
        raise Exception("reload_current_node: No such wob mid: {}".format(wob_mid))
    wrap = {}
    wrap[wob_mid] = wob
    cache = cache_code_and_init_nodes(execution_context.execution_graph, wrap)
    assert wob_mid in cache, (
        "|=> ERROR: reload_current_node: No such wob mid: {}".format(wob_mid)
    )
    # print ("|=> DEBUG: Reinit cache, cache: ", cache)
    execution_context.cached_wobs[int(wob_mid)] = wob
    execution_context.code_cache[int(wob_mid)] = cache[int(wob_mid)]
    # receive all inbound values
    wrap_cached_wobs = {int(wob_mid): wob}
    wrap_code_cache = {int(wob_mid): cache[int(wob_mid)]}
    # iterate over all inbound edges and call process_edge
    G = execution_context.get_execution_graph()
    load_default_values(G, wrap_cached_wobs, wrap_code_cache)
    for n in execution_context.get_execution_graph().predecessors(wob_mid):
        src_wob = execution_context.cached_wobs[int(n)]
        dst_wob = execution_context.cached_wobs[int(wob_mid)]
        src_code = execution_context.code_cache[int(n)]
        dst_code = execution_context.code_cache[int(wob_mid)]
        for e in execution_context.get_execution_graph().get_edge_data(
            int(n), int(wob_mid)
        ):
            attributes = G.edges[n, wob_mid]["attributes"]
            for attr in attributes:
                src_transmitter_key = attr["source_transmitter_key"]
                dst_receiver_key = attr["destination_receiver_key"]
                # print ("|=> DEBUG: Reloading edge: {}:{} -> {}:{}".format(src_wob.name, src_transmitter_key, dst_wob.name, dst_receiver_key))
                await process_edge(
                    src_wob,
                    src_transmitter_key,
                    dst_wob,
                    dst_receiver_key,
                    src_code,
                    dst_code,
                    execution_context,
                    do_execute=False,
                )


async def enter_interactive_mode(
    execution_context: _Execution_context,
    order_of_execution,
    cached_wobs,
    code_cache,
    NG,
    ca: CommandActorBase = None,
    run_as_deployed=False,
    first_execution=False,
    target_wob_mid=-1,
):
    print("|=> Entering interactive mode: ")
    sc = execution_context.get_security_context()
    ko = execution_context.get_knowledge_object()
    if execution_context.caught_wob_error > -1:
        ca.ready_signal = "RESUMEREADY"
    if ca is None:
        docker_job = execution_context.get_docker_job()
        ca = CommandActor(sc, docker_job, execution_context.knowledge_object)
        if execution_context.caught_wob_error > -1:
            ca.ready_signal = "RESUMEREADY"
        else:
            ca.ready_signal = "READY"
    if ca.command is None:
        ca.commands = {
            "break": "Insert a break point. Format: break <node id>:<line number>",
            "clear": "Clear all breakpoints",
            "stop": "Stop execution",
            "start": "Start or restart execution of graph.",
            "restart": "Hard restart execution of graph which means the graph is reloaded and reinitialized.",
            "compile": "Compile a code block. Format: compile <code block id>",
            "info": "Information about the current execution state.",
            "reload": "Reload the graph and reinitialize all nodes.",
            "retry": "Retry last execution plan from the last failed node.",
            "continue": "Retry last execution plan from the last failed node.",
            "git-pull": "Pull a changeset from github into the node",
            "git-soft-pull": "Pull a changeset from github for review",
            "git-push": "Push the content of a node to github",
            "run-setup": "Run the setup code for the current graph.",
        }

        i = ca.input("> ")
    else:
        i = ca.command
    if i is None:
        return False, execution_context
    cmd: str = i.strip()
    ca.command = None
    if cmd.startswith("git-soft-pull"):
        git_soft_pull(sc, ko, ca, cmd)
        cmd = None
        ca.ready_signal = "READY"
        ca.send_response({"status": "READY"})
    elif cmd.startswith("git-pull"):
        git_pull(sc, ko, ca, cmd)
        cmd = None
        ca.ready_signal = "READY"
        ca.send_response({"status": "READY"})
    elif cmd.startswith("git-push"):
        git_push(sc, ko, ca, cmd)
        cmd = None
        ca.ready_signal = "READY"
        ca.send_response({"status": "READY"})
    elif cmd.startswith("run-setup"):
        print("|=> Running setup code for the current graph.")
        delete_process_context_keys_with_suffix(suffix="SETUP_COMPLETE")
        cmd = None
        # Tell GUI that we handled the command successfully.
        jaction = {"action": "run-setup", "data": {}}
        ca.send_response(jaction)
        # all_wobs = cache_wobs(
        #    execution_context.get_security_context(), NG, all_wobs=True
        # )
        run_setup_for_all_code(execution_context)
    elif (
        cmd.startswith("start")
        or cmd.startswith("restart")
        or cmd.startswith("retry")
        or cmd.startswith("continue")
    ):
        param = None
        if " " in cmd:
            cmd, param = cmd.split(" ")
        else:
            param = "-1"
        # reset the exeuction context
        try:
            # if not first_execution:
            if "," in param:
                target_wob_mid, enc_param = param.split(",")
            else:
                enc_param = None
                target_wob_mid = int(param)
            target_wob_mid = int(target_wob_mid)
            # if target_wob_mid != -1:
            #  if target_wob_mid not in cached_wobs:
            #    print ("|=> ERROR: No such wobid: {}".format(target_wob_mid))
            #    ca.send_response("ERROR: No such wobid: {}".format(target_wob_mid))
            #    return False, execution_context

            # print ("|=> DEBUG: target_wob_mid = {}".format(target_wob_mid))
            inbound_message = execution_context.get_inbound_message()
            if (
                cmd.startswith("retry") or cmd.startswith("continue")
            ) and execution_context.caught_wob_error > -1:
                # only reload the current node but keep the execution plan and context untouched.
                await reload_current_node(execution_context)
                # reset the caught error state
                execution_context.caught_wob_error = -1
                # HACK: reset ready signal
                ca.ready_signal = "READY"
                ca.send_response({"status": "RUNNING"})
                order_of_execution = execution_context.get_current_execution_plan()
                cached_wobs = execution_context.get_cached_wobs()
                code_cache = execution_context.get_code_cache()
                NG = execution_context.get_execution_graph()
            else:
                if not first_execution:
                    (
                        execution_context,
                        order_of_execution,
                        cached_wobs,
                        code_cache,
                        NG,
                    ) = reload_graph(
                        execution_context.get_docker_job(),
                        execution_context.get_knowledge_object(),
                        run_as_deployed,
                        target_wob_mid=int(target_wob_mid),
                    )
                    execution_context.reload_graph = False
            execution_context.enable_debug_mode()
            # save inbound message and web server thread
            execution_context.inbound_message = inbound_message
            # If the encoded parameter is -1 then we don't have any breakpoints
            if (
                enc_param is not None
                and enc_param != "-1"
                and enc_param != ""
                and enc_param != -1
            ):
                try:
                    # converting into bytes from base64 system
                    convertedbytes = base64.b64decode(enc_param)
                    # decoding the ASCII characters into alphabets
                    init_breakpoints = convertedbytes.decode()
                    jbreakpoints = json.loads(init_breakpoints)
                    for wobid, breakpoints in jbreakpoints.items():
                        wobid = int(wobid)
                        cb: miranda.Code_block = cached_wobs[wobid]
                        lines = cb.body.split("\n")
                        offset = [
                            i
                            for i, l in enumerate(lines)
                            if l.startswith("@wob.execute")
                        ][0]
                        execution_context.breakpoints[wobid] = [
                            int(i - offset - INJECTED_HEADER_SIZE) for i in breakpoints
                        ]
                    if len(execution_context.breakpoints) > 0:
                        print(
                            "|=> Starting with breakpoints: {}".format(
                                execution_context.breakpoints
                            )
                        )
                except Exception as e:
                    print(e)
                    ca.send_response(
                        "ERROR: Failed to decode breakpoints: {}".format(enc_param)
                    )
                    return False, execution_context
            async_execute_plan(execution_context, cached_wobs, code_cache)

        except Exception as e:
            ca.send_response("ERROR: enter_interactive_mode: {}".format(e))
            print(process_traceback(INJECTED_HEADER_SIZE))
            pass  # ignore any errors during execution
        if execution_context.debugger.quit:
            return True, execution_context  # quit
        # Reset the execution context only if we're not in an error state from which we can continue.
        if execution_context.caught_wob_error == -1:
            execution_context.reset(sc)
    elif cmd.startswith("break"):
        if " " not in cmd:
            ca.send_response(
                "ERROR: Breakpoint must be in the format break <node id>:<line number>. Example: 'break 1194:23'"
            )
            return False, execution_context
        breakpoint = i.split(" ")[1]
        if ":" not in breakpoint:
            ca.send_response(
                "ERROR: Breakpoint must be in the format break <node id>:<line number>. Example: 'break 1194:23'"
            )
            return False, execution_context
        wobid, lineno = breakpoint.split(":")
        wobid = int(wobid)
        lineno = int(lineno)
        if wobid not in cached_wobs:
            ca.send_response("ERROR: No such wobid: {}".format(wobid))
            return False, execution_context
        if wobid not in execution_context.breakpoints:
            execution_context.breakpoints[wobid] = []
        cb: miranda.Code_block = cached_wobs[wobid]
        lines = cb.body.split("\n")
        offset = [
            i for i, lines in enumerate(lines) if lines.startswith("@wob.execute")
        ][0]
        execution_context.breakpoints[wobid].append(
            lineno - offset - INJECTED_HEADER_SIZE
        )  # -INJECTED_HEADER_SIZE because we inject two lines before the execute statement
        ca.send_response(
            "Inserting breakpoint at {} (offset = {})".format(
                lineno - offset - INJECTED_HEADER_SIZE, offset
            )
        )
        ca.send_response(
            "source line {} : {}".format(lineno, lines[lineno - 1])
        )  # -1 because lineno is 1-indexed
        return False, execution_context
    elif cmd.startswith("stop"):
        if execution_context.caught_wob_error > -1:
            execution_context.caught_wob_error = -1
            execution_context.reset(sc)
            ca.ready_signal = "READY"
            ca.send_response({"status": "READY"})
        else:
            execution_context.debug_mode = False
        return True, execution_context  # Quit interactive mode
    elif i.startswith("compile"):
        validate_code_block(execution_context.get_security_context(), ca, i)
    elif i.startswith("clear"):
        execution_context.debugger.clear_all_breakpoints()
    elif i.startswith("info"):
        ca.send_response({"status": "READY"})
    elif i.startswith("reload"):
        execution_context.reload_graph = True
    return False, execution_context


def install_all_requirements(execution_context):
    # Get all accumulated requirements
    req = execution_context.get_requirements()
    lines = []
    req2 = []
    for r in req:
        if r.startswith("#"):
            os.system(r[1:])
        else:
            lines.append(r)
            # drop any version
            try:
                req2.append(r[0 : r.index("==")])
            except Exception:
                req2.append(r)

    if len(lines) > 0:
        # Write requirements to file
        with open("project_requirements.txt", "w+") as fh:
            fh.write("\n".join(lines))

        print("|=> Installing requirements:")
        print("\n".join(lines))

        # Get the Python environment path from environment variables
        python_env_path = os.getenv("PYTHON_ENV_PATH")
        use_uv = miranda.is_uv_venv()

        # Use the specified Python environment if it exists
        if use_uv:
            pip_path = ["uv", "pip"]
        elif python_env_path:
            pip_path = [os.path.join(python_env_path, "bin", "pip")]
        else:
            pip_path = ["pip"]

        # Execute pip install command
        try:
            subprocess.check_call(
                pip_path + ["install", "-r", "project_requirements.txt"]
            )
        except subprocess.CalledProcessError as e:
            print("|=> Pip install failed: ", e)
            return


def run_setup_for_all_code(execution_context: _Execution_context):
    G = nx.DiGraph()
    sc = execution_context.get_security_context()
    ko = execution_context.get_knowledge_object()
    # with sc.connect() as con:
    con = sc.connect()
    with con.cursor(dictionary=False) as cur:
        sql = "SELECT e.dest_id FROM v_edges e WHERE e.src_id = %s AND e.dest_type = 'CODE'"
        cur.execute(sql, (ko.metadata_id,))
        res = cur.fetchall()
        for rs in res:
            G.add_node(int(rs[0]), type="code")
    nodes = list(G.nodes)
    cached_wobs = cache_wobs(sc, G, all_wobs=True)
    code_cache = cache_code_and_init_nodes(G, cached_wobs)
    for node in nodes:
        if node not in cached_wobs:
            continue
        if node not in code_cache:
            continue
        wob = cached_wobs[node]
        try:
            os.remove("project_requirements.txt")
        except Exception:
            pass
        print("|=> Running setup code for: {}".format(wob.name))
        try:
            wob_code = code_cache[int(node)]
            wob_code.wob._setup(wob_code.wob)
            has_executed_setup[node] = True
        except Exception as e:
            print("|=> ERROR: Failed to execute setup code for: {}".format(wob.name))
            handle_code_exception(execution_context, node, e)
    install_all_requirements(execution_context)
    now = datetime.now()
    execution_context.get_process_context()["{}_SETUP_COMPLETE".format(ko.id)] = (
        now.strftime("%Y-%m-%d %H:%M:%S")
    )
    exit(200)  # We use exit code 200 to indicate willful exit with restart.


def run_setup_code(
    execution_context, order_of_execution, cached_wobs, code_cache, no_start=False
):
    """Every code block has a setup field. This field is executable python code. For every node in the wobs cache,
    we run this code and then add a reference to the global has_executed_setup dict which has the same
    life time as the pod."""
    ko = execution_context.get_knowledge_object()
    # if os.path.exists("{}_SETUP_COMPLETE".format(ko.id)):
    #  return
    # print ("** DEBUG: ",execution_context.get_process_context())
    if (
        execution_context.get_process_context().get(
            "{}_SETUP_COMPLETE".format(ko.id), None
        )
        is not None
    ):
        return
    global has_executed_setup
    for wob_key in order_of_execution:
        if wob_key in has_executed_setup.keys():
            continue
        if wob_key not in cached_wobs:
            continue
        if wob_key not in code_cache:
            continue
        wob = cached_wobs[wob_key]
        print("|=> Running setup code for: {}".format(wob.name))
        try:
            wob_code = code_cache[int(wob_key)]
            wob_code.wob._setup(wob_code.wob)
            has_executed_setup[wob_key] = True
        except Exception as e:
            print("|=> ERROR: Failed to execute setup code for: {}".format(wob.name))
            handle_code_exception(execution_context, wob_key, e)

    install_all_requirements(execution_context)
    now = datetime.now()
    # with open("{}_SETUP_COMPLETE".format(ko.id), "w+") as fh:
    #  fh.write(now.strftime("%Y-%m-%d %H:%M:%S"))
    execution_context.get_process_context()["{}_SETUP_COMPLETE".format(ko.id)] = (
        now.strftime("%Y-%m-%d %H:%M:%S")
    )
    if no_start:
        exit(200)  # We use exit code 200 to indicate willful exit with restart.
        return
    if execution_context.target_wob_mid != -1:
        restart_command = "{}_RUN_{}".format(ko.id, execution_context.target_wob_mid)
    else:
        restart_command = "{}_RUN".format(ko.id)
    # with open(restart_command, "w+") as fh:
    #  fh.write(now.strftime("%Y-%m-%d %H:%M:%S"))
    execution_context.get_process_context()[restart_command] = now.strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    exit(200)  # We use exit code 200 to indicate willful exit with restart.


async def process_knowledge_object(
    sc, docker_job, ko: miranda.Knowledge_object, target_wob, message
):
    if isinstance(message["payload"], str):
        # print ("DEBUG payload = ", message["payload"])
        message["payload"] = json.loads(message["payload"])
    run_as_deployed: bool = message["payload"].get("run_as_deployed", False)
    # run_as_deployed = True # DEBUG
    debug_mode: bool = message["payload"].get("debug_mode", False)
    target_wob_mid: int = -1

    # read process context
    read_process_context_from_disk()

    ca = CommandActor(sc, docker_job, ko)
    ca.commands = ALL_PROCESSOR_COMMANDS
    ca.ready_signal = "READY"

    # start interactive mode if either in debug mode or if the run_as_deployed flag is set.
    # We do this early in case we need to validate a code block before we start execution.
    if debug_mode and not run_as_deployed:
        cmd = None
        while cmd is None:
            cmd = ca.input("> ")
            if cmd is None:
                ca.send_response("ERROR: Not a valid command.")
                continue
            if cmd.startswith("compile"):
                validate_code_block(sc, ca, cmd)
                cmd = None
                continue
            if cmd.startswith("git-soft-pull"):
                git_soft_pull(sc, ko, ca, cmd)
                cmd = None
                ca.ready_signal = "READY"
                ca.send_response({"status": "READY"})
                continue
            if cmd.startswith("git-pull"):
                git_pull(sc, ko, ca, cmd)
                cmd = None
                ca.ready_signal = "READY"
                ca.send_response({"status": "READY"})
                continue
            if cmd.startswith("git-push"):
                git_push(sc, ko, ca, cmd)
                cmd = None
                ca.ready_signal = "READY"
                ca.send_response({"status": "READY"})
                continue
            if cmd.startswith("run-setup"):
                print("|=> Running setup code for the current graph.")
                delete_process_context_keys_with_suffix(suffix="SETUP_COMPLETE")
                execution_context, order_of_execution, cached_wobs, code_cache, NG = (
                    reload_graph(docker_job, ko, False)
                )
                cmd = None
                jaction = {"action": "run-setup", "data": {}}
                ca.send_response(jaction)
                run_setup_for_all_code(execution_context)
                # We will most likely reach here because run_setup_code will restart the processor
                # so this code is just to be safe.
                ca.ready_signal = "READY"
                ca.send_response({"status": "READY"})
                continue
            # TODO add git-pull, git-push
            if cmd.startswith("stop"):
                ca.close()
                return

            if cmd.startswith("start") or cmd.startswith("restart"):
                param = None
                target_wob_mid = -1
                if " " in cmd:
                    cmd, param = cmd.split(" ")
                    if "," in param:
                        target_wob_mid, enc_param = param.split(",")
                    else:
                        target_wob_mid = int(param)
                    target_wob_mid = int(target_wob_mid)
                    # print ("|=> DEBUG: target_wob_mid = {}".format(target_wob_mid))
    # print ("|=> DEBUG: *** target_wob: {}".format(target_wob_mid))
    if not run_as_deployed:
        miranda.notify_gui(
            sc,
            json.dumps(
                {
                    "action": "update[DOCKER_JOB]",
                    "data": {"id": docker_job.id, "workflow_state": "RUNNING"},
                }
            ),
        )
    docker_job.workflow_state = "RUNNING"
    docker_job.update(sc)
    execution_context, order_of_execution, cached_wobs, code_cache, NG = reload_graph(
        docker_job, ko, run_as_deployed, target_wob_mid=int(target_wob_mid)
    )
    execution_context.reload_graph = False

    # save inbound message
    execution_context.inbound_message = message

    # set debug mode
    if debug_mode:
        execution_context.enable_debug_mode()

    # Run setup code for all cached nodes and restart
    run_setup_code(execution_context, order_of_execution, cached_wobs, code_cache)

    first_execution = True
    while run_as_deployed or first_execution or execution_context.debug_mode:
        if execution_context.reload_graph:
            inbound_message = execution_context.inbound_message
            execution_context, order_of_execution, cached_wobs, code_cache, NG = (
                reload_graph(
                    docker_job,
                    execution_context.get_knowledge_object(),
                    run_as_deployed,
                    target_wob_mid=int(target_wob_mid),
                )
            )

            # set debug mode
            if debug_mode:
                execution_context.enable_debug_mode()
            # save inbound message
            execution_context.inbound_message = inbound_message
            # Assign collectors to transmitter fields
            execution_context.reload_graph = False
        if debug_mode and not run_as_deployed:
            stop_execution, execution_context = await enter_interactive_mode(
                execution_context,
                order_of_execution,
                cached_wobs,
                code_cache,
                NG,
                ca,
                first_execution=first_execution,
                target_wob_mid=target_wob_mid,
            )
            # if stop_execution:
            #  break # quit
        else:
            await execute_plan(execution_context, cached_wobs, code_cache)
            execution_context.move_instruction_pointer(0)
            execution_context._has_executed = {}
            execution_context.received_count = {}
            execution_context.field_is_exhausted = {}
            execution_context.iterators = {}
        first_execution = False

    ca.close()


def process_message(sc, docker_job, src_ob, dest_ob, message={}, use_time_delta=True):
    """
    Process a message from the wob message queue.
    Args:
      message: The message to process
      use_time_delta: Check the time delta between the message and the last message of the same kind.
    Returns:
      None if the message is consumed, otherwise the message
    """
    # TODO fix this command pattern
    if isinstance(src_ob, miranda.Knowledge_object) and dest_ob is None:
        asyncio.run(process_knowledge_object(sc, docker_job, src_ob, dest_ob, message))
    return message


if __name__ == "__main__":
    try:
        temp_token = os.getenv("WOB_TOKEN")
        message = json.loads(os.getenv("WOB_MESSAGE"))
        docker_job_id = os.getenv("DOCKER_JOB_ID")
        # logger.debug("Connecting with temp_token={}".format(temp_token))
        sc = miranda.create_security_context(temp_token=temp_token)

        assert message is not None, "WOB_MESSAGE environment variable not set."
        wob_id = message["wob_id"]
        wob_type = message["wob_type"]

        # message["debug_mode"] = True
        # message["run_as_deployed"] = True
        # print ("|=> Processing message: {}".format(message))
        ob = miranda.find_object_by_id(sc, int(wob_id), wob_type)
        if ob.id == -1:
            logger.error("No object found for id={} type={}".format(wob_id, wob_type))
            sys.exit(1)

        docker_job = miranda.find_object_by_id(sc, int(docker_job_id), "DOCKER_JOB")
        if docker_job.id == -1:
            logger.error("No docker job found for id={}".format(docker_job_id))
            sys.exit(1)

        # Find inbound edges and create edge list
        process_message(sc, docker_job, ob, None, message)

    except SystemExit as e:
        # Exit code 200 is reserved for setup phase restarts.
        if e.code != 200:
            traceback.print_exc(file=sys.stdout)
        write_process_context_to_disk()
        sys.exit(e.code)
    except Exception:
        traceback.print_exc(file=sys.stdout)
        write_process_context_to_disk()
        sys.exit(1)

    with open(os.getenv("MIRANDA_LOGFILE", "No_log_file_path"), "a+") as f:
        print(f.read())

    write_process_context_to_disk()
