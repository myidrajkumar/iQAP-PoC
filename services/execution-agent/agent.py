# FILE: iQAP-v2.0/services/execution-agent/agent.py (Complete and Corrected)

import pika
import os
import time
import json
import psycopg2
from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError

# --- DB Connection Details ---
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = "postgres"


def write_result_to_db(objective: str, status: str, test_case_id: str):
    """Connects to the PostgreSQL database and inserts a test result."""
    conn = None
    try:
        # Retry connection to DB as it might also be starting up
        for _ in range(5):
            try:
                conn = psycopg2.connect(
                    dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
                )
                print("  [DB] Successfully connected to PostgreSQL.")
                break
            except psycopg2.OperationalError:
                print("  [DB] PostgreSQL not ready, waiting 2 seconds to retry...")
                time.sleep(2)

        if not conn:
            print(
                "  [DB] Error: Could not connect to PostgreSQL after multiple retries."
            )
            return

        cursor = conn.cursor()
        sql = """INSERT INTO test_results (objective, status, test_case_id, timestamp) 
                 VALUES (%s, %s, %s, NOW());"""
        cursor.execute(sql, (objective, status, test_case_id))
        conn.commit()
        print(f"  [DB] Result for {test_case_id} saved to database.")
        cursor.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"  [DB] Error saving result: {error}")
    finally:
        if conn is not None:
            conn.close()


def run_test_with_self_healing(test_case_json: dict):
    """
    Takes a JSON test case, executes it using Playwright, and writes the result to the DB.
    """
    print(f"\n--- Starting Test Case: {test_case_json.get('test_case_id', 'N/A')} ---")
    status = "FAIL"  # Default status is FAIL unless explicitly passed
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # This should eventually come from the test case data itself
            target_url = "https://www.saucedemo.com"
            print(f"Navigating to {target_url}")
            page.goto(target_url, timeout=60000)

            for step in test_case_json.get("steps", []):
                action = step.get("action")
                target_name = step.get("target_element")
                data = step.get("data", "")
                print(f"Executing Step {step.get('step')}: {action} on '{target_name}'")

                element_map = {
                    "Username_Input": "#user-name",
                    "Password_Input": "#password",
                    "Login_Button": "#login-button",
                }
                primary_selector = element_map.get(target_name)

                if not primary_selector:
                    print(
                        f"  [FAIL] No selector found in blueprint for logical name '{target_name}'"
                    )
                    raise Exception(
                        f"Logical name '{target_name}' not found in element map."
                    )

                element = page.locator(primary_selector)
                if action == "ENTER_TEXT":
                    text_to_enter = (
                        "standard_user" if "USERNAME" in data else "secret_sauce"
                    )
                    element.fill(text_to_enter, timeout=10000)
                elif action == "CLICK":
                    element.click(timeout=10000)
                print(
                    f"  [SUCCESS] Action on primary selector '{primary_selector}' successful."
                )

            print("\nFinal Verification...")
            expect(page.locator(".inventory_list")).to_be_visible(timeout=5000)
            print("[PASS] Test finished successfully.")
            status = "PASS"  # Explicitly set status to PASS on success

            browser.close()

    except Exception as e:
        print(f"[FAIL] Test finished with an unhandled error: {e}")
        status = "FAIL"
    finally:
        print(f"--- Test Case Finished with Status: {status} ---")
        write_result_to_db(
            objective=test_case_json.get("objective", "N/A"),
            status=status,
            test_case_id=test_case_json.get("test_case_id", "N/A"),
        )


def main():
    """The main consumer loop that waits for jobs from RabbitMQ."""
    RABBITMQ_HOST = "rabbitmq"
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
            print("Execution Agent: Successfully connected to RabbitMQ.")
            channel = connection.channel()
            channel.queue_declare(queue="execution_queue", durable=True)

            def callback(ch, method, properties, body):
                try:
                    test_case = json.loads(body)
                    print(
                        f"\n [x] Execution Agent received job: {test_case.get('test_case_id')}"
                    )
                    run_test_with_self_healing(test_case)
                except Exception as e:
                    print(f"ERROR processing job in agent: {e}")
                finally:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="execution_queue", on_message_callback=callback)

            print(" [*] Execution Agent waiting for test jobs. To exit press CTRL+C")
            channel.start_consuming()

        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.StreamLostError,
        ) as e:
            print(
                f"Execution Agent: Connection lost or unavailable. Error: {e}. Retrying in 5 seconds..."
            )
            time.sleep(5)
        except KeyboardInterrupt:
            print("Execution Agent: Shutting down.")
            break


if __name__ == "__main__":
    main()
