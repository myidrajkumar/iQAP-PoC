import os
import io
import re
import time
import json
import httpx
from minio import Minio
from minio.error import S3Error
from playwright.async_api import async_playwright, expect, Error as PlaywrightError
from .config import settings # Note the relative import

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

def find_element_locator(page, target_name: str, ui_blueprint: list):
    # ... (This helper function is the same as before)
    element_data = next((el for el in ui_blueprint if el.get("logical_name") == target_name), None)
    if not element_data:
        raise ValueError(f"Logical name '{target_name}' not found in UI blueprint.")
    if element_data.get("data_test"):
        return page.locator(f"[data-test='{element_data['data_test']}']")
    if element_data.get("id"):
        return page.locator(f"#{element_data['id']}")
    if element_data.get("text"):
        return page.get_by_text(element_data["text"], exact=True)
    if element_data.get("placeholder"):
        return page.get_by_placeholder(element_data["placeholder"], exact=True)
    raise ValueError(f"Could not determine a stable locator for '{target_name}'.")

# --- Main Executor Logic ---
async def execute_single_step(request):
    step = request.step
    settings.IS_LIVE_VIEW = request.is_live_view # Set mode for this execution

    async with async_playwright() as p:
        browser = None
        try:
            launch_options = {"headless": not settings.IS_LIVE_VIEW, "slow_mo": 50 if settings.IS_LIVE_VIEW else 0}
            if settings.IS_DOCKER:
                launch_options["args"] = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            
            browser = await p.chromium.launch(**launch_options)
            page = await browser.new_page()
            await page.goto(request.target_url, timeout=60000)

            send_realtime_update(request.db_run_id, {"type": "step_result", "step": step.get("step_number", 0), "status": "RUNNING"})

            action = step.get("action")
            target_name = step.get("target_element")

            if action == "VISUAL_VALIDATION":
                # Visual validation logic can be complex in a single-step executor
                # For now, we simplify it or acknowledge it needs more state.
                # Here, we'll just take a snapshot for now. A full implementation needs baseline management.
                await page.wait_for_load_state("networkidle")
                # Placeholder for visual validation logic
            else:
                element_locator = find_element_locator(page, target_name, request.ui_blueprint)
                await expect(element_locator).to_be_visible(timeout=10000)
                if action == "ENTER_TEXT":
                    data_key = step.get("data_key")
                    data_to_use = request.dataset.get(data_key, "")
                    await element_locator.fill(data_to_use)
                elif action == "CLICK":
                    await element_locator.click()
                    await page.wait_for_load_state("domcontentloaded")

            send_realtime_update(request.db_run_id, {"type": "step_result", "step": step.get("step_number", 0), "status": "PASS"})
            
            final_url = page.url
            await browser.close()
            return {"status": "success", "new_url": final_url}

        except (PlaywrightError, ValueError) as e:
            reason = re.sub(r"\s+", " ", str(e).splitlines()[0])
            if browser:
                await browser.close()
            return {"status": "fail", "new_url": request.target_url, "reason": reason}