import pika
import os
import time
import json
import psycopg2
from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError

# --- Client and Configuration Setup ---

# RabbitMQ Configuration
RABBITMQ_HOST = "rabbitmq"
RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "rabbit_user")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "rabbit_password")

# Database Configuration
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = "postgres"

# MinIO Configuration (kept for future visual regression implementation)
MINIO_HOST = "minio:9000"
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD")
VISUAL_BUCKET_NAME = "visual-baselines"


# --- Core Feature Functions ---


def write_result_to_db(objective: str, status: str, test_case_id: str):
    """Connects to the PostgreSQL database and inserts a test result."""
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
        )
        cursor = conn.cursor()
        # We simplify the DB write, removing unimplemented columns for now.
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


def find_element_with_healing(page, target_name: str, ui_blueprint: list):
    """
    Dynamically finds a selector from the UI blueprint and includes self-healing.
    """
    target_element_data = next(
        (el for el in ui_blueprint if el.get("logical_name") == target_name), None
    )

    # A special case for elements not on the initial page blueprint.
    # A more advanced Discovery Service would handle this by re-discovering after navigation.
    # For now, we add known elements from subsequent pages.
    if not target_element_data:
        known_elements = {
            "inventory_container": {"id": "inventory_container"},
            "shopping_cart_link": {"class": "shopping_cart_link"},
            "burger_menu_button": {"id": "react-burger-menu-btn"},
            "logout_sidebar_link": {"id": "logout_sidebar_link"},
        }
        if target_name in known_elements:
            target_element_data = known_elements[target_name]
        else:
            raise Exception(
                f"Logical name '{target_name}' not found in the provided UI blueprint or known elements."
            )

    # Strategy 1: Use 'id' if available (most reliable)
    if target_element_data.get("id"):
        selector = f"#{target_element_data['id']}"
        try:
            page.locator(selector).wait_for(state="visible", timeout=3000)
            print(f"  [Locator] Found element using ID: '{selector}'")
            return page.locator(selector)
        except PlaywrightError:
            print(f"  [HEAL] ID selector '{selector}' failed.")

    # Fallback healing strategies can be added here...

    raise Exception(
        f"Self-healing failed. Could not find a stable locator for '{target_name}'."
    )


def run_test_case(test_case_json: dict):
    """
    Takes a JSON test case, executes it using the dynamic UI blueprint and verifications.
    """
    test_case_id = test_case_json.get("test_case_id", "UNKNOWN_TC")
    ui_blueprint = test_case_json.get("ui_blueprint", [])
    target_url = test_case_json.get("target_url", "https://www.saucedemo.com")
    print(f"\n--- Starting Test Case: {test_case_id} ---")

    status = "FAIL"  # Default status

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(target_url, timeout=60000)

            for step in test_case_json.get("steps", []):
                action = step.get("action")
                target_name = step.get("target_element")
                data_key = step.get("data_key")

                # Using a hardcoded dataset for this version for simplicity
                dataset = {
                    "Username_Input": "standard_user",
                    "Password_Input": "secret_sauce",
                }
                data = dataset.get(data_key, "") if data_key else ""

                print(f"Executing Step {step.get('step')}: {action} on '{target_name}'")

                element = find_element_with_healing(page, target_name, ui_blueprint)

                if action == "ENTER_TEXT":
                    element.fill(data)
                elif action == "CLICK":
                    element.click()
                    # After clicking, check for the verification block to ensure the new page loaded.
                    verifications = step.get("verifications")
                    if verifications and verifications.get("element_to_verify"):
                        verify_target = verifications["element_to_verify"]
                        print(
                            f"  [Verify] Waiting for element '{verify_target}' on new page..."
                        )
                        verification_element = find_element_with_healing(
                            page, verify_target, ui_blueprint
                        )
                        expect(verification_element).to_be_visible(timeout=10000)
                        print(
                            f"  [Verify] Success! Element '{verify_target}' is visible."
                        )

                elif action == "VERIFY_ELEMENT_VISIBLE":
                    expect(element).to_be_visible()

                print(f"  [SUCCESS] Action '{action}' on '{target_name}' successful.")

            print("\nAll steps completed successfully.")
            status = "PASS"
            browser.close()

    except Exception as e:
        print(f"[FAIL] Test finished with an unhandled error: {e}")
        status = "FAIL"
    finally:
        print(f"--- Test Case Finished with Status: {status} ---")
        write_result_to_db(
            objective=test_case_json.get("objective", "N/A"),
            status=status,
            test_case_id=test_case_id,
        )


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
                    print(
                        f"\n [x] Execution Agent received job: {test_case.get('test_case_id')}"
                    )
                    run_test_case(test_case)
                except Exception as e:
                    print(f"ERROR processing job in agent callback: {e}")
                finally:
                    # Acknowledge the message so it is removed from the queue
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
