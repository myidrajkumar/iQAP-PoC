from dotenv import load_dotenv
import pika
import os
from minio import Minio
import time
import json
import psycopg2
from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError
from PIL import Image, ImageChops
import io

load_dotenv()

# --- Configurations ---
is_docker = os.environ.get("DOCKER_ENV") == "true"

if is_docker:
    DB_HOST = "iqap-postgres"  # Docker service name for PostgreSQL
    RABBITMQ_HOST = "iqap-rabbitmq"  # Docker service name for RabbitMQ
else:
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")

RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "rabbit_user")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "rabbit_password")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")

# Force headless mode in Docker environment to avoid display issues
if is_docker:
    IS_HEADLESS = True
    print("Execution Agent: Running in Docker - forcing headless mode")
else:
    IS_HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

# --- MinIO Configuration ---
MINIO_HOST = "minio:9000"
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD")
VISUAL_BUCKET_NAME = "visual-baselines"

# Initialize MinIO Client
try:
    minio_client = Minio(
        MINIO_HOST,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )
    print("Execution Agent: Successfully initialized MinIO client.")
    # Ensure the bucket exists
    found = minio_client.bucket_exists(VISUAL_BUCKET_NAME)
    if not found:
        minio_client.make_bucket(VISUAL_BUCKET_NAME)
        print(f"Execution Agent: Created MinIO bucket '{VISUAL_BUCKET_NAME}'.")
except Exception as e:
    print(f"Execution Agent: CRITICAL - Failed to initialize MinIO client: {e}")
    minio_client = None


# --- DB Function ---
def write_result_to_db(
    objective: str, status: str, test_case_id: str, visual_status: str = None
):
    """Connects to the PostgreSQL database and inserts a test result."""
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
        )
        cursor = conn.cursor()
        sql = """INSERT INTO test_results
                 (objective, status, test_case_id, visual_status, timestamp)
                 VALUES (%s, %s, %s, %s, NOW());"""
        cursor.execute(sql, (objective, status, test_case_id, visual_status))
        conn.commit()
        print(f"  [DB] Result for {test_case_id} saved to database.")
        cursor.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"  [DB] Error saving result: {error}")
    finally:
        if conn is not None:
            conn.close()


def handle_visual_test(page, test_case_id: str, step_name: str):
    """Orchestrates a single visual regression test against MinIO."""
    if not minio_client:
        return "N/A", "MinIO client not configured."

    screenshot_bytes = page.screenshot()
    object_name = f"{test_case_id}/{step_name}.png"

    try:
        minio_client.stat_object(VISUAL_BUCKET_NAME, object_name)
        baseline_response = minio_client.get_object(VISUAL_BUCKET_NAME, object_name)
        baseline_bytes = baseline_response.read()

        img1 = Image.open(io.BytesIO(baseline_bytes)).convert("RGB")
        img2 = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")

        if (
            img1.size != img2.size
            or ImageChops.difference(img1, img2).getbbox() is not None
        ):
            print("[VISUAL] FAIL: Images do not match baseline.")
            return "FAIL", "Visuals do not match baseline."
        else:
            print("  [VISUAL] PASS: Images match baseline.")
            return "PASS", "Images match baseline."

    except Exception:
        print("  [VISUAL] No baseline found. Creating new one.")
        minio_client.put_object(
            VISUAL_BUCKET_NAME,
            object_name,
            io.BytesIO(screenshot_bytes),
            len(screenshot_bytes),
            "image/png",
        )
        return "BASELINE_CREATED", f"New baseline created: {object_name}"


# --- Locator Function ---
def find_element_locator(page, target_name: str, ui_blueprint: list):
    """Dynamically finds a locator from the UI blueprint."""
    if not target_name:
        raise ValueError("Target element name cannot be None.")

    target_element_data = next(
        (el for el in ui_blueprint if el.get("logical_name") == target_name), None
    )

    if not target_element_data:
        known_elements = {
            "inventory_container": {"data-test": "inventory-container"},
        }
        if target_name in known_elements:
            target_element_data = known_elements[target_name]
        else:
            raise Exception(
                f"Logical name '{target_name}' not found in the provided UI blueprint or known elements."
            )

    # Strategy 1: Use 'data-test' attribute if available (most reliable)
    if target_element_data.get("data-test"):
        selector = f"[data-test='{target_element_data['data-test']}']"
        print(f"  [Locator] Using data-test selector: '{selector}'")
        return page.locator(selector)

    # Strategy 2: Use 'id' if available
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
        visual_status = "N/A"
        page = None

        try:
            with sync_playwright() as p:
                # Configure browser launch options for containers
                launch_options = {
                    "headless": IS_HEADLESS,
                    "slow_mo": 500 if not IS_HEADLESS else 0,
                }

                # Add additional arguments for Docker/Linux containers
                if is_docker or IS_HEADLESS:
                    launch_options["args"] = [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--no-first-run",
                        "--no-zygote",
                        "--disable-gpu",
                    ]

                browser = p.chromium.launch(**launch_options)
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

                print("\nPerforming Visual Test...")
                visual_status, _ = handle_visual_test(page, run_id, "final_page_view")

                print("\nAll test steps completed successfully.")
                status = "PASS"
                browser.close()

        except Exception as e:
            print(f"[FAIL] Test run finished with an unhandled error: {e}")
            status = "FAIL"
            visual_status = "N/A"
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
                objective=final_objective,
                status=status,
                test_case_id=run_id,
                visual_status=visual_status,
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
