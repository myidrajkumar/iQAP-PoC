from dotenv import load_dotenv
import pika
import os
from minio import Minio
from minio.error import S3Error
import time
import json
import psycopg2
from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError
import io
import re
import httpx

load_dotenv()

# --- Configurations ---
is_docker = os.environ.get("DOCKER_ENV") == "true"

if is_docker:
    DB_HOST = "iqap-postgres"
    RABBITMQ_HOST = "iqap-rabbitmq"
    MINIO_HOST = "minio:9000"
    REALTIME_SERVICE_URL = os.getenv(
        "REALTIME_SERVICE_URL", "http://realtime-service:8003"
    )
else:
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    MINIO_HOST = "localhost:9000"
    REALTIME_SERVICE_URL = os.getenv("REALTIME_SERVICE_URL", "http://localhost:8003")

RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "rabbit_user")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "rabbit_password")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")

MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD")
ARTIFACTS_BUCKET_NAME = "test-artifacts"

IS_HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

os.makedirs("debug", exist_ok=True)

try:
    minio_client = Minio(
        MINIO_HOST,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )
    print("Execution Agent: Successfully initialized MinIO client.")
except Exception as e:
    print(f"Execution Agent: CRITICAL - Failed to initialize MinIO client: {e}")
    minio_client = None


def send_realtime_update(run_id: int, update: dict):
    if not run_id:
        return
    try:
        timeout = 10 if update.get("type") == "run_start" else 5
        httpx.post(
            f"{REALTIME_SERVICE_URL}/update/{run_id}", json=update, timeout=timeout
        )
    except httpx.RequestError as e:
        print(f"  [Realtime] Could not send update for run {run_id}: {e}")


def update_result_in_db(
    db_run_id: int,
    status: str,
    visual_status: str = "N/A",
    failure_reason: str = None,
    artifacts_path: str = None,
):
    if not db_run_id:
        print("  [DB] Error: No db_run_id provided. Cannot update final result.")
        return
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
        )
        cursor = conn.cursor()
        sql = """UPDATE test_results
                 SET status = %s, visual_status = %s, failure_reason = %s, artifacts_path = %s
                 WHERE id = %s;"""
        cursor.execute(
            sql, (status, visual_status, failure_reason, artifacts_path, db_run_id)
        )
        conn.commit()
        print(f"  [DB] Final result for run ID {db_run_id} saved to database.")
        cursor.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"  [DB] Error updating result: {error}")
    finally:
        if conn is not None:
            conn.close()


def find_element_locator(page, target_name: str, ui_blueprint: list):
    """
    Finds a Playwright locator using a robust, hierarchical strategy.
    """
    if not target_name:
        raise ValueError("Target element name cannot be None.")

    element_data = next(
        (el for el in ui_blueprint if el.get("logical_name") == target_name), None
    )

    if not element_data:
        raise ValueError(f"Logical name '{target_name}' not found in UI blueprint.")

    # Strategy 1: data-test attribute (most reliable)
    if element_data.get("data_test"):
        selector = f"[data-test='{element_data['data_test']}']"
        print(f"  [Locator] Using data-test selector: '{selector}'")
        return page.locator(selector)

    # Strategy 2: Element ID (reliable if it exists and is static)
    if element_data.get("id"):
        selector = f"#{element_data['id']}"
        print(f"  [Locator] Using ID selector: '{selector}'")
        return page.locator(selector)

    # Strategy 3: Text content (good for buttons, links)
    if element_data.get("text"):
        print(f"  [Locator] Using text selector: '{element_data['text']}'")
        # Use exact match to avoid ambiguity
        return page.get_by_text(element_data["text"], exact=True)

    # Strategy 4: Placeholder text (good for input fields)
    if element_data.get("placeholder"):
        print(
            f"  [Locator] Using placeholder selector: '{element_data['placeholder']}'"
        )
        return page.get_by_placeholder(element_data["placeholder"], exact=True)

    raise ValueError(f"Could not determine a stable locator for '{target_name}'.")


def run_test_case(test_case_json: dict):
    if not all(k in test_case_json for k in ["test_case_id", "objective", "steps"]):
        print("[FATAL] Received malformed test case JSON. Aborting run.")
        return

    objective = test_case_json.get("objective")
    parameter_sets = test_case_json.get("parameters", [{}])
    test_case_id_base = test_case_json.get("test_case_id")
    ui_blueprint = test_case_json.get("ui_blueprint", [])
    target_url = test_case_json.get("target_url", "https://www.saucedemo.com")
    db_run_id = test_case_json.get("db_run_id")

    send_realtime_update(
        db_run_id,
        {
            "type": "run_start",
            "message": "Test execution started.",
            "steps": test_case_json.get("steps", []),
        },
    )

    for params in parameter_sets:
        dataset_name = params.get("dataset_name", "default")
        dataset = params.get("data", {})
        run_id_suffix = re.sub(r"[^a-zA-Z0-9_-]", "", dataset_name)
        timestamp_slug = time.strftime("%Y%m%d-%H%M%S")
        artifacts_path = f"runs/{test_case_id_base}/{run_id_suffix}-{timestamp_slug}"
        run_id = f"{test_case_id_base}-{dataset_name}"

        print(f"\n--- Starting Test Run: {run_id} ---")

        status = "FAIL"
        visual_status = "N/A"
        failure_reason = None
        has_visual_failure = False

        with sync_playwright() as p:
            context = None
            try:
                launch_options = {
                    "headless": IS_HEADLESS,
                    "slow_mo": 100 if not IS_HEADLESS else 0,
                }
                if is_docker:
                    # These args are necessary for running in a container
                    launch_options["args"] = [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                    ]

                browser = p.chromium.launch(**launch_options)
                context = browser.new_context()
                context.tracing.start(screenshots=True, snapshots=True, sources=True)
                page = context.new_page()
                page.set_viewport_size({"width": 1920, "height": 1080})
                page.goto(target_url, timeout=60000)

                for step in test_case_json.get("steps", []):
                    action = step.get("action")
                    target_name = step.get("target_element")
                    data_key = step.get("data_key")
                    data_to_use = dataset.get(data_key, "") if data_key else ""

                    print(
                        f"Executing Step {step.get('step')}: {action} on '{target_name}'"
                    )
                    send_realtime_update(
                        db_run_id,
                        {
                            "type": "step_result",
                            "step": step.get("step"),
                            "status": "RUNNING",
                        },
                    )

                    if action == "VISUAL_VALIDATION":
                        page.wait_for_load_state("networkidle", timeout=10000)
                        baseline_object_name = f"baselines/{run_id}/{target_name}.png"
                        temp_baseline_path = f"debug/temp_baseline_{timestamp_slug}.png"

                        try:
                            minio_client.fget_object(
                                ARTIFACTS_BUCKET_NAME,
                                baseline_object_name,
                                temp_baseline_path,
                            )
                            print(
                                f"  [VISUAL] Baseline found for '{target_name}'. Comparing..."
                            )

                            expect(page).to_have_screenshot(
                                path=temp_baseline_path, threshold=0.2, full_page=True
                            )

                            if (
                                visual_status != "FAIL"
                            ):  # Don't override a previous failure
                                visual_status = "PASS"

                        except S3Error as exc:
                            if exc.code == "NoSuchKey":
                                print(
                                    f"  [VISUAL] No baseline found for '{target_name}'. Creating new one."
                                )
                                new_baseline_bytes = page.screenshot(full_page=True)
                                minio_client.put_object(
                                    ARTIFACTS_BUCKET_NAME,
                                    baseline_object_name,
                                    io.BytesIO(new_baseline_bytes),
                                    len(new_baseline_bytes),
                                )
                                if visual_status != "FAIL":
                                    visual_status = "BASELINE_CREATED"
                            else:
                                raise  # Re-raise other MinIO errors
                        except PlaywrightError:
                            # This block executes on visual mismatch
                            visual_status = "FAIL"
                            # Only set the visual failure flag if it hasn't been set before
                            # This ensures we only save one screenshot for the whole run
                            if not has_visual_failure:
                                has_visual_failure = True
                                # --- FIX: Save artifact with a consistent name ---
                                failure_image_name = (
                                    f"{artifacts_path}/visual_failure.png"
                                )
                                failure_bytes = page.screenshot(full_page=True)
                                minio_client.put_object(
                                    ARTIFACTS_BUCKET_NAME,
                                    failure_image_name,
                                    io.BytesIO(failure_bytes),
                                    len(failure_bytes),
                                )
                            raise  # Re-raise to trigger the main failure logic
                        finally:
                            if os.path.exists(temp_baseline_path):
                                os.remove(temp_baseline_path)
                    else:
                        # Use the new robust locator function
                        element_locator = find_element_locator(
                            page, target_name, ui_blueprint
                        )
                        expect(element_locator).to_be_visible(timeout=10000)
                        if action == "ENTER_TEXT":
                            element_locator.fill(data_to_use)
                        elif action == "CLICK":
                            element_locator.click()
                            page.wait_for_load_state("domcontentloaded")
                        elif action == "VERIFY_ELEMENT_VISIBLE":
                            # This check is already done above, but we keep it for logical clarity
                            expect(element_locator).to_be_visible()

                    print(
                        f"  [SUCCESS] Action '{action}' on '{target_name}' successful."
                    )
                    send_realtime_update(
                        db_run_id,
                        {
                            "type": "step_result",
                            "step": step.get("step"),
                            "status": "PASS",
                        },
                    )

                status = "PASS"

            except Exception as e:
                print(f"[FAIL] Test run finished with an error: {e}")
                status = "FAIL"
                if has_visual_failure and not failure_reason:
                    failure_reason = (
                        "Visual test failed. Screenshot did not match the baseline."
                    )
                else:
                    failure_reason = re.sub(r"\s+", " ", str(e).splitlines()[0])

                send_realtime_update(
                    db_run_id,
                    {"type": "run_end", "status": "FAIL", "reason": failure_reason},
                )

                if "page" in locals() and page and minio_client:
                    try:
                        screenshot_path = f"{artifacts_path}/failure.png"
                        screenshot_bytes = page.screenshot()
                        minio_client.put_object(
                            ARTIFACTS_BUCKET_NAME,
                            screenshot_path,
                            io.BytesIO(screenshot_bytes),
                            len(screenshot_bytes),
                        )

                        if context:
                            trace_path_local = f"debug/trace_{timestamp_slug}.zip"
                            context.tracing.stop(path=trace_path_local)
                            trace_path_remote = f"{artifacts_path}/trace.zip"
                            minio_client.fput_object(
                                ARTIFACTS_BUCKET_NAME,
                                trace_path_remote,
                                trace_path_local,
                            )
                            os.remove(trace_path_local)
                    except Exception as artifact_error:
                        print(
                            f"  [ERROR] Could not save failure artifacts: {artifact_error}"
                        )
            finally:
                if context:
                    context.close()
                if "browser" in locals() and browser:
                    browser.close()

        if status == "PASS":
            # If the test passed but no visual tests were run, mark visual as PASS
            if visual_status == "N/A":
                visual_status = "PASS"
            send_realtime_update(
                db_run_id,
                {"type": "run_end", "status": "PASS", "visual_status": visual_status},
            )

        print(f"--- Test Run Finished with Status: {status} ---")
        update_result_in_db(
            db_run_id=db_run_id,
            status=status,
            visual_status=visual_status,
            failure_reason=failure_reason,
            artifacts_path=(
                artifacts_path if status == "FAIL" or has_visual_failure else None
            ),
        )


def main():
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

            def callback(ch, method, properties, body):
                try:
                    test_case = json.loads(body)
                    run_test_case(test_case)
                except Exception as e:
                    print(f"ERROR processing job in agent callback: {e}")
                finally:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_qos(prefetch_count=1)

            # --- FIX: Agent now listens to both queues regardless of environment ---
            queues_to_listen = ["execution_queue", "live_view_queue"]

            for queue_name in queues_to_listen:
                channel.queue_declare(queue=queue_name, durable=True)
                channel.basic_consume(queue=queue_name, on_message_callback=callback)

            print(
                f" [*] Execution Agent waiting for jobs on queue(s): {', '.join(queues_to_listen)}. To exit press CTRL-C"
            )
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
