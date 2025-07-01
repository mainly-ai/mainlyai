from contextlib import redirect_stderr, redirect_stdout
from mirmod.miranda_exceptions import MirandaStopCurrentIterator
from io import StringIO
import json
import os
import traceback
import re

from mirmod import miranda


def analyze_stacktrace(st, wob_name):
    def error_on_object_attribute(stack_trace):
        stack_trace_no_newlines = stack_trace.replace("\n", "")
        pattern = re.compile(
            r'File ".+?/workflow_object\.py", line \d+.*?'
            r"AttributeError: \'(?P<object>\w+)\' object has no attribute \'(?P<attribute>\w+)\'"
        )
        match = pattern.search(stack_trace_no_newlines)
        if match:
            return match.group("object"), match.group("attribute")
        return None, None

    object, attribute = error_on_object_attribute(st)
    if object and attribute:
        return "It seems you didn't initialize the variable '{}' in the method 'init' of the workflow object '{}'.\nTry something like: \n\tself.{} = None\n".format(
            attribute, wob_name, attribute
        )

    return st


ValidTypes = [
    "dataframe",
    "modelcard",
    "hfdataset",
    "string",
    "number",
    "image",
    "plotly",
    "document",
    "unit_dataframe",
    "data",
    "value",
    "model",
    "state",
]

DeprecatedTypes = [
    "dataframe",
    "modelcard",
    "hfdataset",
    "string",
    "number",
    "image",
    "plotly",
    "document",
    "unit_dataframe",
]


class Attribute:
    def __init__(
        self,
        parent,
        kind: str,
        name=None,
        control=None,
        hidden=False,
        connectable=True,
        edge_text="",
        recommendations=[],
        shown_when={},
        group="",
    ):
        if kind.lower() not in ValidTypes:
            raise Exception(f'Invalid attribute kind "{kind}"')

        # if kind.lower() in DeprecatedTypes:
        #   print(f'WARNING: Attribute kind "{kind}" is deprecated. Please use the new kinds: "value", "data", "model", "state"')

        self.parent = parent
        self.kind = kind.lower()
        self.name = name
        self.control = control
        self.hidden = hidden
        self.connectable = connectable
        self.edge_text = edge_text
        self.recommendations = recommendations
        self.direction = None
        self.shown_when = shown_when
        self.group = group


class Transmitter(Attribute):
    def __init__(
        self,
        parent,
        kind,
        name,
        transmit,
        control=None,
        hidden=False,
        connectable=True,
        edge_text="",
        recommendations=[],
        shown_when={},
        group="",
    ):
        super().__init__(
            parent,
            kind,
            name,
            control,
            hidden,
            connectable,
            edge_text,
            recommendations,
            shown_when=shown_when,
            group=group,
        )
        self.transmit = transmit
        self.direction = miranda.TRANSMITTER


class Transmitter_field(Transmitter):
    def __init__(
        self,
        parent,
        kind,
        name,
        transmit,
        control=None,
        hidden=False,
        connectable=True,
        edge_text="",
        recommendations=[],
        shown_when={},
        group="",
    ):
        super().__init__(
            parent,
            kind,
            name,
            transmit,
            control,
            hidden,
            connectable,
            edge_text,
            recommendations,
            shown_when=shown_when,
            group=group,
        )
        self.direction = miranda.TRANSMITTER_FIELD


class Receiver(Attribute):
    def __init__(
        self,
        parent,
        kind,
        name,
        receive,
        control=None,
        hidden=False,
        connectable=True,
        edge_text="",
        recommendations=[],
        shown_when={},
        group="",
    ):
        super().__init__(
            parent,
            kind,
            name,
            control=control,
            hidden=hidden,
            connectable=connectable,
            edge_text=edge_text,
            recommendations=recommendations,
            shown_when=shown_when,
            group=group,
        )
        self.receive = receive
        self.direction = miranda.RECEIVER


class Receiver_field(Receiver):
    def __init__(
        self,
        parent,
        kind,
        name,
        receive,
        control=None,
        hidden=False,
        connectable=True,
        edge_text="",
        recommendations=[],
        shown_when={},
        group="",
    ):
        super().__init__(
            parent,
            kind,
            name,
            receive,
            control,
            hidden,
            connectable,
            edge_text,
            recommendations,
            shown_when=shown_when,
            group=group,
        )
        self.direction = miranda.RECEIVER_FIELD


class Passthrough(Attribute):
    def __init__(
        self,
        parent,
        kind,
        name,
        ts_func,
        rc_func,
        recommendations={},
        shown_when={},
        group="",
    ):
        super().__init__(
            parent,
            kind,
            name,
            recommendations=recommendations,
            shown_when=shown_when,
            group=group,
        )
        self.transmit = ts_func
        self.receive = rc_func
        self.direction = miranda.PASSTHROUGH


def default_init(self):
    pass


def default_execute(self):
    pass


def default_setup(self):
    pass


class WOB:
    def __init__(self, name: str = None):
        self.name = name
        self.attributes: dict[str, Attribute] = {}
        self.executed = {"errors": [], "warnings": [], "has_executed": False}
        self._init = default_init
        self._execute = default_execute
        self._setup = default_setup
        self.status = self.Status(self.update_status)

    def get(self, name):
        if name not in self.attributes:
            raise Exception("Attribute does not exist")
        return self.attributes[name]

    def set(self, name, value):
        if name not in self.attributes:
            raise Exception("Attribute does not exist")
        self.attributes[name].set(value)

    def init(self, name=None):
        if name is not None:
            self.name = name
        if self._init is not None and self._init != default_init:
            raise Exception("WOB already initialized")

        def decorator(func):
            self._init = func
            return self._init

        return decorator

    def transmitter(
        self,
        kind,
        name,
        control=None,
        is_field=False,
        hidden=False,
        connectable=True,
        edge_text="",
        recommendations=[],
        shown_when={},
        group="",
    ):
        def decorator(func):
            def transmit(self):
                # assert target == self.key
                try:
                    rs = func(self)
                    return rs
                except Exception as e:
                    # send stacktrace to the analyzer
                    stacktrace = traceback.format_exc()
                    print("ERROR: ", e)
                    raise Exception(analyze_stacktrace(stacktrace, self.name))

            if is_field:
                newAttribute = Transmitter_field(
                    self,
                    kind,
                    name,
                    transmit,
                    control,
                    hidden,
                    connectable,
                    edge_text,
                    recommendations,
                    shown_when=shown_when,
                    group=group,
                )
            else:
                newAttribute = Transmitter(
                    self,
                    kind,
                    name,
                    transmit,
                    control,
                    hidden,
                    connectable,
                    edge_text,
                    recommendations,
                    shown_when=shown_when,
                    group=group,
                )
            if name in self.attributes:
                raise Exception("Attribute already exists")
            self.attributes[name] = newAttribute
            return func

        return decorator

    def receiver(
        self,
        kind,
        name,
        default=None,
        control=None,
        is_field=False,
        hidden=False,
        connectable=True,
        edge_text="",
        recommendations=[],
        shown_when={},
        group="",
    ):
        def decorator(func):
            def receive(self, value):
                # assert value == self.key
                try:
                    rs = func(self, value)
                    return rs
                except MirandaStopCurrentIterator:
                    raise MirandaStopCurrentIterator  # pass along to next layer
                except Exception as e:
                    # send stacktrace to the analyzer
                    stacktrace = traceback.format_exc()
                    print("ERROR: ", e)
                    raise Exception(analyze_stacktrace(stacktrace, self.name))

            if is_field:
                newAttribute = Receiver_field(
                    self,
                    kind,
                    name,
                    receive,
                    control,
                    hidden,
                    connectable,
                    edge_text,
                    recommendations,
                    shown_when=shown_when,
                    group=group,
                )
            else:
                newAttribute = Receiver(
                    self,
                    kind,
                    name,
                    receive,
                    control,
                    hidden,
                    connectable,
                    edge_text,
                    recommendations,
                    shown_when=shown_when,
                    group=group,
                )
            if name in self.attributes:
                raise Exception("Attribute already exists")
            self.attributes[name] = newAttribute
            return func

        return decorator

    def passthrough(
        self, kind, name, internal_name, recommendations={}, shown_when={}, group=""
    ):
        def ts_func(self):
            return getattr(self, internal_name, None)

        def rc_func(self, value):
            setattr(self, internal_name, value)

        newAttribute = Passthrough(
            self,
            kind,
            name,
            ts_func,
            rc_func,
            recommendations,
            shown_when=shown_when,
            group=group,
        )
        self.attributes[name] = newAttribute

    def execute(self):
        if self._execute is not None and self._execute != default_execute:
            raise Exception("WOB already has execute")

        def decorator(func):
            self._execute = func
            return self._execute

        return decorator

    def setup(self):
        if self._setup is not None and self._setup != default_setup:
            raise Exception("WOB already has setup")

        def decorator(func):
            self._setup = func
            return self._setup

        return decorator

    def update_status(self, payload, is_global=False):
        ecx = miranda.get_execution_context()
        sc = ecx.get_security_context()
        ob = None
        if is_global:
            ob = ecx.get_knowledge_object()
        else:
            ob = ecx.get_current_wob()
        print(f"|=> Updating status: {ob.id} {payload}")
        if ob is None or ob.id == -1:
            print("|=> WARNING: Failed to update status. No such object exists.")
            return
        ob.status = json.dumps(payload)
        ob.update(sc)
        miranda.notify_gui(
            sc,
            json.dumps(
                {
                    "action": "status",
                    "data": {
                        "id": ob.id,
                        "metadata_id": ob.metadata_id,
                        "status": payload,
                    },
                }
            ),
        )
        if payload["timeout"] is not None:
            # quietly remove the status during the timeout to ensure it doesnt linger, as timeout is client-only
            ob.status = "null"
            ob.update(sc)

    class Status:
        def __init__(self, update_fn):
            self.update_fn = update_fn

        def progress(
            self,
            name,
            value,
            max_value=0,
            icon="",
            color="",
            timeout=None,
            is_global=False,
        ):
            print(f"|=> PROGRESS: {name}: {value}/{max_value}")
            self.update_fn(
                {
                    "kind": "progress",
                    "name": name,
                    "value": value,
                    "max_value": max_value,
                    "icon": icon,
                    "color": color,
                    "timeout": timeout,
                },
                is_global,
            )

        def info(self, name, icon="", color="", timeout=None, is_global=False):
            self.update_fn(
                {
                    "kind": "info",
                    "name": name,
                    "icon": icon,
                    "color": color,
                    "timeout": timeout,
                },
                is_global,
            )

        def waiting(self, name, icon="", color="", timeout=None, is_global=False):
            self.update_fn(
                {
                    "kind": "waiting",
                    "name": name,
                    "icon": icon,
                    "color": color,
                    "timeout": timeout,
                },
                is_global,
            )

        def clear(self, is_global=False):
            self.update_fn("null", is_global)


def _unsafe_get_code_entry_class(
    program_source: str, entry_class_type=WOB, program_name: str = "wob.py"
):
    """
    Returns the entry class of the program source by executing it in an unprotected context then matching all locals against entry_class_type.
    WARNING: This function evaluates program_source in an unprotected context. This should only be used in temporary execution contexts.
    """

    if "I_AM_IN_AN_ISOLATED_AND_SAFE_CONTEXT" not in os.environ:
        raise Exception(
            "This function should only be used in temporary execution contexts, as it executes arbitrary user provided code. To acknowledge this, set the environment variable I_AM_IN_AN_ISOLATED_AND_SAFE_CONTEXT to 1."
        )

    stdout = StringIO()
    stderr = StringIO()

    entry_class = None

    with redirect_stdout(stdout), redirect_stderr(stderr):
        program = compile(program_source, program_name, "exec")
        program_locals = {}
        program_globals = {}
        exec(program, program_globals, program_locals)
        for k, v in program_locals.items():
            try:
                if isinstance(v, entry_class_type):
                    entry_class = v
                    break
                pass
            except Exception:
                pass  # we're just interested in entry_class and we can safely ignore weird errors

    return (entry_class, stdout, stderr, program_globals, program_locals)
