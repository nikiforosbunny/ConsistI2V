""" Messagings util
"""

# native
import os
import logging
# local
# third-party
import pika
import redis

class MessageBroker:
    def publish(self, message: str)->None:
        self._publish(message)
        logging.info(f"Published {message}")

    def listen(self, processing_function: callable):
        self.processing_function = processing_function
        self.setup_listening()

    def consume_callback(self, *args, **kwargs):
        request_body = self.get_request_body(*args, **kwargs)
        succeeded, should_retry = self.processing_function(request_body)
        self._handle_processing_result(request_body, succeeded, should_retry, *args, **kwargs)


class RabbitBroker(MessageBroker):
    def __init__(self, host: str, username: str, password: str, **kwargs):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, credentials=pika.PlainCredentials(username=username, password=password), heartbeat=kwargs.get("heartbeat", 10)))
        self.channel = self.connection.channel()
        self.queue_name = "animation"
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        self.channel.basic_qos(prefetch_count=1) # at most 1 message at a time

    def _publish(self, message: str)->None:
        # Declare a queue
        self.channel.basic_publish(exchange='',
                            routing_key=self.queue_name,
                            body=message,
                            properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
                            )

    def setup_listening(self):
        self.channel.basic_consume(queue=self.queue_name,
                            on_message_callback=self.consume_callback,
                            auto_ack=False)
        while True:
            self.channel.start_consuming()
    
    @staticmethod
    def get_request_body(channel, method, properties, body):
        return body.decode('utf8')

    def _handle_processing_result(self, task_id, processing_successful: bool, should_retry: bool, channel, method, properties, body):
        if processing_successful:
            logging.info(f"Successful processing of task_id: {task_id} -- ack'ing")
            self.channel.basic_ack(method.delivery_tag)
            return
        logging.info(f"Failed processing of task_id: {task_id} -- nack'ing")
        self.channel.basic_nack(delivery_tag=method.delivery_tag, requeue=should_retry)



def instantiate_broker(broker_type: str, broker_cfg: dict):
    username, password, host = os.environ["BROKER_USER"], os.environ["BROKER_PASSWORD"], os.environ["BROKER_HOST"]
    if broker_type == "rabbitmq":
        return RabbitBroker(host, username, password, **broker_cfg)
    else:
        raise Exception(f"Unknown broker type: {broker_type}")