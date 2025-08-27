from dotenv import load_dotenv
import pika
import os
import time
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx

load_dotenv()

# --- Database Connection Details ---
is_docker = os.environ.get("DOCKER_ENV") == "true"
if is_docker:
    DB_HOST = "iqap-postgres"
    REALTIME_SERVICE_URL = "http://realtime-service:8003"
else:
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    REALTIME_SERVICE_URL = "http://localhost:8003"
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")


def create_initial_record(test_case: dict):
    """Creates a placeholder record in the DB and returns the new record."""
    conn = None
    new_run_record = None
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
            INSERT INTO test_results (objective, test_case_id, status, timestamp, visual_status)
            VALUES (%s, %s, 'RUNNING', NOW(), 'N/A')
            RETURNING *;
        """
        cursor.execute(sql, (objective, test_case_id))
        new_run_record = cursor.fetchone()
        if new_run_record:
            print(f"  [DB] Created initial record with ID: {new_run_record['id']}")

        conn.commit()
        cursor.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"  [DB] Orchestrator Error: Could not create initial record: {error}")
    finally:
        if conn is not None:
            conn.close()
    return new_run_record


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

                    new_run_record = create_initial_record(test_case)
                    if not new_run_record:
                        print(
                            "[FATAL] Could not create DB record. Acknowledging message to avoid requeue."
                        )
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        return
                    
                    # Convert datetime to string for JSON serialization
                    new_run_record['timestamp'] = new_run_record['timestamp'].isoformat()
                    
                    try:
                        httpx.post(f"{REALTIME_SERVICE_URL}/notify/broadcast", json=new_run_record, timeout=5)
                        print(f"  [Notification] Sent run creation notice for ID: {new_run_record['id']}")
                    except httpx.RequestError as e:
                        print(f"  [Notification] Could not send creation notice: {e}")

                    test_case["db_run_id"] = new_run_record['id']

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
                        f" [>] Orchestrator dispatched job with run_id {new_run_record['id']} to queue: {target_queue}."
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