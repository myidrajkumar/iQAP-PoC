"""AI Orchestrator API Routes"""

import json
import logging
from fastapi import APIRouter, HTTPException, Body
from schemas.test_case import GenerationRequest, GenerationResponse
from services import ai_service, discovery_service, messaging_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def read_root():
    """Root endpoint to check if the service is running."""
    return {"message": "iQAP AI Orchestrator is running."}


# --- MODIFIED ENDPOINT ---
# It now returns the full test case JSON instead of just a message.
@router.post("/generate-test-case", response_model=dict)
async def generate_test_case(request: GenerationRequest):
    """
    Generates a test case and returns it for user review.
    Orchestrates calls to the discovery service and AI service.
    """
    logger.info("Received request to GENERATE test for URL: %s", request.target_url)

    try:
        # 1. Get UI blueprint from the discovery service
        ui_blueprint_string = await discovery_service.get_ui_blueprint(
            request.target_url
        )
        ui_blueprint_json = json.loads(ui_blueprint_string)

        # 2. Generate the test case using the AI service
        generated_test_case = ai_service.ai_service.generate_test_case(
            request.requirement, ui_blueprint_string
        )

        # 3. Augment the test case with additional required data
        generated_test_case["ui_blueprint"] = ui_blueprint_json.get("elements", [])
        generated_test_case["target_url"] = request.target_url

        # 4. Return the generated test case to the frontend for review
        # The publishing step is now handled by a separate endpoint.
        logger.info(
            "Successfully generated test case. Returning to frontend for review."
        )
        return generated_test_case

    except HTTPException as e:
        # Re-raise HTTP exceptions to let FastAPI handle them
        raise e
    except Exception as e:
        logger.fatal(f"FATAL ERROR in generation process: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )


# --- NEW ENDPOINT ---
# This endpoint receives the final (potentially user-approved) test case and publishes it.
@router.post("/publish-test-case", response_model=GenerationResponse)
async def publish_test_case(test_case: dict = Body(...)):
    """
    Receives a test case JSON and publishes it to the execution queue.
    """
    logger.info(
        "Received request to PUBLISH test case ID: %s", test_case.get("test_case_id")
    )
    try:
        messaging_service.publish_to_rabbitmq(test_case)
        return GenerationResponse(
            message="Test Case Execution Job Published!",
            test_case_id=test_case.get("test_case_id"),
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to publish test case to RabbitMQ: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to publish job.")
