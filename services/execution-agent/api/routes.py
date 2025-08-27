import logging
from fastapi import APIRouter, HTTPException
from core.executor import execute_single_step
from pydantic import BaseModel
from typing import Dict, Any, List
from multiprocessing import Process, Queue

logger = logging.getLogger(__name__)
router = APIRouter()

class StepExecutionRequest(BaseModel):
    db_run_id: int
    step: Dict[str, Any]
    target_url: str
    ui_blueprint: List[Dict[str, Any]]
    dataset: Dict[str, Any]
    is_live_view: bool

def process_target(queue, request):
    """This function runs in the new process."""
    result = execute_single_step(request)
    queue.put(result)

@router.post("/execute-step")
def execute_step_endpoint(request: StepExecutionRequest):
    """
    Receives a single step, executes it in a separate process to ensure
    complete isolation from the asyncio event loop, and returns the result.
    """
    logger.info(f"Spawning new process for step: {request.step}")
    
    try:
        # A Queue is used to get the return value from the separate process
        result_queue = Queue()

        # Create and start the process
        process = Process(target=process_target, args=(result_queue, request))
        process.start()
        process.join(timeout=120) # Wait for the process to finish, with a timeout

        if process.is_alive():
            process.terminate()
            raise HTTPException(status_code=500, detail="Step execution timed out.")

        # Get the result from the queue
        result = result_queue.get()
        return result

    except Exception as e:
        logger.error(f"Error managing execution process: {e}", exc_info=True)
        return {
            "status": "fail",
            "new_url": request.target_url,
            "reason": f"Agent process management Error: {str(e)}"
        }