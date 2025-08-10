# FILE: iQAP-v1.0/services/execution-agent/agent.py (Corrected)

import pika
import os
import time
import json
from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError


def run_test_with_self_healing(test_case_json: dict):
    # This test execution logic remains the same
    print(f"\n--- Starting Test Case: {test_case_json.get('test_case_id')} ---")
    # The rest of this function is unchanged...
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
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
                print(f"  [FAIL] No selector found for logical name '{target_name}'")
                continue

            try:
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
            except PlaywrightError:
                print(
                    f"  [HEAL] Primary selector '{primary_selector}' failed. Attempting self-healing..."
                )
                print("  [FAIL] Self-healing failed.")
                break

        try:
            print("\nFinal Verification...")
            expect(page.locator(".inventory_list")).to_be_visible(timeout=5000)
            print("[PASS] Test finished successfully.")
        except PlaywrightError:
            print("[FAIL] Test finished unsuccessfully.")

        browser.close()
    print("--- Test Case Finished ---")


def main():
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
