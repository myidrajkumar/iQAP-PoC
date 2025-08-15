import pika
import os
import time
import json
import psycopg2
from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError
from PIL import Image, ImageChops
from minio import Minio
import io

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

# MinIO Configuration
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
except Exception as e:
    print(f"Execution Agent: CRITICAL - Failed to initialize MinIO client: {e}")
    minio_client = None


# --- Core Feature Functions ---


def compare_images(img1_data, img2_data, diff_threshold=1.0):
    """Compares two images and returns a difference score and a diff image if applicable."""
    img1 = Image.open(io.BytesIO(img1_data)).convert("RGB")
    img2 = Image.open(io.BytesIO(img2_data)).convert("RGB")

    if img1.size != img2.size:
        return 100.0, None  # Different sizes are a major fail

    diff = ImageChops.difference(img1, img2)

    stat = diff.getextrema()
    max_diff = max(stat[0][1], stat[1][1], stat[2][1])
    score = (max_diff / 255) * 100

    return score, diff if score > diff_threshold else None


def handle_visual_test(page, test_case_id: str, step_name: str):
    """Orchestrates a single visual regression test against MinIO."""
    if not minio_client:
        return "N/A", "MinIO client not configured."

    screenshot_bytes = page.screenshot()
    object_name = f"{test_case_id}/{step_name}.png"
    latest_object_name = f"{test_case_id}/{step_name}.latest.png"
    diff_object_name = f"{test_case_id}/{step_name}.diff.png"

    try:
        minio_client.stat_object(VISUAL_BUCKET_NAME, object_name)
        baseline_response = minio_client.get_object(VISUAL_BUCKET_NAME, object_name)
        baseline_bytes = baseline_response.read()

        diff_score, diff_image = compare_images(baseline_bytes, screenshot_bytes)

        if diff_image:
            print(
                f"  [VISUAL] FAIL: Difference score {diff_score:.2f} exceeded threshold."
            )
            minio_client.put_object(
                VISUAL_BUCKET_NAME,
                latest_object_name,
                io.BytesIO(screenshot_bytes),
                len(screenshot_bytes),
                "image/png",
            )

            diff_bytes = io.BytesIO()
            diff_image.save(diff_bytes, format="PNG")
            diff_bytes.seek(0)
            minio_client.put_object(
                VISUAL_BUCKET_NAME,
                diff_object_name,
                diff_bytes,
                diff_bytes.getbuffer().nbytes,
                "image/png",
            )

            return "FAIL", f"Visual diff score: {diff_score:.2f}"
        else:
            print("  [VISUAL] PASS: Images match baseline.")
            return "PASS", "Images match baseline."

    except Exception as e:
        # Assuming error means baseline does not exist
        print("  [VISUAL] No baseline found. Creating new one.")
        minio_client.put_object(
            VISUAL_BUCKET_NAME,
            object_name,
            io.BytesIO(screenshot_bytes),
            len(screenshot_bytes),
            "image/png",
        )
        return "BASELINE_CREATED", f"New baseline created: {object_name}"


def find_element_with_healing(page, target_name: str, ui_blueprint: list):
    """Dynamically finds a selector from the UI blueprint and includes self-healing."""
    target_element_data = next(
        (el for el in ui_blueprint if el.get("logical_name") == target_name), None
    )

    if not target_element_data:
        raise Exception(
            f"Logical name '{target_name}' not found in the provided UI blueprint."
        )

    # Strategy 1: Use 'id' if available (most reliable)
    if target_element_data.get("id"):
        primary_selector = f"#{target_element_data['id']}"
        try:
            page.locator(primary_selector).wait_for(state="visible", timeout=3000)
            print(
                f"  [Locator] Found element using primary selector: '{primary_selector}'"
            )
            return page.locator(primary_selector)
        except PlaywrightError:
            print(f"  [HEAL] Primary selector '{primary_selector}' failed.")

    # Fallback strategies for self-healing
    if target_element_data.get("text"):
        text_selector = (
            f"{target_element_data['tag']}:has-text(\"{target_element_data['text']}\")"
        )
        try:
            page.locator(text_selector).wait_for(state="visible", timeout=2000)
            print(f"  [HEAL] Found element using text selector: '{text_selector}'")
            return page.locator(text_selector)
        except PlaywrightError:
            pass

    if target_element_data.get("placeholder"):
        placeholder_selector = (
            f"input[placeholder='{target_element_data['placeholder']}']"
        )
        try:
            page.locator(placeholder_selector).wait_for(state="visible", timeout=2000)
            print(
                f"  [HEAL] Found element using placeholder selector: '{placeholder_selector}'"
            )
            return page.locator(placeholder_selector)
        except PlaywrightError:
            pass

    raise Exception(
        f"Self-healing failed. Could not find a stable locator for '{target_name}'."
    )


def write_result_to_db(
    objective: str,
    status: str,
    visual_status: str,
    step_results: list,
    test_case_id: str,
):
    """Connects to PostgreSQL and inserts a detailed test result."""
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
        )
        cursor = conn.cursor()
        sql = """INSERT INTO test_results (objective, status, visual_status, step_results, test_case_id, timestamp) 
                 VALUES (%s, %s, %s, %s, %s, NOW());"""
        cursor.execute(
            sql,
            (objective, status, visual_status, json.dumps(step_results), test_case_id),
        )
        conn.commit()
        print(f"  [DB] Result for {test_case_id} saved to database.")
        cursor.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"  [DB] Error saving result: {error}")
    finally:
        if conn is not None:
            conn.close()


def run_test_case(test_case_json: dict):
    """Orchestrates the entire test execution flow for a single test case."""
    test_case_id = test_case_json.get("test_case_id", "UNKNOWN_TC")
    ui_blueprint = test_case_json.get("ui_blueprint", [])
    print(f"\n--- Starting Test Case: {test_case_id} ---")

    overall_status = "FAIL"
    visual_status = "N/A"
    step_results = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            target_url = "https://www.saucedemo.com"  # TODO: Make this dynamic
            page.goto(target_url, timeout=60000)

            for step in test_case_json.get("steps", []):
                action = step.get("action")
                target_name = step.get("target_element")
                data_key = step.get("data_key")

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
                elif action == "VERIFY_ELEMENT_VISIBLE":
                    expect(element).to_be_visible()

                step_results.append(
                    {
                        "step": step.get("step"),
                        "status": "PASS",
                        "details": f"Action {action} on {target_name} successful.",
                    }
                )

            print("\nFinal Verification...")
            inventory_element = find_element_with_healing(
                page, "inventory_container", ui_blueprint
            )
            expect(inventory_element).to_be_visible()
            overall_status = "PASS"

            print("\nPerforming Visual Test...")
            visual_status, visual_details = handle_visual_test(
                page, test_case_id, "final_inventory_page"
            )
            step_results.append(
                {"step": "visual", "status": visual_status, "details": visual_details}
            )

            browser.close()
    except Exception as e:
        print(f"[FAIL] Test finished with an unhandled error: {e}")
        overall_status = "FAIL"
        step_results.append({"step": "error", "status": "FAIL", "details": str(e)})
    finally:
        print(f"--- Test Case Finished with Status: {overall_status} ---")
        write_result_to_db(
            objective=test_case_json.get("objective", "N/A"),
            status=overall_status,
            visual_status=visual_status,
            step_results=step_results,
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
