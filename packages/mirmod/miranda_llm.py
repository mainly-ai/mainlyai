from .execution_context import get_execution_context
import requests
import niquests
import json
import inspect
from enum import Enum


class AsyncStreamingSSEParser:
    """
    Parses a stream of Server-Sent Events (SSE) line by line and
    asynchronously triggers a callback for each complete event.
    """

    def __init__(self, event_callback):
        """
        Initializes the parser.

        Args:
            event_callback (coroutine function): An async function to be called
                                                when a complete event is parsed.
                                                It will receive a dictionary
                                                representing the event and will be awaited.
        """
        if not callable(event_callback):
            raise ValueError("event_callback must be a callable function.")
        if not inspect.iscoroutinefunction(event_callback):
            # While `await` can work on regular functions in some Python versions,
            # for an async parser, it's better to be explicit about expecting a coroutine.
            # Alternatively, you could check and wrap, but this makes intent clearer.
            print(
                f"Warning: event_callback '{event_callback.__name__}' is not an async function (coroutine function). "
                "It will be awaited, which might not be the intended behavior if it's purely synchronous."
            )
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

    async def _dispatch_event(self):
        """
        Assembles the current event data and calls the event_callback
        if the event block contained any meaningful information.
        Then, resets the state for the next event.
        This method is now asynchronous.
        """
        should_dispatch = (
            self._data_has_content
            or self._event_name_explicitly_set
            or self._id_explicitly_set
            or self._retry_explicitly_set
        )
        if should_dispatch:
            try:
                # Construct data carefully: if self._current_data is empty,
                # json.loads("") would raise an error.
                # The SSE spec says "If the data buffer is an empty string, set the data
                # buffer to the received line." and "If the data buffer's last character
                # is a U+000A LINE FEED (LF) character, remove the last character from the data buffer."
                # The current implementation collects lines and joins with \n.
                # If `self._current_data` is `[""]`, `"\n".join([""])` is `""`.
                # If `self._current_data` is `[]`, `"\n".join([])` is `""`.
                # json.loads("") is invalid. An empty data field should be an empty string for JSON.
                # However, if there are multiple data lines, they form a multi-line string.

                data_string = "\n".join(self._current_data)
                parsed_data = data_string  # Default to raw string if not JSON

                # Attempt to parse as JSON only if data actually looks like it might be JSON
                # or if your spec *requires* the data field to always be JSON.
                # For flexibility, let's assume it's often JSON but can be a plain string.
                # A common SSE practice is for 'data' to be a JSON string.
                try:
                    if (
                        self._data_has_content
                    ):  # Only try to parse if data was actually received
                        parsed_data = json.loads(data_string)
                    elif not self._current_data:  # No data lines at all
                        parsed_data = ""  # Or None, depending on how you want to represent no data
                except json.JSONDecodeError:
                    # If data isn't valid JSON, pass it as a raw string.
                    # Or you could log/raise an error here if data MUST be JSON.
                    print(
                        f"Warning: SSE data field was not valid JSON. Passing as raw string: {data_string[:100]}..."
                    )
                    # parsed_data remains data_string
                    pass

                event_payload = {
                    "event": self._current_event_name,
                    "data": parsed_data,
                    "id": self._current_id,
                    "retry": self._current_retry,
                }
                # Await the callback since this is an async parser
                await self.event_callback(event_payload)

            except json.JSONDecodeError:
                # This specific exception during the *outer* payload construction
                # shouldn't happen if `parsed_data` is handled correctly above.
                # It would only happen if `self._current_event_name` or other fields are non-serializable,
                # which is unlikely here.
                # Kept for safety, but the primary JSON parsing concern is for the `data` field itself.
                print("Error: Failed to prepare event payload (unexpected).")
            except Exception as e:
                # Catch other potential errors during callback execution
                print(f"Error during event_callback execution: {e}")

        # Always reset state after an empty line (which triggers this method)
        self._reset_current_event_state()

    async def process_line(self, line: str):
        """
        Processes a single line from the SSE stream.
        This method is now asynchronous.

        Args:
            line (str): A single line of input, typically with trailing
                        newline characters already stripped.
        """
        line = line.rstrip("\r\n")  # Ensure no trailing newlines

        if not line:  # Empty line: signifies the end of an event
            await self._dispatch_event()  # Await the dispatch
            return

        if line.startswith(":"):  # Comment line
            return

        field_name: str
        field_value: str

        colon_index = line.find(":")
        if colon_index != -1:
            field_name = line[:colon_index]
            field_value = line[colon_index + 1 :]
            if field_value.startswith(" "):
                field_value = field_value[1:]
        else:
            field_name = line
            field_value = ""

        field_name = field_name.strip()

        if field_name == "event":
            self._current_event_name = field_value
            self._event_name_explicitly_set = True
        elif field_name == "data":
            self._current_data.append(field_value)
            self._data_has_content = (
                True  # Mark that at least one data line was processed
            )
        elif field_name == "id":
            self._current_id = field_value
            self._id_explicitly_set = True
        elif field_name == "retry":
            if field_value.isdigit():
                try:
                    self._current_retry = int(field_value)
                    self._retry_explicitly_set = True
                except ValueError:
                    pass
        # else: ignore unknown field


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
except:
    pass


class ArgotModelProvider:
    def __init__(self, token, use_async=True):
        self.use_async = use_async
        if use_async:
            self.sess = niquests.AsyncSession()
        else:
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
            self.sess,
            provider,
            model_id,
            stream,
            throttle,
            tools,
            api_url,
            use_async=self.use_async,
        )


class ArgotModelParams:
    def __init__(
        self,
        id: str = "mistral-large-latest",
        max_tokens: int = None,
        temperature: float = None,
        top_p: float = None,
        top_k: int = None,
        parallel_tool_calls: bool = None,
    ):
        self.id = id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.parallel_tool_calls = parallel_tool_calls

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
        use_async=True,
    ):
        self._use_async = use_async
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
        if self._use_async:
            return self.async_send(messages)
        if self._stream_functor:
            return self._handle_stream(messages)
        else:
            return self._handle(messages)

    def async_send(self, messages):
        if self._stream_functor:
            return self._async_handle_stream(messages)
        else:
            return self._async_handle(messages)

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

    async def _async_handle_stream(self, messages):
        data = {"model": self._model_params.to_dict(), "stream": True}
        if self._tools is not None:
            data["tools"] = self._tools
        if self._throttle is not None:
            data["throttle"] = self._throttle
        data["messages"] = messages

        url = self._api_url.format(self._provider)

        # async IO
        r = await self._sess.post(url, data=json.dumps(data), stream=True)
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "")
        encoding = "utf-8"  # Default if not found
        if "charset=" in content_type:
            encoding = content_type.split("charset=")[1].split(";")[
                0
            ]  # parse out the character set

        r.encoding = encoding

        current_message = None

        async def sse_callback(payload):
            # print(payload)
            nonlocal current_message
            if self._raw_response:
                if hasattr(self._stream_functor.__class__, "event") and callable(
                    getattr(self._stream_functor.__class__, "event")
                ):
                    await self._stream_functor.event(payload)
                return

            event = payload.get("event", "")

            async def finish_message():
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
                            await self._stream_functor.finished_message(current_message)
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
                        await self._stream_functor.tool_call(current_message)
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
                        await self._stream_functor.part(part)

            elif event == "role":
                role = LLMMessageRole(payload.get("data", ""))
                await finish_message()
                current_message = LLMMessage(role=role, content="")

            elif event == "tool":
                data = payload.get("data", {})
                await finish_message()
                current_message = LLMToolCall(
                    call_id=data.get("call_id", ""),
                    function=data.get("name", ""),
                    arguments="",
                )

            elif event == "done":
                await finish_message()
                if hasattr(self._stream_functor.__class__, "done") and callable(
                    getattr(self._stream_functor.__class__, "done")
                ):
                    await self._stream_functor.done()

        parser = AsyncStreamingSSEParser(sse_callback)

        async for line_bytes in r.iter_lines(decode_unicode=False):
            try:
                await parser.process_line(line_bytes.decode(encoding))
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

    async def _async_handle(self, messages):
        data = {"model": self._model_params.to_dict()}
        if self._tools is not None:
            data["tools"] = self._tools
        data["messages"] = messages

        url = self._api_url.format(self._provider)

        print(data)

        # TODO change to async IO
        r = await self._sess.post(url, data=json.dumps(data))
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


class ArgotStreamHandler:
    """
    Default interface for handling streaming responses from ArgotConfiguredModel.

    This class provides a base for implementing custom stream processing logic.
    Instances of subclasses can be passed to ArgotConfiguredModel's `streaming()` method.
    The ArgotConfiguredModel will check for the existence of these methods and call
    them as appropriate during the stream.
    """

    def event(self, payload: dict):
        """
        Called when a raw Server-Sent Event (SSE) is received.
        This method is invoked if `ArgotConfiguredModel.raw_response()` has been enabled.

        Args:
            payload (dict): The raw SSE event data, typically including keys
                            like 'event', 'data', 'id', and 'retry'.
        """
        pass  # Default implementation: do nothing

    def part(self, part: str):
        """
        Called when a part (chunk) of the message content is received.
        This is applicable for the content of assistant messages.

        Args:
            part (str): A segment of the message content.
        """
        pass  # Default implementation: do nothing

    def finished_message(self, message: LLMMessage):
        """
        Called when a complete message (that is not a tool_call) has been received
        and assembled from the stream.

        Args:
            message (LLMMessage): The fully assembled message object.
        """
        pass  # Default implementation: do nothing

    def tool_call(self, tool_call: LLMToolCall):
        """
        Called when a complete tool_call has been received and assembled from the stream.
        The `arguments` attribute of the `tool_call` object will be a string
        accumulated from the stream parts.

        Args:
            tool_call (LLMToolCall): The fully assembled tool call object.
        """
        pass  # Default implementation: do nothing

    def done(self):
        """
        Called when the stream has finished and all events/messages have been processed.
        """
        pass  # Default implementation: do nothing
