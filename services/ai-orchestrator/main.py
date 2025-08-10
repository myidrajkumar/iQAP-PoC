import time
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# Initialize the FastAPI app
app = FastAPI()

# Configure CORS to allow our frontend to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Define the structure of the incoming request body
class GenerationRequest(BaseModel):
    requirement: str
    # In a real app, you would also pass the target URL
    # target_url: str


def build_mcp_package(requirement: str) -> str:
    """
    This is the heart of the MCP. It assembles all necessary context.
    In a real system, this function would:
    1. Call the Discovery Service to get the UI blueprint for the target URL.
    2. Query a VectorDB to get few-shot examples related to the requirement.
    3. Fetch the mandatory JSON output schema from a database or config.
    4. Assemble everything into a detailed prompt.
    """
    print("MCP: Building context package...")

    # For this PoC, we will hardcode the context to simulate other services.
    ui_blueprint_context = """
    Context from Discovery Service:
    The login page contains these elements:
    - A textbox with the logical name 'Username_Input' (id='user-name')
    - A textbox with the logical name 'Password_Input' (id='password')
    - A button with the logical name 'Login_Button' (id='login-button')
    """

    json_schema_context = """
    You MUST return a single, valid JSON object with the following schema:
    {
        "test_case_id": "string",
        "objective": "string",
        "steps": [
            { "step": "integer", "action": "string", "target_element": "string", "data": "string", "expected_result": "string" }
        ]
    }
    """

    full_prompt = f"""
    System Role: You are an expert QA Engineer. Your task is to convert a requirement into a structured JSON test case.
    ---
    {ui_blueprint_context}
    ---
    Requirement: "{requirement}"
    ---
    Constraints:
    - Base all 'target_element' names on the logical names provided in the context.
    - Use placeholders like '[VALID_USERNAME]' for data.
    ---
    {json_schema_context}
    """
    print("MCP: Prompt assembly complete.")
    return full_prompt


def call_llm_service(prompt: str) -> dict:
    """
    This function calls the external LLM provider.
    For this PoC, it is MOCKED to ensure it runs without an API key.
    """
    print("LLM Service: Simulating API call...")
    time.sleep(1.5)  # Simulate network latency to make the UI loading state visible

    mock_response = {
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
    print("LLM Service: Mock response received.")
    return mock_response


@app.post("/generate-test-case")
async def generate_test_case(request: GenerationRequest):
    """The main API endpoint for generating a test case."""
    print("Orchestrator: Received request.")

    # 1. Build the MCP package
    mcp_prompt = build_mcp_package(request.requirement)

    # 2. Call the LLM with the complete context
    structured_response = call_llm_service(mcp_prompt)

    # 3. Future Step: Validate the response against the schema
    # 4. Future Step: Publish the JSON to a RabbitMQ message queue

    print("Orchestrator: Test case generated successfully.")
    return structured_response


@app.get("/")
def read_root():
    return {"message": "iQAP AI Orchestrator is running."}
