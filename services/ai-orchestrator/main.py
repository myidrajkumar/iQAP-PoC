import os
import pika
import json
import httpx
import time
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# --- Initialize FastAPI and Gemini Model ---
app = FastAPI()

try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    generation_config = {
        "temperature": 0.1,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 4096,
    }
    model = genai.GenerativeModel("gemini-2.0-flash", generation_config=generation_config)
    print("AI Orchestrator: Successfully configured Gemini Pro model.")
except Exception as e:
    print(
        f"CRITICAL ERROR: Failed to configure Gemini API. Is GOOGLE_API_KEY set? Error: {e}"
    )
    model = None

# --- Service URLs and RabbitMQ Configuration ---
DISCOVERY_SERVICE_URL = "http://discovery-service:8001/discover"
RABBITMQ_HOST = "rabbitmq"
RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "rabbit_user")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "rabbit_password")
credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic Models ---
class GenerationRequest(BaseModel):
    requirement: str
    target_url: str


def publish_to_rabbitmq(message: dict):
    """Publishes a job message to the RabbitMQ queue."""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
        )
        channel = connection.channel()
        channel.queue_declare(queue="test_generation_queue", durable=True)
        channel.basic_publish(
            exchange="",
            routing_key="test_generation_queue",
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
        print(f" [x] Sent job to RabbitMQ: {message.get('test_case_id')}")
    except pika.exceptions.AMQPConnectionError as e:
        print(f"ERROR: Could not connect to RabbitMQ: {e}")
        raise HTTPException(status_code=503, detail="Messaging service unavailable.")


async def get_ui_blueprint(url: str) -> str:
    """Calls the Discovery Service to get a UI blueprint."""
    print("Contacting Discovery Service...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DISCOVERY_SERVICE_URL, json={"url": url}, timeout=60.0
            )
            response.raise_for_status()
            print("Discovery Service returned blueprint successfully.")
            return json.dumps(response.json(), indent=2)
    except httpx.RequestError as e:
        print(f"ERROR: Could not connect to Discovery Service: {e}")
        raise HTTPException(status_code=503, detail="Discovery Service unavailable.")


def call_gemini_with_retries(
    requirement: str, ui_blueprint: str, max_retries: int = 3
) -> dict:
    """
    Calls the Gemini API, validates the response, and retries on failure.
    This is the new "Guardian" function.
    """
    if not model:
        raise Exception("Gemini model is not configured.")

    prompt = f"""
    You are an expert QA Automation Engineer. Your ONLY function is to convert a business requirement and a UI element blueprint into a structured JSON test case.

    RULES:
    1.  Base the test steps EXCLUSIVELY on the "Business Requirement".
    2.  Use the "UI Blueprint" to find the correct `logical_name` for each element.
    3.  The keys in the `data` object inside `parameters` MUST EXACTLY MATCH the `logical_name` you use in the `steps`.
    4.  For any "CLICK" that navigates, you MUST include a "verifications" block.
    5.  You MUST return ONLY the raw JSON object and absolutely no other text or markdown.

    ---
    Business Requirement: "{requirement}"
    ---
    UI Blueprint: {ui_blueprint}
    ---
    
    Generate the JSON test case now.
    """

    for attempt in range(max_retries):
        print(f"MCP: Calling Google Gemini (Attempt {attempt + 1}/{max_retries})...")
        try:
            response = model.generate_content(prompt)
            cleaned_response = (
                response.text.replace("```json", "").replace("```", "").strip()
            )

            # Validate the JSON structure
            result = json.loads(cleaned_response)
            required_keys = ["test_case_id", "objective", "parameters", "steps"]
            if all(key in result for key in required_keys):
                print("Gemini API call successful and response is valid.")
                return result
            else:
                print(
                    f"[WARNING] Gemini response was valid JSON but missed required keys. Retrying..."
                )

        except (json.JSONDecodeError, Exception) as e:
            print(f"[WARNING] Gemini API call or parsing failed: {e}. Retrying...")

        time.sleep(2)  # Wait before retrying

    raise Exception("AI failed to generate a valid test case after multiple attempts.")


@app.post("/generate-test-case")
async def generate_test_case(request: GenerationRequest):
    """The main generation function that assembles and publishes the job."""
    print(f"Orchestrator: Received request for URL: {request.target_url}")

    try:
        ui_blueprint_string = await get_ui_blueprint(request.target_url)
        ui_blueprint_json = json.loads(ui_blueprint_string)

        generated_test_case = call_gemini_with_retries(
            request.requirement, ui_blueprint_string
        )

        generated_test_case["ui_blueprint"] = ui_blueprint_json["elements"]
        generated_test_case["target_url"] = request.target_url

        publish_to_rabbitmq(generated_test_case)

        return {
            "message": "Test Case Generation Job Published!",
            "test_case_id": generated_test_case.get("test_case_id"),
        }

    except Exception as e:
        # If anything fails (discovery, or all Gemini retries), return a clear error to the UI.
        print(f"FATAL ERROR in generation process: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    """Root endpoint for health checks."""
    return {"message": "iQAP AI Orchestrator is running."}
