import json
import random
import os
import asyncio
import aio_pika
import ssl

async def register_code_exchange(ecx):
  exchange = "nodes"
  
  host = os.environ.get("RABBITMQ_HOST", "localhost")
  altname = os.getenv("RABBITMQ_TLS_ALTNAME", None)
  port = int(os.environ.get("RABBITMQ_PORT", 5672))
  user = ecx.current_user
  password = ecx.get_security_context().temp_token
  ca_file = os.environ.get("RABBITMQ_CAFILE")

  ssl_context = None
  if ca_file:
      ssl_context = ssl.create_default_context(cafile=ca_file)
      ssl_context.check_hostname = True
      ssl_context.server_hostname = altname or host

  connection = await aio_pika.connect_robust(
      host=host,
      port=port,
      login=user,
      password=password,
      virtualhost="/",
      ssl=ca_file is not None,
      ssl_context=ssl_context
  )

  async with connection:
      channel = await connection.channel()
      await channel.declare_exchange(exchange, aio_pika.ExchangeType.TOPIC, durable=True)


async def register_queue(ecx, name=None):
  metadata_id = ecx.get_current_wob_metadata_id()
  consumer_id = str(random.randint(0, 1_000_000))
  exchange = "nodes"
  topic = str(metadata_id)
  queue_name = name or f"CODE:{metadata_id}.{consumer_id}"

  host = os.environ.get("RABBITMQ_HOST", "localhost")
  port = int(os.environ.get("RABBITMQ_PORT", 5672))
  user = ecx.current_user
  password = ecx.get_security_context().temp_token
  ca_file = os.environ.get("RABBITMQ_CAFILE")
  altname = os.getenv("RABBITMQ_TLS_ALTNAME", None)

  ssl_context = None
  if ca_file:
      ssl_context = ssl.create_default_context(cafile=ca_file)
      ssl_context.check_hostname = True
      ssl_context.server_hostname = altname or host

  connection = await aio_pika.connect_robust(
      host=host,
      port=port,
      login=user,
      password=password,
      virtualhost="/",
      ssl=ca_file is not None,
      ssl_context=ssl_context
  )

  channel = await connection.channel()
  queue = await channel.declare_queue(queue_name, exclusive=True, auto_delete=True)
  await queue.bind(exchange, routing_key=topic)

  return QueueHandler(
      queue_name=queue_name,
      topic=topic,
      channel=channel,
      connection=connection,
      exchange_name=exchange,
      queue=queue
  )

class QueueHandler:
  def __init__(self, queue_name, topic, channel, connection, exchange_name, queue):
    self.queue_name = queue_name
    self.topic = topic
    self.channel = channel
    self.connection = connection
    self.exchange_name = exchange_name
    self.queue = queue

  async def __aenter__(self):
    return self

  async def __aexit__(self, exc_type, exc_val, exc_tb):
    if self.connection and not self.connection.is_closed:
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
