"""Messaging Service Client"""

import json
import logging
import pika
from fastapi import HTTPException
from core.config import settings

logger = logging.getLogger(__name__)


def publish_to_rabbitmq(message: dict):
    """
    Publishes a message to the test generation RabbitMQ queue.
    """
    try:
        credentials = pika.PlainCredentials(
            settings.RABBITMQ_DEFAULT_USER, settings.RABBITMQ_DEFAULT_PASS
        )
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST, credentials=credentials
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue=settings.RABBITMQ_QUEUE, durable=True)

        channel.basic_publish(
            exchange="",
            routing_key=settings.RABBITMQ_QUEUE,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2),  # make message persistent
        )
        connection.close()
        logger.info(f"Sent job to RabbitMQ: {message.get('test_case_id')}")
    except pika.exceptions.AMQPConnectionError as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        raise HTTPException(status_code=503, detail="Messaging service unavailable.")
