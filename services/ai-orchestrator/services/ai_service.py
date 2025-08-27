"""AI Service Module"""

import json
import logging
from typing import Dict, Any
import google.generativeai as genai
from core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIService:
    """
    A service class to handle interactions with the Google Gemini Pro model for agentic planning.
    """

    def __init__(self, api_key: str, model_name: str, temperature: float):
        self.model = None
        if not api_key:
            raise ValueError(
                "CRITICAL ERROR: GOOGLE_API_KEY is not set. AI Service cannot start."
            )
        try:
            genai.configure(api_key=api_key)
            generation_config = {"temperature": temperature}
            self.model = genai.GenerativeModel(
                model_name, generation_config=generation_config
            )
            logger.info("Successfully configured Gemini Pro model : %s", model_name)
        except Exception as e:
            raise RuntimeError(
                f"CRITICAL ERROR: Failed to configure Gemini API. Error: {e}"
            )

    def plan_next_step(self, objective: str, history: list, ui_blueprint: str = None) -> Dict[str, Any]:
        """
        Analyzes the objective and history to decide the next sequence of actions.
        """
        if not self.model:
            raise RuntimeError("Gemini model is not configured.")

        prompt = self._build_agent_prompt(objective, history, ui_blueprint)

        try:
            logger.info("Calling Gemini API for multi-step planning...")
            response = self.model.generate_content(prompt)
            cleaned_response = (
                response.text.replace("```json", "").replace("```", "").strip()
            )
            
            result = json.loads(cleaned_response)
            
            if "steps" in result:
                logger.info(f"Gemini planned {len(result['steps'])} steps.")
                return result
            else:
                logger.error("Gemini response was valid JSON but missed the required 'steps' key.")
                raise ValueError("AI failed to generate a valid action plan.")

        except Exception as e:
            logger.warning(f"Gemini API call or parsing failed: {e}. Raising error.")
            raise ValueError(f"An error occurred during AI planning: {e}")

    def _build_agent_prompt(self, objective: str, history: list, ui_blueprint: str = None) -> str:
        """Constructs the prompt for multi-step planning."""
        
        history_str = "\n".join(f"- {item}" for item in history)
        blueprint_str = f"""
        **Current UI Blueprint:**
        ```json
        {ui_blueprint if ui_blueprint else "No UI blueprint available. You must discover the UI first."}
        ```
        """

        return f"""
        You are an autonomous QA Agent. Your goal is to test a web application based on a given objective.
        Your task is to generate a JSON object containing a sequence of steps to perform based on the current UI.

        **CRITICAL REASONING INSTRUCTIONS:**
        1.  **Plan Sequentially:** Analyze the UI blueprint and create a list of all actions you can perform NOW on the current page to progress toward the objective.
        2.  **Stop at Navigation:** If a step involves a CLICK that will navigate to a new page, that should be the LAST step in your plan. The agent will re-discover the UI on the new page.
        3.  **Handle Hidden Elements:** If your target (e.g., "Logout") is not in the blueprint, your plan should be to click the container element (e.g., a "Menu" button) to reveal it. This click should be the only step in your plan.
        4.  **Declare Completion:** If the objective has been fully met, return a single "finish" step.
        5.  **No Blueprint?:** If no UI blueprint is available, your plan must be a single "discover" step with no parameters.

        **Objective:** "{objective}"

        **Action Types:**
        - `discover`: To scan the current page. (Parameters: {{}})
        - `execute_step`: To interact with an element. (Parameters: {{ "action": "CLICK" | "ENTER_TEXT", "target_element": "logical_name", ...}})
        - `finish`: When the entire objective is complete. (Parameters: {{"reason": "summary"}})

        **History of Plans Executed:**
        {history_str if history_str else "No plans executed yet."}

        {blueprint_str}

        **Your Task:**
        Generate a single JSON object containing a `thought` and a `steps` array for the next sequence of actions.

        **Example 1: Logging In**
        {{
          "thought": "The UI shows a login form. I can fill in the username, the password, and then click the login button. The login click will navigate, so it will be the last step.",
          "steps": [
            {{ "action": "execute_step", "parameters": {{ "action": "ENTER_TEXT", "target_element": "Username", "data_key": "Username" }} }},
            {{ "action": "execute_step", "parameters": {{ "action": "ENTER_TEXT", "target_element": "Password", "data_key": "Password" }} }},
            {{ "action": "execute_step", "parameters": {{ "action": "CLICK", "target_element": "Login" }} }}
          ]
        }}

        **Example 2: Needing to Discover**
        {{
            "thought": "I have no UI information for the current page. I must discover it first.",
            "steps": [
                {{ "action": "discover", "parameters": {{}} }}
            ]
        }}

        Now, generate the JSON for your next plan.
        """

# Create a single instance of the AI service to be reused
ai_service = AIService(
    api_key=settings.GOOGLE_API_KEY,
    model_name=settings.GEMINI_MODEL_NAME,
    temperature=settings.GEMINI_TEMPERATURE,
)