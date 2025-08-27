import filecmp
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

def send_final_status_broadcast(update_payload: dict):
    try:
        httpx.post(f"{REALTIME_SERVICE_URL}/notify/broadcast", json=update_payload, timeout=5)
        print(f"  [Notification] Sent final status broadcast for ID: {update_payload.get('id')}")
    except httpx.RequestError as e:
        print(f"  [Notification] Could not send final status broadcast: {e}")


def update_result_in_db(
    db_run_id: int,
    status: str,
    visual_status: str = "N/A",
    failure_reason: str = None,
    artifacts_path: str = None,
    visual_artifacts: list = None,
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
                 SET status = %s, visual_status = %s, failure_reason = %s, artifacts_path = %s, visual_artifacts = %s
                 WHERE id = %s;"""
        visual_artifacts_json = json.dumps(visual_artifacts) if visual_artifacts else None
        cursor.execute(
            sql, (status, visual_status, failure_reason, artifacts_path, visual_artifacts_json, db_run_id)
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

    if element_data.get("data_test"):
        selector = f"[data-test='{element_data['data_test']}']"
        return page.locator(selector)
    if element_data.get("id"):
        selector = f"#{element_data['id']}"
        return page.locator(selector)
    if element_data.get("text"):
        return page.get_by_text(element_data["text"], exact=True)
    if element_data.get("placeholder"):
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
    is_live_view = test_case_json.get("is_live_view", False)

    if is_live_view:
        send_realtime_update(
            db_run_id,
            {"type": "run_start", "message": "Test execution started.", "steps": test_case_json.get("steps", [])},
        )

    for params in parameter_sets:
        dataset_name = params.get("dataset_name", "default")
        dataset = params.get("data", {})
        run_id_suffix = re.sub(r"[^a-zA-Z0-9_-]", "", dataset_name)
        timestamp_slug = time.strftime("%Y%m%d-%H%M%S")
        artifacts_path = f"runs/{test_case_id_base}/{run_id_suffix}-{timestamp_slug}"
        run_id = f"{test_case_id_base}-{dataset_name}"

        print(f"\n--- Starting Test Run: {run_id} (Live View: {is_live_view}) ---")

        status = "PASS"
        visual_status = "N/A"
        failure_reason = None
        visual_failures_list = []

        with sync_playwright() as p:
            context = None
            browser = None
            try:
                launch_options = {
                    "headless": not is_live_view,
                    "slow_mo": 0,
                }
                if is_docker:
                    launch_options["args"] = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
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

                    if is_live_view:
                        send_realtime_update(db_run_id, {"type": "step_result", "step": step.get("step"), "status": "RUNNING"})

                    if action == "VISUAL_VALIDATION":
                        page.wait_for_load_state("networkidle", timeout=10000)
                        
                        mode = "headless" if not is_live_view else "headful"
                        baseline_object_name = f"baselines/{run_id}/{mode}/{target_name}.png"
                        
                        temp_baseline_path = f"debug/baseline_{timestamp_slug}.png"
                        current_screenshot_path = f"debug/current_{timestamp_slug}.png"
                        
                        try:
                            minio_client.fget_object(ARTIFACTS_BUCKET_NAME, baseline_object_name, temp_baseline_path)
                            page.screenshot(path=current_screenshot_path, full_page=True)
                            if not filecmp.cmp(temp_baseline_path, current_screenshot_path, shallow=False):
                                visual_status = "FAIL"
                                failure_artifact_name = f"visual_failure_step_{step.get('step')}_{target_name}.png"
                                failure_artifact_path = f"{artifacts_path}/{failure_artifact_name}"
                                minio_client.fput_object(ARTIFACTS_BUCKET_NAME, failure_artifact_path, current_screenshot_path)
                                visual_failures_list.append(failure_artifact_name)
                            else:
                                if visual_status != "FAIL": visual_status = "PASS"
                        except S3Error as exc:
                            if exc.code == "NoSuchKey":
                                new_baseline_bytes = page.screenshot(full_page=True)
                                minio_client.put_object(ARTIFACTS_BUCKET_NAME, baseline_object_name, io.BytesIO(new_baseline_bytes), len(new_baseline_bytes), content_type='image/png')
                                if visual_status != "FAIL": visual_status = "BASELINE_CREATED"
                            else: raise
                        finally:
                            if os.path.exists(temp_baseline_path): os.remove(temp_baseline_path)
                            if os.path.exists(current_screenshot_path): os.remove(current_screenshot_path)
                    
                    else:
                        element_locator = find_element_locator(page, target_name, ui_blueprint)
                        expect(element_locator).to_be_visible(timeout=10000)
                        if action == "ENTER_TEXT": element_locator.fill(data_to_use)
                        elif action == "CLICK": element_locator.click(); page.wait_for_load_state("domcontentloaded")
                        elif action == "VERIFY_ELEMENT_VISIBLE": expect(element_locator).to_be_visible()

                    if is_live_view:
                        send_realtime_update(db_run_id, {"type": "step_result", "step": step.get('step'), "status": "PASS"})
                
                if is_live_view:
                    final_live_status = "FAIL" if visual_status == "FAIL" else "PASS"
                    reason = "Visual test failed" if visual_status == "FAIL" else None
                    send_realtime_update(db_run_id, {"type": "run_end", "status": final_live_status, "reason": reason})

            except (PlaywrightError, ValueError, AssertionError) as e:
                status = "FAIL"
                failure_reason = re.sub(r"\s+", " ", str(e).splitlines()[0])
                if is_live_view:
                    send_realtime_update(db_run_id, {"type": "run_end", "status": "FAIL", "reason": failure_reason})
                
                if 'page' in locals() and page and minio_client:
                    try:
                        screenshot_path = f"{artifacts_path}/failure.png"
                        screenshot_bytes = page.screenshot()
                        minio_client.put_object(ARTIFACTS_BUCKET_NAME, screenshot_path, io.BytesIO(screenshot_bytes), len(screenshot_bytes))
                        if context:
                            trace_path_local = f"debug/trace_{timestamp_slug}.zip"
                            context.tracing.stop(path=trace_path_local)
                            trace_path_remote = f"{artifacts_path}/trace.zip"
                            minio_client.fput_object(ARTIFACTS_BUCKET_NAME, trace_path_remote, trace_path_local)
                            if os.path.exists(trace_path_local): os.remove(trace_path_local)
                    except Exception as artifact_error:
                        print(f"  [ERROR] Could not save failure artifacts: {artifact_error}")
            
            finally:
                if context: context.close()
                if browser: browser.close()
        
        # Determine final status
        final_visual_status = visual_status
        if status == "PASS" and visual_status == "FAIL":
            final_visual_status = "FAIL"
        elif status == "PASS":
            final_visual_status = visual_status if visual_status != 'N/A' else 'PASS'
        else:
            final_visual_status = "FAIL"

        update_result_in_db(
            db_run_id=db_run_id,
            status=status,
            visual_status=final_visual_status,
            failure_reason=failure_reason,
            artifacts_path=(artifacts_path if status == "FAIL" or visual_failures_list else None),
            visual_artifacts=visual_failures_list,
        )

        send_final_status_broadcast({
            "type": "status_update",
            "id": db_run_id,
            "status": status,
            "visual_status": final_visual_status,
        })


def main():
    while True:
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials, heartbeat=600))
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
            queues_to_listen = ["execution_queue", "live_view_queue"]
            for queue_name in queues_to_listen:
                channel.queue_declare(queue=queue_name, durable=True)
                channel.basic_consume(queue=queue_name, on_message_callback=callback)
            print(f" [*] Execution Agent waiting for jobs on queue(s): {', '.join(queues_to_listen)}. To exit press CTRL-C")
            channel.start_consuming()
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.StreamLostError) as e:
            print(f"Execution Agent: Connection lost or unavailable. Error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("Execution Agent: Shutting down.")
            break


if __name__ == "__main__":
    main()