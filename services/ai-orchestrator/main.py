import os
import pika
import json
import httpx
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# --- Initialize FastAPI and Gemini Model ---
app = FastAPI()

try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    generation_config = {
        "temperature": 0.2,
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


# --- Pydantic Models for Request Bodies ---
class GenerationRequest(BaseModel):
    requirement: str
    target_url: str


class WebhookRequest(BaseModel):
    suite_name: str
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
            properties=pika.BasicProperties(delivery_mode=2),  # make message persistent
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


def call_gemini_service(requirement: str, ui_blueprint: str) -> dict:
    """Builds the MCP and calls the Google Gemini API with the corrected, consistent prompt."""
    if not model:
        raise HTTPException(
            status_code=500, detail="Gemini model is not configured. Check API key."
        )

    print("MCP: Building context and calling Google Gemini...")

    prompt = f"""
    You are an expert QA Automation Engineer. Your task is to convert a business requirement and a UI element blueprint into a structured JSON test case. You must return only a single, valid JSON object and nothing else.

    Business Requirement: "{requirement}"
    ---
    UI Blueprint (discovered elements from the page):
    {ui_blueprint}
    ---
    Generate a JSON test case. The keys in the 'data' object inside 'parameters' MUST EXACTLY MATCH the 'logical_name' of the elements from the blueprint that you use in the 'steps'. For example, if a step targets 'user-name', the data key must also be 'user-name'.

    Example Response Format:
    {{
      "test_case_id": "TC001",
      "objective": "Verify a user can log in with valid credentials.",
      "target_url": "https://www.saucedemo.com",
      "parameters": [
        {{
          "dataset_name": "valid_credentials",
          "data": {{ 
            "user-name": "standard_user", 
            "password": "secret_sauce" 
          }}
        }}
      ],
      "steps": [
        {{ 
          "step": 1, 
          "action": "ENTER_TEXT", 
          "target_element": "user-name",
          "data_key": "user-name"
        }},
        {{ 
          "step": 2, 
          "action": "ENTER_TEXT", 
          "target_element": "password",
          "data_key": "password"
        }},
        {{ 
          "step": 3, 
          "action": "CLICK", 
          "target_element": "login-button",
          "verifications": {{
            "element_to_verify": "inventory_container"
          }}
        }}
      ]
    }}
    """

    try:
        response = model.generate_content(prompt)
        # Clean up Gemini's markdown response ` ```json ... ``` `
        cleaned_response = (
            response.text.replace("```json", "").replace("```", "").strip()
        )
        print("Gemini API call successful.")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"ERROR: Gemini API call or JSON parsing failed: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate test case from AI model."
        )


@app.post("/generate-test-case")
async def generate_test_case(request: GenerationRequest):
    """The main generation function that assembles and publishes the job."""
    print(f"Orchestrator: Received request for URL: {request.target_url}")

    # 1. Get UI blueprint from the Discovery Service
    ui_blueprint_string = await get_ui_blueprint(request.target_url)
    ui_blueprint_json = json.loads(ui_blueprint_string)

    # 2. Call the real Gemini LLM with the context
    generated_test_case = call_gemini_service(request.requirement, ui_blueprint_string)

    # 3. Inject the blueprint and the target_url into the final message for the agent
    generated_test_case["ui_blueprint"] = ui_blueprint_json["elements"]
    generated_test_case["target_url"] = request.target_url

    # 4. Publish the enriched job to RabbitMQ
    publish_to_rabbitmq(generated_test_case)

    return {
        "message": "Test Case Generation Job Published!",
        "test_case_id": generated_test_case.get("test_case_id"),
    }


@app.post("/webhook/run-suite")
async def run_suite_webhook(request: WebhookRequest):
    """CI/CD Webhook to trigger a pre-defined test suite."""
    print(f"Webhook: Received request to run suite '{request.suite_name}'")
    # TODO: This is a stub. A real implementation would fetch pre-defined tests from the DB.
    mock_requirement = (
        "Log in, verify the main product inventory page is visible, and then log out."
    )

    generation_request = GenerationRequest(
        requirement=mock_requirement, target_url=request.target_url
    )
    response_data = await generate_test_case(generation_request)

    return {
        "message": f"Webhook triggered. Job '{response_data.get('test_case_id')}' published."
    }


@app.get("/")
def read_root():
    """Root endpoint for health checks."""
    return {"message": "iQAP AI Orchestrator is running."}
