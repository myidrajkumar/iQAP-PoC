import logging
import httpx
from services.ai_service import ai_service
from core.config import settings

logger = logging.getLogger(__name__)

MAX_THINKING_STEPS = 10 # This is the outer loop limit

async def run_agent_journey(journey_request: dict):
    """
    Manages the agentic loop with multi-step planning and stateful discovery.
    """
    objective = journey_request.get("objective")
    target_url = journey_request.get("target_url")
    db_run_id = journey_request.get("db_run_id")
    parameters = journey_request.get("parameters", [{}])
    dataset = parameters[0].get("data", {}) if parameters else {}
    
    history = []
    current_url = target_url
    ui_blueprint = None
    final_visual_status = "N/A"

    for i in range(MAX_THINKING_STEPS):
        try:
            logger.info(f"--- Agent Thinking Cycle {i+1} ---")
            
            # 1. THINK: Get the next multi-step plan from the AI
            plan = ai_service.plan_next_step(objective, history, ui_blueprint)
            history.append(f"Plan {i+1}: {plan.get('thought')}")
            
            if not plan.get("steps"):
                raise ValueError("AI plan contained no steps.")

            for step_plan in plan["steps"]:
                action = step_plan.get("action")
                action_params = step_plan.get("parameters")

                if action == "discover":
                    history.append(f"Action: Discovering UI at {current_url}")
                    async with httpx.AsyncClient() as client:
                        response = await client.post(settings.DISCOVERY_SERVICE_URL, json={"url": current_url}, timeout=60.0)
                        response.raise_for_status()
                        ui_blueprint = response.json()
                    history.append(f"Observation: Discovered {len(ui_blueprint.get('elements', []))} elements.")
                
                elif action == "execute_step":
                    step_details = action_params
                    history.append(f"Action: Executing step -> {step_details['action']} on '{step_details['target_element']}'")
                    
                    if not ui_blueprint:
                        raise ValueError("Agent tried to execute a step without a UI blueprint.")

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
                        # --- MODIFICATION: Update state from the rich execution result ---
                        current_url = execution_result.get("new_url", current_url)
                        ui_blueprint = execution_result.get("new_blueprint") # Update memory with the new view
                        history.append(f"Observation: Step successful. Now at URL: {current_url}. Found {len(ui_blueprint.get('elements',[]))} new elements.")
                    else:
                        reason = execution_result.get("reason", "Unknown execution error.")
                        history.append(f"Observation: Step failed! Reason: {reason}")
                        await update_final_status(db_run_id, "FAIL", "FAIL", reason, history)
                        return
                
                elif action == "finish":
                    reason = action_params.get("reason", "Objective completed.")
                    history.append(f"Action: Finishing test with status SUCCESS.")
                    final_visual_status = "PASS" if final_visual_status == "N/A" else final_visual_status
                    await update_final_status(db_run_id, "PASS", final_visual_status, reason, history)
                    return

        except Exception as e:
            logger.error(f"FATAL ERROR in agent loop: {e}", exc_info=True)
            await update_final_status(db_run_id, "FAIL", "FAIL", f"Orchestrator Error: {e}", history)
            return

    await update_final_status(db_run_id, "FAIL", "FAIL", "Agent exceeded maximum thinking steps.", history)


async def update_final_status(db_run_id: int, status: str, visual_status: str, reason: str, history: list):
    # This function is unchanged
    logger.info(f"Updating final status for run {db_run_id}: {status}, Visual: {visual_status}. Reason: {reason}")
    try:
        payload = {"status": status, "visual_status": visual_status, "failure_reason": reason}
        async with httpx.AsyncClient() as client:
            await client.put(f"{settings.REPORTING_SERVICE_URL}/results/{db_run_id}/final-status", json=payload, timeout=30.0)
    except Exception as e:
        logger.error(f"Failed to update final status for run {db_run_id}: {e}")