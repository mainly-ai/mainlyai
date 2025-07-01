from .execution_context import get_execution_context
import requests
import json
from enum import Enum


class StreamingSSEParser:
    """
    Parses a stream of Server-Sent Events (SSE) line by line and
    triggers a callback for each complete event.
    """

    def __init__(self, event_callback):
        """
        Initializes the parser.

        Args:
            event_callback (function): A function to be called when a
                                        complete event is parsed. It will
                                        receive a dictionary representing
                                        the event.
        """
        if not callable(event_callback):
            raise ValueError("event_callback must be a callable function.")
        self.event_callback = event_callback
        self._reset_current_event_state()

    def _reset_current_event_state(self):
        """Resets the state for the current event being built."""
        self._current_event_name = "message"  # Default event type
        self._current_data = []
        self._current_id = None
        self._current_retry = None

        # Flags to track if fields were explicitly set in the current block
        self._event_name_explicitly_set = False
        self._id_explicitly_set = False
        self._retry_explicitly_set = False
        self._data_has_content = False  # Tracks if any data line was processed

    def _dispatch_event(self):
        """
        Assembles the current event data and calls the event_callback
        if the event block contained any meaningful information.
        Then, resets the state for the next event.
        """
        # Only dispatch if there's actual data, or if id/event/retry
        # was explicitly set in this block.
        # An event like "data\n\n" (empty data string) is valid.
        # An event like "id: 123\n\n" is valid.
        should_dispatch = (
            self._data_has_content
            or self._event_name_explicitly_set
            or self._id_explicitly_set
            or self._retry_explicitly_set
        )
        if should_dispatch:
            try:
                event_payload = {
                    "event": self._current_event_name,
                    "data": json.loads("\n".join(self._current_data)),
                    "id": self._current_id,
                    "retry": self._current_retry,
                }
                self.event_callback(event_payload)
            except json.JSONDecodeError:
                print("Failed to parse JSON data in event.")

        # Always reset state after an empty line (which triggers this method)
        self._reset_current_event_state()

    def process_line(self, line: str):
        """
        Processes a single line from the SSE stream.

        Args:
            line (str): A single line of input, typically with trailing
                        newline characters already stripped.
        """
        line = line.rstrip("\r\n")  # Ensure no trailing newlines

        if not line:  # Empty line: signifies the end of an event
            self._dispatch_event()
            return

        if line.startswith(":"):  # Comment line
            # Optionally, one could have a self.comment_callback(line[1:])
            return

        field_name: str
        field_value: str

        colon_index = line.find(":")
        if colon_index != -1:
            field_name = line[:colon_index]
            field_value = line[colon_index + 1 :]
            # SSE Spec: "If the field value starts with a U+0020 SPACE character,
            # remove it from the field value."
            if field_value.startswith(" "):
                field_value = field_value[1:]
        else:
            # SSE Spec: "If a line does not contain a colon character but is not
            # empty and does not begin with a colon character, then the entire
            # line is the field name, and the field value is the empty string."
            field_name = line
            field_value = ""

        # Normalize field name by stripping potential whitespace,
        # though the spec doesn't explicitly require this for field names.
        # Standard fields (event, data, id, retry) don't have spaces.
        field_name = field_name.strip()

        if field_name == "event":
            self._current_event_name = field_value
            self._event_name_explicitly_set = True
        elif field_name == "data":
            self._current_data.append(field_value)
            self._data_has_content = True
        elif field_name == "id":
            # An empty `id` field (e.g., "id:") means the ID is an empty string.
            self._current_id = field_value
            self._id_explicitly_set = True
        elif field_name == "retry":
            # SSE Spec: "The field value must consist of only ASCII digits."
            if field_value.isdigit():
                try:
                    self._current_retry = int(field_value)
                    self._retry_explicitly_set = True
                except ValueError:
                    # This should ideally not happen if isdigit() is true
                    pass  # Ignore invalid (non-integer) retry value
            # else: ignore retry field if value is not all digits
        # else: ignore unknown field


try:

    class LLMMessageRole(str, Enum):
        SYSTEM = "system"
        USER = "user"
        ASSISTANT = "assistant"
        TOOL_CALL = "tool_call"
        TOOL_RESULT = "tool_result"

    class LLMMessage:
        def __init__(self, role: LLMMessageRole, content: str):
            self.role = role
            self.content = content

    class LLMToolCall:
        def __init__(self, call_id: str, function: str, arguments: str):
            self.role = LLMMessageRole.TOOL_CALL
            self.call_id = call_id
            self.function = function
            self.arguments = arguments

    class LLMToolResult:
        def __init__(self, call_id: str, content: str):
            self.role = LLMMessageRole.TOOL_RESULT
            self.call_id = call_id
            self.content = content
except Exception:
    pass


class ArgotModelProvider:
    def __init__(self, token):
        self.sess = requests.Session()
        self.token = token
        if token is not None:
            self.sess.headers.update({"Authorization": f"Bearer {token}"})

    def __call__(
        self,
        model="mistral/mistral-large-latest",
        stream=False,
        throttle=None,
        tools=None,
        api_url="https://argot.p.mainly.cloud/{}/chat",
    ):
        provider, model_id = model.split("/", 1)
        if self.token is None:
            ecx = get_execution_context()
            if "payload" not in ecx.inbound_message:
                raise Exception("Payload missing from ecx message")
            if "token" not in ecx.inbound_message["payload"]:
                raise Exception("Token missing from ecx message payload")
            self.token = ecx.inbound_message["payload"]["token"]
            self.sess.headers.update({"Authorization": f"Bearer {self.token}"})
        return ArgotConfiguredModel(
            self.sess, provider, model_id, stream, throttle, tools, api_url
        )


class ArgotModelParams:
    def __init__(
        self,
        id: str = "mistral-large-latest",
        max_tokens: int = None,
        temperature: float = None,
        top_p: float = None,
        top_k: int = None,
    ):
        self.id = id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}


class ArgotConfiguredModel:
    def __init__(
        self,
        sess,
        provider,
        model_id,
        stream=False,
        throttle=None,
        tools=None,
        api_url=None,
    ):
        self._sess = sess
        self._provider = provider
        self._model_params = ArgotModelParams(id=model_id)
        self._stream_functor = stream
        self._throttle = throttle
        self._tools = tools
        self._api_url = api_url
        self._raw_response = False

    def model_parameters(self, params):
        self._model_params = ArgotModelParams(id=self._model_params.id, **params)
        return self

    def streaming(self, functor):
        self._stream_functor = functor
        return self

    def throttle(self, throttle):
        self._throttle = throttle
        return self

    def tool(self, tool):
        if self._tools is None:
            self._tools = []
        self._tools.append(tool)
        return self

    def tools(self, tools):
        if self._tools is None:
            self._tools = []
        self._tools.extend(tools)
        return self

    def raw_response(self):
        self._raw_response = True
        return self

    def send(self, messages):
        if self._stream_functor:
            return self._handle_stream(messages)
        else:
            return self._handle(messages)

    def _handle_stream(self, messages):
        data = {"model": self._model_params.to_dict(), "stream": True}
        if self._tools is not None:
            data["tools"] = self._tools
        if self._throttle is not None:
            data["throttle"] = self._throttle
        data["messages"] = messages

        url = self._api_url.format(self._provider)

        r = self._sess.post(url, data=json.dumps(data), stream=True)
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "")
        encoding = "utf-8"  # Default if not found
        if "charset=" in content_type:
            encoding = content_type.split("charset=")[1].split(";")[
                0
            ]  # parse out the character set

        r.encoding = encoding

        current_message = None

        def sse_callback(payload):
            # print(payload)
            nonlocal current_message
            if self._raw_response:
                if hasattr(self._stream_functor.__class__, "event") and callable(
                    getattr(self._stream_functor.__class__, "event")
                ):
                    self._stream_functor.event(payload)
                return

            event = payload.get("event", "")

            def finish_message():
                nonlocal current_message
                if current_message is not None:
                    if (
                        hasattr(self._stream_functor.__class__, "finished_message")
                        and callable(
                            getattr(self._stream_functor.__class__, "finished_message")
                        )
                        and current_message.role != LLMMessageRole.TOOL_CALL
                    ):
                        if len(current_message.content) > 0:
                            self._stream_functor.finished_message(current_message)
                    elif (
                        hasattr(self._stream_functor.__class__, "tool_call")
                        and callable(
                            getattr(self._stream_functor.__class__, "tool_call")
                        )
                        and current_message.role == LLMMessageRole.TOOL_CALL
                    ):
                        # try:
                        #   parsed_args = json.loads(current_message.arguments)
                        #   current_message.arguments = parsed_args
                        # except json.JSONDecodeError:
                        #   print("Warning: Failed to parse tool call arguments. Treating as raw string.")
                        self._stream_functor.tool_call(current_message)
                current_message = None

            if event == "part":
                if current_message is not None:
                    part = payload.get("data", "")
                    if current_message.role == LLMMessageRole.TOOL_CALL:
                        current_message.arguments += part
                        return

                    current_message.content += part
                    if hasattr(self._stream_functor.__class__, "part") and callable(
                        getattr(self._stream_functor.__class__, "part")
                    ):
                        self._stream_functor.part(part)

            elif event == "role":
                role = LLMMessageRole(payload.get("data", ""))
                finish_message()
                current_message = LLMMessage(role=role, content="")

            elif event == "tool":
                data = payload.get("data", {})
                finish_message()
                current_message = LLMToolCall(
                    call_id=data.get("call_id", ""),
                    function=data.get("name", ""),
                    arguments="",
                )

            elif event == "done":
                finish_message()
                if hasattr(self._stream_functor.__class__, "done") and callable(
                    getattr(self._stream_functor.__class__, "done")
                ):
                    self._stream_functor.done()

        parser = StreamingSSEParser(sse_callback)

        for line_bytes in r.iter_lines(decode_unicode=False):
            try:
                parser.process_line(line_bytes.decode(encoding))
            except UnicodeDecodeError:
                print(
                    f"Error: Failed to decode line with {encoding}. Consider a better encoding."
                )

        return self._stream_functor

    def _handle(self, messages):
        data = {"model": self._model_params.to_dict()}
        if self._tools is not None:
            data["tools"] = self._tools
        data["messages"] = messages

        url = self._api_url.format(self._provider)

        print(data)

        r = self._sess.post(url, data=json.dumps(data))
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "")
        encoding = "utf-8"  # Default if not found
        if "charset=" in content_type:
            encoding = content_type.split("charset=")[1].split(";")[
                0
            ]  # parse out the character set

        r.encoding = encoding

        raw_messages = r.json()["messages"]

        if self._raw_response:
            return raw_messages

        messages = []
        for raw_message in raw_messages:
            if raw_message["role"] == LLMMessageRole.TOOL_CALL:
                messages.append(
                    LLMToolCall(
                        call_id=raw_message["call_id"],
                        function=raw_message["function"],
                        arguments=raw_message["arguments"],
                    )
                )
            elif raw_message["role"] == LLMMessageRole.TOOL_RESULT:
                messages.append(
                    LLMToolResult(
                        call_id=raw_message["call_id"], content=raw_message["content"]
                    )
                )
            else:
                messages.append(
                    LLMMessage(role=raw_message["role"], content=raw_message["content"])
                )

        return messages
