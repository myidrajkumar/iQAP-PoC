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


@router.post("/generate-test-case", response_model=dict)
async def generate_test_case_endpoint(request: GenerationRequest):
    """Generates a test case and returns it for user review."""
    logger.info("Received request to GENERATE test for URL: %s", request.target_url)
    try:
        ui_blueprint_string = await discovery_service.get_ui_blueprint(
            request.target_url
        )
        ui_blueprint_json = json.loads(ui_blueprint_string)
        generated_test_case = ai_service.ai_service.generate_test_case(
            request.requirement, ui_blueprint_string
        )
        generated_test_case["ui_blueprint"] = ui_blueprint_json.get("elements", [])
        generated_test_case["target_url"] = request.target_url
        logger.info(
            "Successfully generated test case. Returning to frontend for review."
        )
        return generated_test_case
    except Exception as e:
        logger.fatal(f"FATAL ERROR in generation process: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )


@router.post("/publish-test-case", response_model=GenerationResponse)
async def publish_test_case_endpoint(test_case: dict = Body(...)):
    """Receives a test case JSON and publishes it to the test_generation_queue."""
    logger.info(
        "Received request to PUBLISH test case ID: %s", test_case.get("test_case_id")
    )
    try:
        # This service's only job is to publish the raw test case.
        # The execution-orchestrator will handle DB record creation.
        messaging_service.publish_to_rabbitmq(test_case)
        return GenerationResponse(
            message="Test Case Generation Job Published!",
            test_case_id=test_case.get("test_case_id"),
            # run_id will be created by the next service, so we don't return it here.
        )
    except Exception as e:
        logger.error(f"Failed to publish test case to RabbitMQ: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to publish job.")
