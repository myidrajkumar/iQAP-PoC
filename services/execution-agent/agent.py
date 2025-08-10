import json
from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError


def run_test_with_self_healing(test_case_json: dict):
    """
    Receives a JSON test case and executes it using Playwright.
    Includes a basic self-healing mechanism.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # This proves the "plug and play" nature of iQAP.
        target_url = "https://www.saucedemo.com"
        print(f"Navigating to {target_url}")
        page.goto(target_url)

        for step in test_case_json["steps"]:
            action = step["action"]
            target_name = step["target_element"]
            data = step.get("data", "")

            print(f"\nExecuting Step {step['step']}: {action} on '{target_name}'")

            # In a real system, this map would be the live UI blueprint
            # provided by the Discovery Service for the target page.
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
                continue

            try:
                # --- Primary Execution Attempt ---
                element = page.locator(primary_selector)

                if action == "ENTER_TEXT":
                    # Replace placeholder data with actual test data
                    username = (
                        "standard_user"
                        if "[VALID_USERNAME]" in data
                        else "problem_user"
                    )
                    password = (
                        "secret_sauce"
                        if "[VALID_PASSWORD]" in data
                        else "wrong_password"
                    )
                    text_to_enter = username if "USERNAME" in data else password
                    element.fill(text_to_enter)

                elif action == "CLICK":
                    element.click()

                print(
                    f"  [SUCCESS] Action '{action}' on primary selector '{primary_selector}' successful."
                )

            except PlaywrightError:
                # --- Self-Healing Logic ---
                print(
                    f"  [HEAL] Primary selector '{primary_selector}' failed. Attempting self-healing..."
                )

                try:
                    healed_element = None
                    # Simple self-healing strategy: Try finding a button by its text content.
                    if target_name == "Login_Button":
                        print(
                            "  [HEAL] Strategy: Looking for an input button with text 'Login'."
                        )
                        # This would find a button like <input type="submit" value="Login">
                        healed_element = page.locator(
                            "input[type='submit'][value='Login']"
                        )

                    if healed_element and healed_element.is_visible():
                        print("  [HEAL] Found element with alternative strategy.")
                        if action == "CLICK":
                            healed_element.click()
                        print(f"  [SUCCESS] Self-healing successful.")
                    else:
                        raise Exception("Self-healing could not find the element.")
                except Exception as e:
                    print(f"  [FAIL] Self-healing failed. {e}")
                    break  # Stop the test if a step fails and cannot be healed

        # --- Final Verification ---
        try:
            print("\nFinal Verification: Checking for successful login...")
            # A good test waits for a specific element that only appears after success.
            inventory_list = page.locator(".inventory_list")
            expect(inventory_list).to_be_visible(timeout=5000)
            print("[PASS] Test finished successfully. Inventory list is visible.")
        except PlaywrightError:
            print("[FAIL] Test finished unsuccessfully. Could not verify login.")

        browser.close()


if __name__ == "__main__":
    # In a real system, this agent would listen to a message queue for jobs.
    # For this PoC, we feed it the JSON directly to test its execution logic.
    print("--- iQAP Execution Agent PoC ---")

    # This is the same JSON our AI Orchestrator generates.
    mock_test_case = {
        "test_case_id": "TC-LOGIN-001",
        "objective": "Verify a user can log in with valid credentials and see the dashboard.",
        "steps": [
            {
                "step": 1,
                "action": "ENTER_TEXT",
                "target_element": "Username_Input",
                "data": "[VALID_USERNAME]",
                "expected_result": "Text should be entered in the username field.",
            },
            {
                "step": 2,
                "action": "ENTER_TEXT",
                "target_element": "Password_Input",
                "data": "[VALID_PASSWORD]",
                "expected_result": "Text should be entered in the password field.",
            },
            {
                "step": 3,
                "action": "CLICK",
                "target_element": "Login_Button",
                "data": "N/A",
                "expected_result": "User should be redirected to the dashboard page.",
            },
        ],
    }

    run_test_with_self_healing(mock_test_case)
