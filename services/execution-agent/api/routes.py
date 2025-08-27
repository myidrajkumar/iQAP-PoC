import logging
from fastapi import APIRouter, HTTPException
from core.executor import execute_single_step
from pydantic import BaseModel
from typing import Dict, Any, List

logger = logging.getLogger(__name__)
router = APIRouter()

class StepExecutionRequest(BaseModel):
    db_run_id: int
    step: Dict[str, Any]
    target_url: str
    ui_blueprint: List[Dict[str, Any]]
    dataset: Dict[str, Any]
    is_live_view: bool

@router.post("/execute-step")
async def execute_step_endpoint(request: StepExecutionRequest):
    """
    Receives a single step, executes it, and returns the result.
    """
    logger.info(f"Executing step for run_id {request.db_run_id}: {request.step}")
    try:
        result = execute_single_step(request)
        return result
    except Exception as e:
        logger.error(f"Error during step execution: {e}", exc_info=True)
        # Return a failure object consistent with the executor's return type
        return {
            "status": "fail",
            "new_url": request.target_url,
            "reason": f"Agent Error: {str(e)}"
        }