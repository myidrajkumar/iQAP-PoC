import logging
from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from schemas.test_case import JourneyRequest
from services import agent_service
import httpx
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/start-test-journey")
async def start_test_journey_endpoint(
    request: JourneyRequest,
    background_tasks: BackgroundTasks
):
    """
    Receives a test objective, creates an initial DB record, 
    and starts the agentic workflow in the background.
    """
    logger.info("Received request to START test journey for URL: %s", request.target_url)
    
    # 1. Create the initial 'RUNNING' record in the reporting service
    try:
        # Convert Pydantic models to a JSON-serializable list of dictionaries
        parameters_dict = [p.model_dump() for p in request.parameters] if request.parameters else None
        
        initial_payload = {
            "objective": request.objective,
            "test_case_id": "AGENTIC_RUN",
            "parameters": parameters_dict # Use the converted dictionary
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{settings.REPORTING_SERVICE_URL}/results", json=initial_payload)
            response.raise_for_status()
            new_run_record = response.json()
            db_run_id = new_run_record.get("id")
            if not db_run_id:
                raise HTTPException(status_code=500, detail="Failed to create initial run record.")

    except Exception as e:
        logger.error(f"Could not create initial test record: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Reporting service unavailable or failed to create record.")

    # 2. Add the agentic journey to run in the background
    journey_request_data = request.model_dump()
    journey_request_data["db_run_id"] = db_run_id
    
    background_tasks.add_task(agent_service.run_agent_journey, journey_request_data)

    # 3. Return the initial record immediately to the frontend
    return new_run_record