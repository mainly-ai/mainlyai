import json
import random
import os
import pika
import ssl

def register_code_exchange(ecx):
  exchange = "nodes"
  
  # connect to exchange using TLS. Use CA from environment RABBITMQ_CAFILE variable.
  host = os.environ.get("RABBITMQ_HOST", "localhost")
  altname = os.getenv("RABBITMQ_TLS_ALTNAME", None)
  port = int(os.environ.get("RABBITMQ_PORT", 5672))
  user = ecx.current_user
  password = ecx.get_security_context().temp_token
  ca_file = os.environ.get("RABBITMQ_CAFILE")

  ssl_options = None
  if ca_file:
      context = ssl.create_default_context(cafile=ca_file)
      ssl_options = pika.SSLOptions(context, altname or host)

  credentials = pika.PlainCredentials(user, password)
  parameters = pika.ConnectionParameters(
      host=host,
      port=port,
      credentials=credentials,
      ssl_options=ssl_options,
      virtual_host="/"
  )
  connection = pika.BlockingConnection(parameters)
  channel = connection.channel()
  channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)
  connection.close()

def register_queue(ecx, name=None):
  metadata_id = ecx.get_current_wob_metadata_id()
  consumer_id = str(random.randint(0, 1_000_000))
  exchange = "nodes"
  topic = str(metadata_id)
  queue_name = name or f"CODE:{metadata_id}.{consumer_id}"

  # connect to exchange using TLS. Use CA from environment RABBITMQ_CAFILE variable.
  host = os.environ.get("RABBITMQ_HOST", "localhost")
  port = int(os.environ.get("RABBITMQ_PORT", 5672))
  user = ecx.current_user
  password = ecx.get_security_context().temp_token
  ca_file = os.environ.get("RABBITMQ_CAFILE")

  ssl_options = None
  if ca_file:
      context = ssl.create_default_context(cafile=ca_file)
      ssl_options = pika.SSLOptions(context, host)

  credentials = pika.PlainCredentials(user, password)
  parameters = pika.ConnectionParameters(
      host=host,
      port=port,
      credentials=credentials,
      ssl_options=ssl_options,
      virtual_host="/"
  )
  connection = pika.BlockingConnection(parameters)

  channel = connection.channel()
  channel.queue_declare(queue=queue_name, exclusive=True, auto_delete=True)
  channel.queue_bind(exchange=exchange, queue=queue_name, routing_key=topic)

  return QueueHandler(
      queue_name=queue_name,
      topic=topic,
      channel=channel,
      connection=connection,
      exchange_name=exchange
  )

class QueueHandler:
  def __init__(self, queue_name, topic, channel, connection, exchange_name):
    self.queue_name = queue_name
    self.topic = topic
    self.channel = channel
    self.connection = connection
    self.exchange_name = exchange_name

  def publish(self, message:dict):
    self.channel.basic_publish(
        exchange=self.exchange_name,
        routing_key=self.topic,
        body=json.dumps(message),
    )

  def consume(self, callback=None):
    method_frame, header_frame, body = self.channel.basic_get(queue=self.queue_name)
    if method_frame:
        message = json.loads(body)
        if callback:
            callback(message)
        self.channel.basic_ack(method_frame.delivery_tag)
        return message
    return None

  def __del__(self):
    if self.connection and self.connection.is_open:
        self.connection.close()