import os
from dotenv import load_dotenv
import pika
import json
import httpx
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# --- Initialize FastAPI and Gemini Model ---
app = FastAPI()

try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    generation_config = {"temperature": 0.0}
    model = genai.GenerativeModel(
        "gemini-2.5-flash", generation_config=generation_config
    )
    print("AI Orchestrator: Successfully configured Gemini Pro model.")
except Exception as e:
    print(
        f"CRITICAL ERROR: Failed to configure Gemini API. Is GOOGLE_API_KEY set? Error: {e}"
    )
    model = None

# --- Service URLs and RabbitMQ Configuration ---
is_docker = os.environ.get("DOCKER_ENV") == "true"
print(f"Running in Docker: {is_docker}")

if is_docker:
    DISCOVERY_SERVICE_URL = "http://discovery-service:8001/discover"
    RABBITMQ_HOST = "iqap-rabbitmq"  # Docker service name for RabbitMQ
else:
    DISCOVERY_SERVICE_URL = "http://localhost:8001/discover"
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")


RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "rabbit_user")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "rabbit_password")
credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

MOCK_TEST_CASE_JSON = {
    "test_case_id": "TC001_FALLBACK",
    "objective": "Verify a user can log in with valid credentials.",
    "parameters": [
        {
            "dataset_name": "valid_credentials",
            "data": {"user-name": "standard_user", "password": "secret_sauce"},
        }
    ],
    "steps": [
        {
            "step": 1,
            "action": "ENTER_TEXT",
            "target_element": "user-name",
            "data_key": "user-name",
        },
        {
            "step": 2,
            "action": "ENTER_TEXT",
            "target_element": "password",
            "data_key": "password",
        },
        {
            "step": 3,
            "action": "CLICK",
            "target_element": "login-button",
            "verifications": {"element_to_verify": "inventory_container"},
        },
    ],
}

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
        raise HTTPException(status_code=503, detail="Messaging service unavailable.")


async def get_ui_blueprint(url: str) -> str:
    print(f"Contacting Discovery Service of {DISCOVERY_SERVICE_URL}...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DISCOVERY_SERVICE_URL, json={"url": url}, timeout=60.0
            )
            response.raise_for_status()
            print("Discovery Service returned blueprint successfully.")
            return json.dumps(response.json(), indent=2).strip()
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail="Discovery Service unavailable.")


def generate_test_case_from_ai(requirement: str, ui_blueprint: str) -> dict:
    """
    Tries to call the Gemini API. If it fails for ANY reason, it returns the
    hardcoded MOCK_TEST_CASE_JSON as a reliable fallback.
    """
    if not model:
        print("[WARNING] Gemini model not configured. Using fallback.")
        return MOCK_TEST_CASE_JSON

    prompt = f"""
    You are a JSON generation machine. Your sole purpose is to convert a user's requirement into a structured JSON test case.
    
    RULES:
    1.  Base the test steps EXCLUSIVELY on the provided "Business Requirement".
    2.  Use the "UI Blueprint" to find the correct "logical_name" for each element.
    3.  You MUST use the key "action" for the action type. The allowed values for "action" are ONLY: "ENTER_TEXT", "CLICK", "VERIFY_ELEMENT_VISIBLE".
    4.  The keys in the "data" object inside "parameters" MUST EXACTLY MATCH the "logical_name" you use in the "steps".
    5.  A "CLICK" that navigates MUST have a "verifications" block.
    6.  You MUST return ONLY the raw JSON object and absolutely no other text or markdown.

    ---
    Business Requirement:
    {requirement}
    ---
    UI Blueprint:
    {ui_blueprint}
    ---
    
    Generate the JSON test case now.
    """

    try:
        print("MCP: Calling Google Gemini...")
        response = model.generate_content(prompt)
        cleaned_response = (
            response.text.replace("```json", "").replace("```", "").strip()
        )

        result = json.loads(cleaned_response)
        required_keys = ["test_case_id", "objective", "parameters", "steps"]
        print(f"Gemini response: {result}")
        if all(key in result for key in required_keys):
            print("Gemini API call successful and response is valid.")
            return result
        else:
            print(
                f"[WARNING] Gemini response was valid JSON but missed required keys. Using fallback."
            )
            return MOCK_TEST_CASE_JSON

    except Exception as e:
        print(f"[WARNING] Gemini API call or parsing failed: {e}. Using fallback.")
        return MOCK_TEST_CASE_JSON


@app.post("/generate-test-case")
async def generate_test_case(request: GenerationRequest):
    print(f"Orchestrator: Received request for URL: {request.target_url}")

    try:
        ui_blueprint_string = await get_ui_blueprint(request.target_url)
        ui_blueprint_json = json.loads(ui_blueprint_string.strip())
        print(
            f"Orchestrator: UI Blueprint json received successfully. {ui_blueprint_json}"
        )

        generated_test_case = generate_test_case_from_ai(
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
        print(f"FATAL ERROR in generation process: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    return {"message": "iQAP AI Orchestrator is running."}
