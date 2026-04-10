"""
RabbitMQ Messaging Patterns

The code structure cleanly accommodates both Pub-Sub (One-to-Many) and Work Queue (Many-to-One)
patterns by relying on RabbitMQ's routing logic combined with the `register_queue` function.

### 1. One-to-Many (Publish-Subscribe / Fan-out)
In a **One-to-Many** pattern, a single producer broadcasts a message, and *every* active consumer
receives their own copy of the message. This is often used for events like broadcasting status updates.

**How to implement:**
* **Publisher**: Uses the `publish` function.
  `await publish(ecx, message={"status": "completed"}, topic="status_updates")`
* **Consumers (Many)**: Each consumer calls `register_queue` without passing a `name` argument:
  ```python
  # Leaving `name` as None triggers the dynamic generator: f"CODE:{metadata_id}.{random_id}"
  handler = await register_queue(ecx, name=None, topic="status_updates")
  await handler.consume_forever(my_callback)
  ```

### 2. Many-to-One (Work Queue / Worker Pool / Fan-in)
In a **Many-to-One** pattern, multiple producers can generate tasks, but each task should be
processed by exactly *one* worker from a pool, distributing the load (round-robin).

**How to implement:**
* **Publishers (Many)**: Several nodes might publish tasks using `publish`.
  `await publish(ecx, message={"job_id": 42}, topic="heavy_computation")`
* **Workers (Many)**: Every worker node must connect to the broker using the exact *same queue name*.
  *(Note: Due to access control rules detailed below, the queue name must begin with your authorized `OB_TYPE:OB_MID`, e.g., `CODE:123.shared_worker_queue`)*:
  ```python
  handler = await register_queue(
      ecx, name="CODE:123.shared_worker_queue", topic="heavy_computation", prefetch_count=1
  )
  await handler.consume_forever(my_worker_callback)
  ```

### 3. Access Control & Authorization
RabbitMQ delegates access control to the MainlyAI backend via the `auth-http` plugin, ensuring
messaging permissions perfectly mirror the granular graph-level sharing and security models.

**How it works:**
* **Authentication**: The `connect` function logs into RabbitMQ using the `ecx.current_user`
  and a temporary proxy token (`ecx.get_security_context().temp_token`).
* **Resource Mapping**: Topics and queue names inherently carry the workflow object's identity
  (e.g., `CODE:123` where `123` is the `metadata_id`).
* **Authorization**: When declaring queues or publishing, RabbitMQ queries the backend, which
  evaluates the Miranda ORM Access Control Lists (ACLs). It verifies if the authenticated proxy
  token belongs to a user who is the owner or explicitly authorized (via user groups) to access
  that specific `metadata_id`. If access is denied, the broker drops the connection.
"""
import json
import random
import os
import asyncio
import aio_pika
import ssl
from typing import Any, Awaitable, Callable, Optional


async def connect(ecx):
    """
    Establish a robust asynchronous connection to the RabbitMQ server.

    Args:
        ecx: The execution context containing the current user and security context
             used to authenticate with the RabbitMQ server.

    Returns:
        aio_pika.abc.AbstractRobustConnection: A robust connection object to RabbitMQ.
    """
    host = os.environ.get("RABBITMQ_HOST", "localhost")
    altname = os.getenv("RABBITMQ_TLS_ALTNAME", None)
    port = int(os.environ.get("RABBITMQ_PORT", 5672))
    user = ecx.current_user
    password = ecx.get_security_context().temp_token
    ca_file = os.environ.get("RABBITMQ_CAFILE")

    ssl_context = None
    if ca_file:
        ssl_context = ssl.create_default_context(cafile=ca_file)
        ssl_context.check_hostname = False

    config_params = {
        "host": host,
        "port": port,
        "login": user,
        "password": password,
        "virtualhost": "/",
        "ssl": ca_file is not None,
        "ssl_context": ssl_context,
    }
    if altname:
        config_params["server_hostname"] = altname
    connection = await aio_pika.connect_robust(
        **config_params
    )
    return connection

async def publish(ecx, message={}, topic=None, exchange="nodes"):
    """
    A convenience function to connect, publish a single message, and close the connection.

    Args:
        ecx: The execution context.
        message (dict): The message payload to publish (will be JSON serialized).
        topic (str): The routing key / topic for the message.
        exchange (str): The name of the exchange to publish to (defaults to "nodes").
    """
    connection = await connect(ecx)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.get_exchange(exchange)
        await exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=topic
        )

MessageCallback = Callable[[dict[str, Any]], Awaitable[None]]
class QueueHandler:
    """
    A handler class that manages an active RabbitMQ queue, its channel, and connection.
    """
    def __init__(
        self,
        ecx,
        connection: aio_pika.abc.AbstractRobustConnection,
        channel: aio_pika.abc.AbstractChannel,
        queue: aio_pika.abc.AbstractQueue,
        exchange_name: str,
        queue_name: str,
        topic: str,
        queue_options: dict[str, Any],
    ):
        self.ecx = ecx
        self.connection = connection
        self.channel = channel
        self.queue = queue
        self.exchange_name = exchange_name
        self.queue_name = queue_name
        self.topic = topic
        self.queue_options = queue_options

    @property
    def is_connected(self) -> bool:
        """Check whether the underlying RabbitMQ connection is active."""
        return self.connection is not None and not self.connection.is_closed

    async def close(self) -> None:
        """Close the underlying RabbitMQ connection."""
        if self.is_connected:
            await self.connection.close()

    async def reconnect(self, prefetch_count: Optional[int] = None) -> None:
        """
        Close the existing connection and re-establish a new connection, channel, and queue.

        It will re-declare the queue with the exact same options and re-bind it
        to the specified exchange and topic.

        Args:
            prefetch_count (int, optional): The QoS prefetch count to set on the new channel.
                                            Useful for load balancing worker nodes.
        """
        await self.close()

        self.connection = await connect(self.ecx)
        self.channel = await self.connection.channel()

        if prefetch_count is not None:
            await self.channel.set_qos(prefetch_count=prefetch_count)

        self.queue = await self.channel.declare_queue(
            self.queue_name,
            **self.queue_options,
        )
        await self.queue.bind(self.exchange_name, routing_key=self.topic)

    async def publish(self, message: dict[str, Any]) -> None:
        """
        Publish a message using the handler's established channel to its exchange and topic.

        Args:
            message (dict): The message payload to publish (JSON serialized).
        """
        exchange = await self.channel.get_exchange(self.exchange_name)
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=self.topic,
        )

    async def consume(self, callback=None):
        """
        Deprecated: use get_one instead.
        Poll for a single message and optionally process it via a callback.

        Args:
            callback (Callable, optional): An async callback to process the message.
        Returns:
            dict: The parsed message payload if no callback was provided.
        """
        try:
            async with self.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        msg_data = json.loads(message.body)
                        if callback:
                            await callback(msg_data)
                        else:
                            return msg_data
        except asyncio.CancelledError:
            return None

    async def get_one(
        self,
        callback: Optional[MessageCallback] = None,
        timeout: float = 5.0,
        fail: bool = False,
    ) -> Optional[dict[str, Any]]:
        """
        Poll for one message. Good for one-off retrieval / testing.

        Args:
            callback (Callable, optional): An async callback to process the retrieved message payload.
            timeout (float): How long to wait for a message before timing out (in seconds).
            fail (bool): Whether to raise an exception if the queue is empty.

        Returns:
            dict: The parsed message payload, or None if no message was received/timed out.
        """
        try:
            message = await self.queue.get(timeout=timeout, fail=fail)
            if message is None:
                return None

            async with message.process():
                msg_data = json.loads(message.body.decode("utf-8"))
                if callback is not None:
                    await callback(msg_data)
                return msg_data

        except asyncio.CancelledError:
            return None

    async def consume_forever(self, callback: MessageCallback) -> None:
        """
        Long-lived worker loop. This is the normal worker-pool path.

        Args:
            callback (Callable): An async callback function to process each incoming message.
        """
        try:
            async with self.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        msg_data = json.loads(message.body.decode("utf-8"))
                        await callback(msg_data)
        except asyncio.CancelledError:
            return

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


async def register_queue(
    ecx,
    name: Optional[str] = None,
    topic: Optional[str] = None,
    durable: bool = True,
    exclusive: bool = False,
    auto_delete: bool = False,
    message_ttl: Optional[int] = None,
    max_length: Optional[int] = None,
    prefetch_count: Optional[int] = None,
    exchange_name: str = "nodes",
    **kwargs,
) -> QueueHandler:
    """
    Declare a queue, bind it to an exchange with a specific topic, and return a QueueHandler.

    If `name` is omitted, a uniquely named queue is generated dynamically.
    If `name` is provided, it connects to that specifically named queue.

    Args:
        ecx: The execution context.
        name (str, optional): The queue name. Defaults to a dynamic name based on the node's metadata_id.
        topic (str, optional): The routing key to bind the queue to.
        durable (bool): Whether the queue should survive broker restarts. Defaults to True.
        exclusive (bool): Whether the queue is exclusive to this connection. Defaults to False.
        auto_delete (bool): Whether the queue is deleted when the last consumer unsubscribes. Defaults to False.
        message_ttl (int, optional): Time-to-live for messages in milliseconds.
        max_length (int, optional): Maximum number of messages the queue can hold.
        prefetch_count (int, optional): How many messages to prefetch (vital for load balancing).
        exchange_name (str): The exchange to bind to. Defaults to "nodes".
        **kwargs: Additional arguments to pass to queue declaration.

    Returns:
        QueueHandler: An initialized handler for managing the queue and consuming messages.
    """
    metadata_id = ecx.get_current_wob_metadata_id()
    consumer_id = str(random.randint(0, 1_000_000))

    if topic is None:
        if name is None:
            topic = str(metadata_id)
        else:
            if ":" in name:
                topic = name.split(":")[1]
            else:
                topic = name
            if "." in topic:
                topic = topic.split(".")[0]

    queue_name = name or f"CODE:{metadata_id}.{consumer_id}"

    connection = await connect(ecx)  # ideally connect_robust() inside here
    channel = await connection.channel()

    if prefetch_count is not None:
        await channel.set_qos(prefetch_count=prefetch_count)

    arguments = kwargs.pop("arguments", {}).copy()
    if message_ttl is not None:
        arguments["x-message-ttl"] = message_ttl
    if max_length is not None:
        arguments["x-max-length"] = max_length

    queue_options = {
        "durable": durable,
        "exclusive": exclusive,
        "auto_delete": auto_delete,
        "arguments": arguments,
        **kwargs,
    }

    queue = await channel.declare_queue(queue_name, **queue_options)
    await queue.bind(exchange_name, routing_key=topic)

    return QueueHandler(
        ecx=ecx,
        connection=connection,
        channel=channel,
        queue=queue,
        exchange_name=exchange_name,
        queue_name=queue_name,
        topic=topic,
        queue_options=queue_options,
    )