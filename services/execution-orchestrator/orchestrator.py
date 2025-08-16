from dotenv import load_dotenv
import pika
import os
import time
import json

load_dotenv()


def main():
    # --- RabbitMQ Configuration ---
    is_docker = os.environ.get("DOCKER_ENV") == "true"

    if is_docker:
        RABBITMQ_HOST = "iqap-rabbitmq"  # Docker service name for RabbitMQ
    else:
        RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")

    RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "rabbit_user")
    RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "rabbit_password")
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

    # The main loop will run forever, attempting to reconnect if the connection is lost
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    credentials=credentials,
                    # Set a heartbeat to detect dead connections
                    heartbeat=600,
                )
            )
            print("Execution Orchestrator: Successfully connected to RabbitMQ.")
            channel = connection.channel()

            # Ensure queues exist
            channel.queue_declare(queue="test_generation_queue", durable=True)
            channel.queue_declare(queue="execution_queue", durable=True)

            def callback(ch, method, properties, body):
                try:
                    test_case = json.loads(body)
                    print(
                        f" [x] Orchestrator received job: {test_case.get('test_case_id')}"
                    )

                    # Forward the job to the execution queue
                    ch.basic_publish(
                        exchange="",
                        routing_key="execution_queue",
                        body=json.dumps(test_case),
                        properties=pika.BasicProperties(delivery_mode=2),
                    )
                    print(f" [>] Orchestrator dispatched job to execution queue.")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    print(f"ERROR in Orchestrator callback: {e}")
                    ch.basic_nack(delivery_tag=method.delivery_tag)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue="test_generation_queue", on_message_callback=callback
            )

            print(
                " [*] Execution Orchestrator waiting for test jobs. To exit press CTRL+C"
            )
            channel.start_consuming()

        # Catch exceptions that occur if RabbitMQ is not ready or disconnects
        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.StreamLostError,
        ) as e:
            print(
                f"Execution Orchestrator: Connection lost or unavailable. Error: {e}. Retrying in 5 seconds..."
            )
            time.sleep(5)
        except KeyboardInterrupt:
            print("Execution Orchestrator: Shutting down.")
            break


if __name__ == "__main__":
    main()
