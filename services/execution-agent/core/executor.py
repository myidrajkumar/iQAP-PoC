import os
import io
import re
import time
import json
import httpx
from minio import Minio
from minio.error import S3Error
from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError
from .config import settings

# --- MinIO Client Initialization ---
try:
    minio_client = Minio(
        settings.MINIO_HOST,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False,
    )
    print("Execution Agent: Successfully initialized MinIO client.")
except Exception as e:
    print(f"Execution Agent: CRITICAL - Failed to initialize MinIO client: {e}")
    minio_client = None

# --- Helper Functions ---
def send_realtime_update(run_id: int, update: dict):
    if not run_id or not settings.IS_LIVE_VIEW:
        return
    try:
        httpx.post(f"{settings.REALTIME_SERVICE_URL}/update/{run_id}", json=update, timeout=5)
    except httpx.RequestError as e:
        print(f"  [Realtime] Could not send update for run {run_id}: {e}")

def get_interactive_elements(page):
    elements = []
    # This selector is now defined locally
    INTERACTIVE_ELEMENTS = 'button, a, input, select, textarea, [role="button"], [role="link"]'
    locators = page.locator(INTERACTIVE_ELEMENTS)
    for i in range(locators.count()):
        locator = locators.nth(i)
        try:
            if not locator.is_visible():
                continue
            tag = locator.evaluate("element => element.tagName.toLowerCase()")
            text = locator.text_content(timeout=500).strip()
            element_id = locator.get_attribute("id")
            name = locator.get_attribute("name")
            placeholder = locator.get_attribute("placeholder")
            aria_label = locator.get_attribute("aria-label")
            role = locator.get_attribute("role")
            data_test = locator.get_attribute("data-test")
            logical_name = (element_id or data_test or name or aria_label or text.replace(" ", "_") or f"{tag}_{i}")
            if logical_name: logical_name = logical_name.replace('\n', ' ').strip()
            elements.append({
                "logical_name": logical_name, "tag": tag, "text": text, "id": element_id,
                "name": name, "placeholder": placeholder, "aria_label": aria_label,
                "role": role, "data_test": data_test,
            })
        except Exception:
            continue
    return elements

def find_element_locator(page, target_name: str, ui_blueprint: list):
    element_data = next((el for el in ui_blueprint if el.get("logical_name") == target_name), None)
    if not element_data:
        raise ValueError(f"Logical name '{target_name}' not found in UI blueprint.")
    if element_data.get("data_test"): return page.locator(f"[data-test='{element_data['data_test']}']")
    if element_data.get("id"): return page.locator(f"#{element_data['id']}")
    if element_data.get("text"): return page.get_by_text(element_data["text"], exact=True)
    if element_data.get("placeholder"): return page.get_by_placeholder(element_data["placeholder"], exact=True)
    raise ValueError(f"Could not determine a stable locator for '{target_name}'.")

# --- Main Executor Logic ---
def execute_single_step(request):
    step = request.step
    settings.IS_LIVE_VIEW = request.is_live_view

    with sync_playwright() as p:
        browser = None
        try:
            launch_options = {"headless": not settings.IS_LIVE_VIEW, "slow_mo": 50 if settings.IS_LIVE_VIEW else 0}
            if settings.IS_DOCKER:
                launch_options["args"] = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            
            browser = p.chromium.launch(**launch_options)
            page = browser.new_page()
            page.goto(request.target_url, timeout=60000)

            send_realtime_update(request.db_run_id, {"type": "step_result", "step": step.get("step_number", 0), "status": "RUNNING"})

            action = step.get("action")
            target_name = step.get("target_element")

            element_locator = find_element_locator(page, target_name, request.ui_blueprint)
            expect(element_locator).to_be_visible(timeout=10000)
            if action == "ENTER_TEXT":
                data_key = step.get("data_key")
                data_to_use = request.dataset.get(data_key, "")
                element_locator.fill(data_to_use)
            elif action == "CLICK":
                element_locator.click()
                # Wait for potential navigation or dynamic content
                page.wait_for_load_state("domcontentloaded", timeout=5000)

            send_realtime_update(request.db_run_id, {"type": "step_result", "step": step.get("step_number", 0), "status": "PASS"})
            
            final_url = page.url
            
            new_elements = get_interactive_elements(page)
            new_blueprint = {"url": final_url, "elements": new_elements}
            
            browser.close()
            return {"status": "success", "new_url": final_url, "new_blueprint": new_blueprint}

        except (PlaywrightError, ValueError) as e:
            reason = re.sub(r"\s+", " ", str(e).splitlines()[0])
            if browser:
                browser.close()
            return {"status": "fail", "new_url": request.target_url, "reason": reason}