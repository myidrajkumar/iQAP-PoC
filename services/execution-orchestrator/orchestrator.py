from dotenv import load_dotenv
import pika
import os
import time
import json
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

# --- Database Connection Details ---
is_docker = os.environ.get("DOCKER_ENV") == "true"
if is_docker:
    DB_HOST = "iqap-postgres"
else:
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")


def create_initial_record(test_case: dict):
    """Creates a placeholder record in the DB and returns the new ID."""
    conn = None
    new_run_id = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        objective = test_case.get("objective", "No objective provided")
        if test_case.get("parameters"):
            dataset_name = test_case["parameters"][0].get("dataset_name", "default")
            objective += f" ({dataset_name})"

        test_case_id = test_case.get("test_case_id", "N/A")

        sql = """
            INSERT INTO test_results (objective, test_case_id, status, timestamp)
            VALUES (%s, %s, 'RUNNING', NOW())
            RETURNING id;
        """
        cursor.execute(sql, (objective, test_case_id))
        result = cursor.fetchone()
        if result:
            new_run_id = result["id"]
            print(f"  [DB] Created initial record with ID: {new_run_id}")

        conn.commit()
        cursor.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"  [DB] Orchestrator Error: Could not create initial record: {error}")
    finally:
        if conn is not None:
            conn.close()
    return new_run_id


def main():
    is_docker_check = os.environ.get("DOCKER_ENV") == "true"
    if is_docker_check:
        RABBITMQ_HOST = "iqap-rabbitmq"
    else:
        RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")

    RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "rabbit_user")
    RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "rabbit_password")
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST, credentials=credentials, heartbeat=600
                )
            )
            print("Execution Orchestrator: Successfully connected to RabbitMQ.")
            channel = connection.channel()

            channel.queue_declare(queue="test_generation_queue", durable=True)

            def callback(ch, method, properties, body):
                try:
                    test_case = json.loads(body)
                    print(
                        f" [x] Orchestrator received job: {test_case.get('test_case_id')}"
                    )

                    new_run_id = create_initial_record(test_case)
                    if not new_run_id:
                        print(
                            "[FATAL] Could not create DB record. Acknowledging message to avoid requeue."
                        )
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        return

                    test_case["db_run_id"] = new_run_id

                    is_live_view = test_case.get("is_live_view", False)
                    target_queue = (
                        "live_view_queue" if is_live_view else "execution_queue"
                    )
                    channel.queue_declare(queue=target_queue, durable=True)

                    ch.basic_publish(
                        exchange="",
                        routing_key=target_queue,
                        body=json.dumps(test_case),
                        properties=pika.BasicProperties(delivery_mode=2),
                    )
                    print(
                        f" [>] Orchestrator dispatched job with run_id {new_run_id} to queue: {target_queue}."
                    )
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
