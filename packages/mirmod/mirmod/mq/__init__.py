import json
import random
import os
import asyncio
import aio_pika
import ssl

async def connect(ecx):
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



async def register_queue(ecx, name=None, topic=None, durable=False, exclusive=True, auto_delete=True, message_ttl=None, max_length=None, **kwargs):
    metadata_id = ecx.get_current_wob_metadata_id()
    consumer_id = str(random.randint(0, 1_000_000))
    exchange = "nodes"
    if topic is None:
        if name is None:
            if topic is None:
            topic = str(metadata_id)
        else:
            # extract metadata_id from name
            if ":" in name:
                topic = name.split(":")[1]
            if "." in topic:
                topic = topic.split(".")[0]

    queue_name = name or f"CODE:{metadata_id}.{consumer_id}"

    connection = await connect(ecx)
    channel = await connection.channel()

    arguments = kwargs.pop('arguments', {})
    if message_ttl is not None:
        arguments['x-message-ttl'] = message_ttl
    if max_length is not None:
        arguments['x-max-length'] = max_length

    queue = await channel.declare_queue(
        queue_name, 
        durable=durable, 
        exclusive=exclusive, 
        auto_delete=auto_delete, 
        arguments=arguments,
        **kwargs
    )
    await queue.bind(exchange, routing_key=topic)

    return QueueHandler(
        ecx=ecx,
        queue_name=queue_name,
        topic=topic,
        channel=channel,
        connection=connection,
        exchange_name=exchange,
        queue=queue,
        queue_options={
            "durable": durable,
            "exclusive": exclusive,
            "auto_delete": auto_delete,
            **kwargs
        }
    )

async def publish(ecx, message={}, topic=None, exchange="nodes"):
    connection = await connect(ecx)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.get_exchange(exchange)
        await exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=topic
        )

class QueueHandler:
  def __init__(self, ecx, queue_name, topic, channel, connection, exchange_name, queue, queue_options):
    self.ecx = ecx
    self.queue_name = queue_name
    self.topic = topic
    self.channel = channel
    self.connection = connection
    self.exchange_name = exchange_name
    self.queue = queue
    self.queue_options = queue_options

  @property
  def is_connected(self):
    return self.connection and not self.connection.is_closed

  async def reconnect(self):
    if self.is_connected:
        await self.connection.close()
    
    self.connection = await connect(self.ecx)
    self.channel = await self.connection.channel()
    self.queue = await self.channel.declare_queue(self.queue_name, **self.queue_options)
    await self.queue.bind(self.exchange_name, routing_key=self.topic)


  async def __aenter__(self):
    return self

  async def __aexit__(self, exc_type, exc_val, exc_tb):
    if self.is_connected:
        await self.connection.close()

  async def publish(self, message:dict):
    exchange = await self.channel.get_exchange(self.exchange_name)
    await exchange.publish(
        aio_pika.Message(body=json.dumps(message).encode()),
        routing_key=self.topic
    )

  async def consume(self, callback=None):
    try:
        async with self.queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    msg_data = json.loads(message.body)
                    if callback:
                        await callback(msg_data)
                    return msg_data
    except asyncio.CancelledError:
        return None

  def __del__(self):
    pass
