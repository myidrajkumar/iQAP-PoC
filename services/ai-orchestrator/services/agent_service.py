import logging
import httpx
from services.ai_service import ai_service
from core.config import settings

logger = logging.getLogger(__name__)

MAX_STEPS = 15 # Safety break to prevent infinite loops

async def run_agent_journey(journey_request: dict):
    """
    Manages the agentic loop: Think, Act, Observe.
    """
    objective = journey_request.get("objective")
    target_url = journey_request.get("target_url")
    db_run_id = journey_request.get("db_run_id")
    parameters = journey_request.get("parameters", [{}])
    dataset = parameters[0].get("data", {}) if parameters else {}
    
    history = []
    current_url = target_url
    ui_blueprint = None

    for i in range(MAX_STEPS):
        try:
            logger.info(f"--- Agent Step {i+1} ---")
            
            # 1. THINK: Plan the next step using the AI
            plan = ai_service.plan_next_step(objective, history, ui_blueprint)
            action = plan.get("action")
            parameters = plan.get("parameters")
            thought = plan.get("thought", "No thought provided.")
            history.append(f"Thought: {thought}")

            # 2. ACT: Execute the planned action (use a tool)
            if action == "discover":
                if i == 0:
                    discovery_url = target_url
                else:
                    discovery_url = parameters.get("url", current_url)
                
                history.append(f"Action: Discovering UI at {discovery_url}")
                async with httpx.AsyncClient() as client:
                    response = await client.post(settings.DISCOVERY_SERVICE_URL, json={"url": discovery_url}, timeout=60.0)
                    response.raise_for_status()
                    ui_blueprint = response.json()
                current_url = discovery_url # Update current URL after discovery
                history.append(f"Observation: Discovered {len(ui_blueprint.get('elements', []))} elements.")

            elif action == "execute_step":
                step_details = parameters.get("step")
                history.append(f"Action: Executing step -> {step_details['action']} on '{step_details['target_element']}'")
                
                payload = {
                    "db_run_id": db_run_id,
                    "step": step_details,
                    "target_url": current_url,
                    "ui_blueprint": ui_blueprint.get("elements", []),
                    "dataset": dataset,
                    "is_live_view": journey_request.get("is_live_view", False)
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(settings.EXECUTION_AGENT_URL, json=payload, timeout=120.0)
                    response.raise_for_status()
                    execution_result = response.json()

                if execution_result.get("status") == "success":
                    current_url = execution_result.get("new_url", current_url)
                    history.append(f"Observation: Step successful. Now at URL: {current_url}")
                    # After a successful action, we must re-discover the UI
                    ui_blueprint = None
                else:
                    reason = execution_result.get("reason", "Unknown execution error.")
                    history.append(f"Observation: Step failed! Reason: {reason}")
                    await update_final_status(db_run_id, "FAIL", reason, history)
                    return

            elif action == "finish":
                reason = parameters.get("reason", "Objective completed.")
                history.append(f"Action: Finishing test with status SUCCESS.")
                await update_final_status(db_run_id, "PASS", reason, history)
                return
            
            elif action == "fail":
                reason = parameters.get("reason", "Agent determined failure.")
                history.append(f"Action: Failing test.")
                await update_final_status(db_run_id, "FAIL", reason, history)
                return

        except Exception as e:
            logger.error(f"FATAL ERROR in agent loop: {e}", exc_info=True)
            await update_final_status(db_run_id, "FAIL", f"Orchestrator Error: {e}", history)
            return

    # If the loop finishes due to MAX_STEPS
    await update_final_status(db_run_id, "FAIL", "Agent exceeded maximum step limit.", history)


async def update_final_status(db_run_id: int, status: str, reason: str, history: list):
    """
    Updates the final status of the test run in the reporting service.
    """
    logger.info(f"Updating final status for run {db_run_id}: {status}. Reason: {reason}")
    try:
        # We can enhance this later to save the full history
        payload = {"status": status, "failure_reason": reason}
        async with httpx.AsyncClient() as client:
            await client.put(f"{settings.REPORTING_SERVICE_URL}/results/{db_run_id}/final-status", json=payload, timeout=30.0)
    except Exception as e:
        logger.error(f"Failed to update final status for run {db_run_id}: {e}")