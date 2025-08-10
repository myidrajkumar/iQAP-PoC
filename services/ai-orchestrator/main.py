import os
import pika
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# Initialize the FastAPI app
app = FastAPI()

# --- RabbitMQ Configuration ---
RABBITMQ_HOST = 'rabbitmq'
RABBITMQ_USER = os.getenv('RABBITMQ_DEFAULT_USER', 'rabbit_user')
RABBITMQ_PASS = os.getenv('RABBITMQ_DEFAULT_PASS', 'rabbit_password')
credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerationRequest(BaseModel):
    requirement: str

def publish_to_rabbitmq(message: dict):
    """Publishes a message to the RabbitMQ queue."""
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
        channel = connection.channel()
        channel.queue_declare(queue='test_generation_queue', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='test_generation_queue',
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ))
        connection.close()
        print(f" [x] Sent job to RabbitMQ: {message}")
    except pika.exceptions.AMQPConnectionError as e:
        print(f"ERROR: Could not connect to RabbitMQ: {e}")
        raise HTTPException(status_code=503, detail="Could not connect to the messaging service.")


@app.post("/generate-test-case")
async def generate_test_case(request: GenerationRequest):
    """
    Receives a requirement, simulates MCP/LLM, and publishes a job to RabbitMQ.
    """
    print("Orchestrator: Received request.")
    
    # In a real system, this is where you build the MCP and call the LLM.
    # For now, we use the same mock response as the PoC.
    mock_test_case = {
        "test_case_id": "TC-LOGIN-001",
        "objective": request.requirement,
        "steps": [
            {"step": 1, "action": "ENTER_TEXT", "target_element": "Username_Input", "data": "[VALID_USERNAME]"},
            {"step": 2, "action": "ENTER_TEXT", "target_element": "Password_Input", "data": "[VALID_PASSWORD]"},
            {"step": 3, "action": "CLICK", "target_element": "Login_Button"}
        ]
    }
    
    # Publish the generated test case to the queue for processing
    publish_to_rabbitmq(mock_test_case)
    
    return {"message": "Test Case Generation Job Published!", "job_details": mock_test_case}

@app.get("/")
def read_root():
    return {"message": "iQAP AI Orchestrator v1.0 is running."}