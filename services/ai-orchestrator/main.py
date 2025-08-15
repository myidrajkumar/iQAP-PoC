import os
import pika
import json
import httpx
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# --- Initialize ---
app = FastAPI()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
generation_config = {
    "temperature": 0.2,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}
model = genai.GenerativeModel("gemini-1.0-pro", generation_config=generation_config)

DISCOVERY_SERVICE_URL = "http://discovery-service:8001/discover"

# --- RabbitMQ Configuration ---
RABBITMQ_HOST = "rabbitmq"
credentials = pika.PlainCredentials(
    os.getenv("RABBITMQ_DEFAULT_USER"), os.getenv("RABBITMQ_DEFAULT_PASS")
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerationRequest(BaseModel):
    requirement: str
    target_url: str


class WebhookRequest(BaseModel):
    suite_name: str
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
        print(f"ERROR: Could not connect to RabbitMQ: {e}")
        raise HTTPException(status_code=503, detail="Messaging service unavailable.")


def call_gemini_service(requirement: str, ui_blueprint: str) -> dict:
    """Builds the MCP and calls the Google Gemini API."""
    print("MCP: Building context and calling Google Gemini...")

    prompt = f"""
    You are an expert QA Automation Engineer. Your task is to convert a business requirement and a UI element blueprint into a structured JSON test case. You must return only a single, valid JSON object and nothing else.

    Business Requirement: "{requirement}"
    ---
    UI Blueprint (discovered elements from the page):
    {ui_blueprint}
    ---
    Generate a JSON test case with the following schema:
    {{
      "test_case_id": "string (e.g., TC-LOGIN-001)",
      "objective": "string",
      "parameters": [
        {{
          "dataset_name": "string (e.g., 'valid_credentials')",
          "data": {{ "Username_Input": "string", "Password_Input": "string" }}
        }},
        {{
          "dataset_name": "string (e.g., 'locked_out_user')",
          "data": {{ "Username_Input": "string", "Password_Input": "string" }}
        }}
      ],
      "steps": [
        {{ "step": "integer", "action": "string (e.g., ENTER_TEXT, CLICK)", "target_element": "string (must be a logical_name from the blueprint)", "data_key": "string (the key from the dataset above, e.g., 'Username_Input')" }}
      ]
    }}
    """

    try:
        response = model.generate_content(prompt)
        # Clean up Gemini's markdown response
        cleaned_response = (
            response.text.replace("```json", "").replace("```", "").strip()
        )
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"ERROR: Gemini API call failed: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate test case from AI model."
        )


@app.post("/webhook/run-suite")
async def run_suite_webhook(request: WebhookRequest):
    """CI/CD Webhook to trigger a pre-defined test suite."""
    print(f"Webhook: Received request to run suite '{request.suite_name}'")
    # TODO: This is a stub. A real implementation would fetch pre-defined tests from the DB.
    mock_requirement = "Log in, verify inventory page, and log out."
    generated_test_case = await generate_test_case(
        GenerationRequest(requirement=mock_requirement, target_url=request.target_url)
    )
    return {
        "message": f"Webhook triggered. Job '{generated_test_case.get('test_case_id')}' published."
    }


async def get_ui_blueprint(url: str) -> str:
    """Calls the Discovery Service to get a UI blueprint."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DISCOVERY_SERVICE_URL, json={"url": url}, timeout=60.0
            )
            response.raise_for_status()
            return json.dumps(response.json(), indent=2)
    except httpx.RequestError as e:
        print(f"ERROR: Could not connect to Discovery Service: {e}")
        raise HTTPException(status_code=503, detail="Discovery Service unavailable.")


def call_llm_service(requirement: str, ui_blueprint: str) -> dict:
    """Builds the MCP and calls the real OpenAI API."""
    print("MCP: Building context and calling OpenAI...")
    system_prompt = "You are an expert QA Automation Engineer. Your task is to convert a business requirement and a UI element blueprint into a structured JSON test case. You must return only a single, valid JSON object and nothing else."

    user_prompt = f"""
    Business Requirement: "{requirement}"
    ---
    UI Blueprint (discovered elements from the page):
    {ui_blueprint}
    ---
    Generate a JSON test case with the following schema:
    {{
        "test_case_id": "string (e.g., TC-LOGIN-001)",
        "objective": "string",
        "steps": [
            {{ "step": "integer", "action": "string (e.g., ENTER_TEXT, CLICK)", "target_element": "string (must be a logical_name from the blueprint)", "data": "string (use placeholders like [VALID_USERNAME])" }}
        ]
    }}
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        response_text = completion.choices.message.content
        return json.loads(response_text)
    except Exception as e:
        print(f"ERROR: OpenAI API call failed: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate test case from AI model."
        )


@app.post("/generate-test-case")
async def generate_test_case(request: GenerationRequest):
    print(f"Orchestrator: Received request for URL: {request.target_url}")

    # 1. Get UI blueprint from the Discovery Service
    ui_blueprint = await get_ui_blueprint(request.target_url)

    # 2. Call the real LLM with the context
    generated_test_case = call_llm_service(request.requirement, ui_blueprint)

    # 3. Publish the job to RabbitMQ
    publish_to_rabbitmq(generated_test_case)

    return {
        "message": "Test Case Generation Job Published!",
        "test_case_id": generated_test_case.get("test_case_id"),
    }


@app.get("/")
def read_root():
    return {"message": "iQAP AI Orchestrator is running."}
