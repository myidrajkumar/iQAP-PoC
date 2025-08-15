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
    """Compares two images and returns a difference score."""
    img1 = Image.open(io.BytesIO(img1_data)).convert("RGB")
    img2 = Image.open(io.BytesIO(img2_data)).convert("RGB")

    if img1.size != img2.size:
        return 100.0, None  # Different sizes are a major fail

    diff = ImageChops.difference(img1, img2)

    # Calculate a simple difference score
    stat = diff.getextrema()
    max_diff = max(stat[0][1], stat[1][1], stat[2][1])
    score = (max_diff / 255) * 100

    return score, diff if score > diff_threshold else None


def handle_visual_test(page, test_case_id: str, step_name: str):
    """Orchestrates a single visual regression test."""
    if not minio_client:
        return "N/A", "MinIO client not configured."

    screenshot_bytes = page.screenshot()
    object_name = f"{test_case_id}/{step_name}.png"
    latest_object_name = f"{test_case_id}/{step_name}.latest.png"
    diff_object_name = f"{test_case_id}/{step_name}.diff.png"

    try:
        # Check if a baseline exists
        minio_client.stat_object(VISUAL_BUCKET_NAME, object_name)

        # Baseline exists, download and compare
        baseline_response = minio_client.get_object(VISUAL_BUCKET_NAME, object_name)
        baseline_bytes = baseline_response.read()

        diff_score, diff_image = compare_images(baseline_bytes, screenshot_bytes)

        if diff_image:
            print(
                f"  [VISUAL] FAIL: Difference score {diff_score:.2f} exceeded threshold."
            )
            # Upload the failed image and the difference map for review
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


def write_result_to_db(
    objective: str,
    status: str,
    visual_status: str,
    step_results: list,
    test_case_id: str,
):
    """Connects to the PostgreSQL database and inserts a detailed test result."""
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
    """
    Takes a JSON test case, executes it using Playwright, and writes the result to the DB.
    """
    test_case_id = test_case_json.get("test_case_id", "UNKNOWN_TC")
    print(f"\n--- Starting Test Case: {test_case_id} ---")

    overall_status = "FAIL"  # Default status
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
                data_key = step.get("data_key")  # For data parameterization

                # Using a hardcoded dataset for this version
                dataset = {
                    "Username_Input": "standard_user",
                    "Password_Input": "secret_sauce",
                }
                data = dataset.get(data_key, "")

                print(f"Executing Step {step.get('step')}: {action} on '{target_name}'")

                # Simplified element map; in a real system this would come from the discovery blueprint
                element_map = {
                    "Username_Input": "#user-name",
                    "Password_Input": "#password",
                    "Login_Button": "#login-button",
                }
                selector = element_map.get(target_name)

                if not selector:
                    raise Exception(
                        f"Logical name '{target_name}' not found in element map."
                    )

                element = page.locator(selector)

                if action == "ENTER_TEXT":
                    element.fill(data, timeout=10000)
                elif action == "CLICK":
                    element.click(timeout=10000)

                step_results.append(
                    {
                        "step": step.get("step"),
                        "status": "PASS",
                        "details": f"Action {action} on {target_name} successful.",
                    }
                )

            print("\nFinal Verification...")
            expect(page.locator(".inventory_list")).to_be_visible(timeout=5000)
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
