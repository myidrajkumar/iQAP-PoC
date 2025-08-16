"""AI Orchestrator API Routes"""

import json
import logging
from fastapi import APIRouter, HTTPException
from schemas.test_case import GenerationRequest, GenerationResponse
from services import ai_service, discovery_service, messaging_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def read_root():
    """Root endpoint to check if the service is running."""
    return {"message": "iQAP AI Orchestrator is running."}


@router.post("/generate-test-case", response_model=GenerationResponse)
async def generate_test_case(request: GenerationRequest):
    """
    Main endpoint to generate a test case.
    Orchestrates calls to the discovery service, AI service, and messaging service.
    """
    logger.info("Received request for URL: %s", request.target_url)

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

        # 4. Publish the job to RabbitMQ
        messaging_service.publish_to_rabbitmq(generated_test_case)

        return GenerationResponse(
            message="Test Case Generation Job Published!",
            test_case_id=generated_test_case.get("test_case_id"),
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions to let FastAPI handle them
        raise e
    except Exception as e:
        logger.fatal(f"FATAL ERROR in generation process: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )
