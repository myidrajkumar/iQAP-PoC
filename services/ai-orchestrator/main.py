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
    # Set temperature to a low value for more deterministic, less "creative" responses
    generation_config = {"temperature": 0.1, "top_p": 1, "top_k": 1, "max_output_tokens": 4096}
    model = genai.GenerativeModel('gemini-pro', generation_config=generation_config)
    print("AI Orchestrator: Successfully configured Gemini Pro model.")
except Exception as e:
    print(f"CRITICAL ERROR: Failed to configure Gemini API. Is GOOGLE_API_KEY set? Error: {e}")
    model = None

# --- Service URLs and RabbitMQ Configuration ---
DISCOVERY_SERVICE_URL = "http://discovery-service:8001/discover"
RABBITMQ_HOST = 'rabbitmq'
RABBITMQ_USER = os.getenv('RABBITMQ_DEFAULT_USER', 'rabbit_user')
RABBITMQ_PASS = os.getenv('RABBITMQ_DEFAULT_PASS', 'rabbit_password')
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
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
        channel = connection.channel()
        channel.queue_declare(queue='test_generation_queue', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='test_generation_queue',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
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
            response = await client.post(DISCOVERY_SERVICE_URL, json={"url": url}, timeout=60.0)
            response.raise_for_status()
            print("Discovery Service returned blueprint successfully.")
            return json.dumps(response.json(), indent=2)
    except httpx.RequestError as e:
        print(f"ERROR: Could not connect to Discovery Service: {e}")
        raise HTTPException(status_code=503, detail="Discovery Service unavailable.")

def call_gemini_service(requirement: str, ui_blueprint: str) -> dict:
    """Builds the MCP and calls the Google Gemini API with a simplified, robust prompt."""
    if not model:
        raise HTTPException(status_code=500, detail="Gemini model is not configured. Check API key.")
    
    print("MCP: Building context and calling Google Gemini...")
    
    # This is the new, simplified, and more direct prompt.
    prompt = f"""
    You are an expert QA Automation Engineer. Your primary function is to convert a business requirement and a UI element blueprint into a structured JSON test case.
    
    Instructions:
    1.  Base the test steps EXCLUSIVELY on the provided "Business Requirement".
    2.  Use the "UI Blueprint" to find the correct `logical_name` for each element you need to interact with.
    3.  The keys in the `data` object inside `parameters` MUST EXACTLY MATCH the `logical_name` you use in the `steps`.
    4.  For any "CLICK" action that causes a page navigation, you MUST include a "verifications" block to confirm the navigation was successful by checking for a visible element on the new page.
    5.  You must return ONLY the raw JSON object and absolutely no other text, explanation, or markdown formatting.

    ---
    Business Requirement:
    "{requirement}"
    ---
    UI Blueprint (discovered elements from the page):
    {ui_blueprint}
    ---
    
    Now, generate the JSON test case based on these instructions.
    """
    
    try:
        response = model.generate_content(prompt)
        # It's crucial to clean the response as Gemini can wrap it in markdown
        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        print("Gemini API call successful.")
        return json.loads(cleaned_response)
    except Exception as e:
        raw_response_text = "N/A"
        if 'response' in locals():
            raw_response_text = response.text
        print(f"ERROR: Gemini API call or JSON parsing failed: {e}. Raw response: {raw_response_text}")
        raise HTTPException(status_code=500, detail=f"Failed to generate a valid test case from the AI model. Raw response: {raw_response_text}")

@app.post("/generate-test-case")
async def generate_test_case(request: GenerationRequest):
    """The main generation function that assembles and publishes the job."""
    print(f"Orchestrator: Received request for URL: {request.target_url}")
    
    ui_blueprint_string = await get_ui_blueprint(request.target_url)
    ui_blueprint_json = json.loads(ui_blueprint_string)
    
    generated_test_case = call_gemini_service(request.requirement, ui_blueprint_string)
    
    # Inject the blueprint and the target_url into the final message for the agent
    generated_test_case['ui_blueprint'] = ui_blueprint_json['elements']
    generated_test_case['target_url'] = request.target_url
    
    publish_to_rabbitmq(generated_test_case)
    
    return {"message": "Test Case Generation Job Published!", "test_case_id": generated_test_case.get("test_case_id")}

@app.post("/webhook/run-suite")
async def run_suite_webhook(request: WebhookRequest):
    """CI/CD Webhook to trigger a pre-defined test suite."""
    print(f"Webhook: Received request to run suite '{request.suite_name}'")
    mock_requirement = "Log in, verify the main product inventory page is visible, and then log out."
    
    generation_request = GenerationRequest(requirement=mock_requirement, target_url=request.target_url)
    response_data = await generate_test_case(generation_request)

    return {"message": f"Webhook triggered. Job '{response_data.get('test_case_id')}' published."}

@app.get("/")
def read_root():
    """Root endpoint for health checks."""
    return {"message": "iQAP AI Orchestrator is running."}