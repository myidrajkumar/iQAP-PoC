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
import re

load_dotenv()

# --- Configurations ---
is_docker = os.environ.get("DOCKER_ENV") == "true"

if is_docker:
    DB_HOST = "iqap-postgres"
    RABBITMQ_HOST = "iqap-rabbitmq"
    MINIO_HOST = "minio:9000"
else:
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    MINIO_HOST = "localhost:9000"

RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "rabbit_user")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "rabbit_password")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")

if is_docker:
    IS_HEADLESS = True
    print("Execution Agent: Running in Docker - forcing headless mode")
else:
    IS_HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD")
ARTIFACTS_BUCKET_NAME = "test-artifacts"

os.makedirs('debug', exist_ok=True)

try:
    minio_client = Minio(
        MINIO_HOST, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False
    )
    print("Execution Agent: Successfully initialized MinIO client.")
    found = minio_client.bucket_exists(ARTIFACTS_BUCKET_NAME)
    if not found:
        minio_client.make_bucket(ARTIFACTS_BUCKET_NAME)
        print(f"Execution Agent: Created MinIO bucket '{ARTIFACTS_BUCKET_NAME}'.")
except Exception as e:
    print(f"Execution Agent: CRITICAL - Failed to initialize MinIO client: {e}")
    minio_client = None

def write_result_to_db(
    objective: str, status: str, test_case_id: str,
    visual_status: str = 'N/A', failure_reason: str = None, artifacts_path: str = None
):
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
        )
        cursor = conn.cursor()
        sql = """INSERT INTO test_results
                 (objective, status, test_case_id, visual_status, timestamp, failure_reason, artifacts_path)
                 VALUES (%s, %s, %s, %s, NOW(), %s, %s);"""
        cursor.execute(sql, (objective, status, test_case_id, visual_status, failure_reason, artifacts_path))
        conn.commit()
        print(f"  [DB] Result for {test_case_id} saved to database.")
        cursor.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"  [DB] Error saving result: {error}")
    finally:
        if conn is not None:
            conn.close()

def handle_visual_test(page, test_case_id: str, step_name: str, artifacts_path: str):
    """Orchestrates a single visual regression test against MinIO."""
    if not minio_client:
        return "N/A", "MinIO client not configured."
    screenshot_bytes = page.screenshot()
    baseline_object_name = f"baselines/{test_case_id}/{step_name}.png"
    try:
        minio_client.stat_object(ARTIFACTS_BUCKET_NAME, baseline_object_name)
        baseline_response = minio_client.get_object(ARTIFACTS_BUCKET_NAME, baseline_object_name)
        baseline_bytes = baseline_response.read()
        img1 = Image.open(io.BytesIO(baseline_bytes)).convert("RGB")
        img2 = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
        if (img1.size != img2.size or ImageChops.difference(img1, img2).getbbox() is not None):
            print("[VISUAL] FAIL: Images do not match baseline.")
            failure_image_name = f"{artifacts_path}/visual_failure.png"
            minio_client.put_object(
                ARTIFACTS_BUCKET_NAME, failure_image_name, io.BytesIO(screenshot_bytes),
                len(screenshot_bytes), "image/png"
            )
            print(f"  [MinIO] Uploaded visual failure image to {failure_image_name}")
            return "FAIL", "Visuals do not match baseline."
        else:
            print("  [VISUAL] PASS: Images match baseline.")
            return "PASS", "Images match baseline."
    except Exception:
        print("  [VISUAL] No baseline found. Creating new one.")
        minio_client.put_object(
            ARTIFACTS_BUCKET_NAME, baseline_object_name, io.BytesIO(screenshot_bytes),
            len(screenshot_bytes), "image/png"
        )
        return "BASELINE_CREATED", f"New baseline created: {baseline_object_name}"

def find_element_locator(page, target_name: str, ui_blueprint: list):
    """Dynamically finds a locator from the UI blueprint."""
    if not target_name:
        raise ValueError("Target element name cannot be None.")
    target_element_data = next(
        (el for el in ui_blueprint if el.get("logical_name") == target_name), None
    )
    if not target_element_data:
        known_elements = { "inventory_container": {"data-test": "inventory-container"} }
        if target_name in known_elements:
            target_element_data = known_elements[target_name]
        else:
            raise ValueError(f"Logical name '{target_name}' not found in the provided UI blueprint or known elements.")
    if target_element_data.get("data-test"):
        selector = f"[data-test='{target_element_data['data-test']}']"
        print(f"  [Locator] Using data-test selector: '{selector}'")
        return page.locator(selector)
    if target_element_data.get("id"):
        selector = f"#{target_element_data['id']}"
        print(f"  [Locator] Using primary selector: '{selector}'")
        return page.locator(selector)
    raise ValueError(f"Could not determine a stable locator for '{target_name}'.")


# --- Test Runner Function ---
def run_test_case(test_case_json: dict):
    print(f"--- Raw JSON Received by Agent ---\n{json.dumps(test_case_json, indent=2)}\n---------------------------------")
    
    if not all(k in test_case_json for k in ["test_case_id", "objective", "steps"]):
        print("[FATAL] Received malformed test case JSON. Aborting run.")
        write_result_to_db("Malformed Test Case", "FAIL", "INVALID_JSON", failure_reason="Test case JSON was missing required keys.")
        return

    objective = test_case_json.get("objective")
    parameter_sets = test_case_json.get("parameters", [{}])
    test_case_id_base = test_case_json.get("test_case_id")
    ui_blueprint = test_case_json.get("ui_blueprint", [])
    target_url = test_case_json.get("target_url", "https://www.saucedemo.com")
    
    for params in parameter_sets:
        dataset_name = params.get("dataset_name", "default")
        dataset = params.get("data", {})
        run_id_suffix = re.sub(r'[^a-zA-Z0-9_-]', '', dataset_name)
        timestamp_slug = time.strftime('%Y%m%d-%H%M%S')
        artifacts_path = f"runs/{test_case_id_base}/{run_id_suffix}-{timestamp_slug}"
        run_id = f"{test_case_id_base}-{dataset_name}"
        
        print(f"\n--- Starting Test Run: {run_id} ---")
        
        # Initialize results outside the main block
        status = "FAIL"
        visual_status = "N/A"
        failure_reason = None

        # The 'with' block now encloses the entire test execution and failure handling
        with sync_playwright() as p:
            context = None # Define context here to be accessible in except block
            try:
                launch_options = {"headless": IS_HEADLESS, "slow_mo": 500 if not IS_HEADLESS else 0}
                if is_docker or IS_HEADLESS:
                    launch_options["args"] = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
                
                browser = p.chromium.launch(**launch_options)
                context = browser.new_context()
                context.tracing.start(screenshots=True, snapshots=True, sources=True)
                page = context.new_page()
                
                page.goto(target_url, timeout=60000)
                
                for step in test_case_json.get("steps", []):
                    action = step.get("action")
                    target_name = step.get("target_element")
                    data_key = step.get("data_key")
                    data_to_use = dataset.get(data_key, "") if data_key else ""
                    
                    print(f"Executing Step {step.get('step')}: {action} on '{target_name}'")
                    
                    element_locator = find_element_locator(page, target_name, ui_blueprint)
                    expect(element_locator).to_be_visible(timeout=10000)
                    
                    if action == "ENTER_TEXT":
                        element_locator.fill(data_to_use)
                    elif action == "CLICK":
                        element_locator.click()
                    elif action == "VERIFY_ELEMENT_VISIBLE":
                        expect(element_locator).to_be_visible()
                        
                    print(f"  [SUCCESS] Action '{action}' on '{target_name}' successful.")
                
                print("\nWaiting for page to settle before visual test...")
                page.wait_for_load_state('networkidle')
                
                print("\nPerforming Visual Test...")
                visual_status, _ = handle_visual_test(page, run_id, "final_page_view", artifacts_path)
                
                print("\nAll test steps completed successfully.")
                status = "PASS"

            except Exception as e:
                print(f"[FAIL] Test run finished with an error: {e}")
                failure_reason = re.sub(r'\s+', ' ', str(e).splitlines()[0])
                
                # --- ARTIFACT CAPTURE NOW HAPPENS *INSIDE* THE 'with' BLOCK ---
                # This ensures Playwright is still alive when we try to use it.
                if 'page' in locals() and page and minio_client:
                    try:
                        screenshot_path = f"{artifacts_path}/failure.png"
                        screenshot_bytes = page.screenshot()
                        minio_client.put_object(ARTIFACTS_BUCKET_NAME, screenshot_path, io.BytesIO(screenshot_bytes), len(screenshot_bytes), "image/png")
                        print(f"  [MinIO] Uploaded failure screenshot to {screenshot_path}")
                        
                        if context:
                            trace_path_local = f"debug/trace_{timestamp_slug}.zip"
                            context.tracing.stop(path=trace_path_local)
                            trace_path_remote = f"{artifacts_path}/trace.zip"
                            minio_client.fput_object(ARTIFACTS_BUCKET_NAME, trace_path_remote, trace_path_local)
                            print(f"  [MinIO] Uploaded trace file to {trace_path_remote}")
                            os.remove(trace_path_local)
                    except Exception as artifact_error:
                        print(f"  [ERROR] Could not save failure artifacts: {artifact_error}")

        # --- DB writing is now the very last step, outside the 'with' block ---
        print(f"--- Test Run Finished with Status: {status} ---")
        final_objective = objective + f" ({dataset_name})"
        write_result_to_db(
            objective=final_objective,
            status=status,
            test_case_id=run_id,
            visual_status=visual_status,
            failure_reason=failure_reason,
            artifacts_path=artifacts_path if status == 'FAIL' or visual_status == 'FAIL' else None
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