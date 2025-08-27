"""Discovery Service for iQAP"""

import asyncio
import sys

from fastapi import FastAPI, HTTPException
from playwright.sync_api import sync_playwright
from pydantic import BaseModel

INTERACTIVE_ELEMENTS = (
    'button, a, input, select, textarea, [role="button"], [role="link"]'
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI()


class DiscoverRequest(BaseModel):
    """Discovery request model"""

    url: str


@app.post("/discover")
def discover_elements(request: DiscoverRequest):
    """Crawls a URL and returns a blueprint of its interactive elements."""

    print(f"Discovery Service: Received request for URL: {request.url}")
    elements = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(request.url, timeout=30000)

            # Find all common interactive elements
            locators = page.locator(INTERACTIVE_ELEMENTS)
            get_interactive_elements(elements, locators)

            browser.close()
    except Exception as e:
        print(f"ERROR: Playwright failed to discover elements: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to crawl URL: {e}")

    print(f"Discovery Service: Found {len(elements)} elements.")
    print(f"Discovery Service: Identified elements: {elements}")
    return {"url": request.url, "elements": elements}


def get_interactive_elements(elements, locators):
    for i in range(locators.count()):
        locator = locators.nth(i)
        try:
            # Skip invisible elements, which can cause errors
            if not locator.is_visible():
                continue

            tag = locator.evaluate("element => element.tagName.toLowerCase()")
            text = locator.text_content(timeout=500).strip()
            element_id = locator.get_attribute("id")
            name = locator.get_attribute("name")
            placeholder = locator.get_attribute("placeholder")
            aria_label = locator.get_attribute("aria-label")
            data_test = locator.get_attribute("data-test")

            logical_name = (
                element_id
                or data_test
                or name
                or aria_label
                or text.replace(" ", "_")
                or f"{tag}_{i}"
            )

            elements.append(
                {
                    "logical_name": logical_name,
                    "tag": tag,
                    "text": text,
                    "id": element_id,
                    "name": name,
                    "placeholder": placeholder,
                    "data_test": data_test,  # Add to the blueprint
                }
            )
        except Exception:
            # Ignore elements that disappear or cause errors during inspection
            continue


@app.get("/")
def read_root():
    """Root Health Check Endpoint"""
    return {"message": "iQAP Discovery Service is running."}
