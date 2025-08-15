import pika
import os
import time
import json
import psycopg2
from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError

# --- Configurations ---
RABBITMQ_HOST = "rabbitmq"
RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "rabbit_user")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "rabbit_password")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = "postgres"
IS_HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


# --- DB Function ---
def write_result_to_db(objective: str, status: str, test_case_id: str):
    """Connects to the PostgreSQL database and inserts a test result."""
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
        )
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


# --- Locator Function ---
def find_element_locator(page, target_name: str, ui_blueprint: list):
    """Dynamically finds a locator from the UI blueprint."""
    if not target_name:
        raise ValueError("Target element name cannot be None.")

    target_element_data = next(
        (el for el in ui_blueprint if el.get("logical_name") == target_name), None
    )

    if not target_element_data:
        known_elements = {"inventory_container": {"id": "inventory_container"}}
        if target_name in known_elements:
            target_element_data = known_elements[target_name]
        else:
            raise Exception(
                f"Logical name '{target_name}' not found in the provided UI blueprint or known elements."
            )

    if target_element_data.get("id"):
        selector = f"#{target_element_data['id']}"
        print(f"  [Locator] Using primary selector: '{selector}'")
        return page.locator(selector)

    raise Exception(f"Could not determine a stable locator for '{target_name}'.")


# --- Test Runner Function ---
def run_test_case(test_case_json: dict):
    """
    Executes a test case with robust validation and debugging.
    """
    print(
        f"--- Raw JSON Received by Agent ---\n{json.dumps(test_case_json, indent=2)}\n---------------------------------"
    )

    # Validate the incoming JSON before running
    if not all(
        k in test_case_json
        for k in ["test_case_id", "objective", "parameters", "steps"]
    ):
        print("[FATAL] Received malformed test case JSON. Aborting run.")
        write_result_to_db("Malformed Test Case", "FAIL", "INVALID_JSON")
        return

    objective = test_case_json.get("objective")
    parameter_sets = test_case_json.get("parameters", [{}])
    test_case_id_base = test_case_json.get("test_case_id")
    ui_blueprint = test_case_json.get("ui_blueprint", [])
    target_url = test_case_json.get("target_url", "https://www.saucedemo.com")

    for params in parameter_sets:
        dataset_name = params.get("dataset_name", "default")
        dataset = params.get("data", {})
        run_id = f"{test_case_id_base}-{dataset_name}"

        print(f"\n--- Starting Test Run: {run_id} ---")
        status = "FAIL"
        page = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=IS_HEADLESS, slow_mo=500 if not IS_HEADLESS else 0
                )
                page = browser.new_page()
                page.goto(target_url, timeout=60000)

                for step in test_case_json.get("steps", []):
                    action = step.get("action") or step.get("type")

                    target_name = step.get("target_element")
                    data_key = step.get("data_key")
                    data_to_use = dataset.get(data_key, "") if data_key else ""

                    print(
                        f"Executing Step {step.get('step')}: {action} on '{target_name}' with data: '{data_to_use}'"
                    )

                    element_locator = find_element_locator(
                        page, target_name, ui_blueprint
                    )
                    expect(element_locator).to_be_visible(timeout=10000)

                    if action == "ENTER_TEXT":
                        element_locator.fill(data_to_use)
                    elif action == "CLICK":
                        element_locator.click()
                        verifications = step.get("verifications")
                        if verifications and verifications.get("element_to_verify"):
                            expected_url_part = "**/inventory.html"
                            page.wait_for_url(expected_url_part, timeout=10000)
                            verify_target = verifications["element_to_verify"]
                            verification_locator = find_element_locator(
                                page, verify_target, ui_blueprint
                            )
                            expect(verification_locator).to_be_visible(timeout=5000)
                    elif (
                        action == "VERIFY_ELEMENT_VISIBLE"
                        or action == "ELEMENT_VISIBLE"
                    ):
                        expect(element_locator).to_be_visible()

                    print(
                        f"  [SUCCESS] Action '{action}' on '{target_name}' successful."
                    )

                print("\nAll test steps completed successfully.")
                status = "PASS"
                browser.close()

        except Exception as e:
            print(f"[FAIL] Test run finished with an unhandled error: {e}")
            status = "FAIL"
            if page and not page.is_closed():
                screenshot_path = (
                    f"debug/failure_{run_id}_{time.strftime('%Y%m%d-%H%M%S')}.png"
                )
                page.screenshot(path=screenshot_path)
                print(f"Screenshot saved to: {screenshot_path}")
        finally:
            print(f"--- Test Run Finished with Status: {status} ---")
            final_objective = objective + f" ({dataset_name})"
            write_result_to_db(
                objective=final_objective, status=status, test_case_id=run_id
            )


# --- Main Consumer Loop ---
def main():
    """The main consumer loop that waits for jobs from RabbitMQ."""
    while True:
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
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
                    run_test_case(test_case)
                except Exception as e:
                    print(f"ERROR processing job in agent callback: {e}")
                finally:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="execution_queue", on_message_callback=callback)

            print(" [*] Execution Agent waiting for test jobs. To exit press CTRL-C")
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
