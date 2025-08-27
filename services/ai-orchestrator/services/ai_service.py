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
        Analyzes the objective and history to decide the next action (tool use).
        """
        if not self.model:
            raise RuntimeError("Gemini model is not configured.")

        prompt = self._build_agent_prompt(objective, history, ui_blueprint)

        try:
            logger.info("Calling Gemini API for agent planning...")
            response = self.model.generate_content(prompt)
            cleaned_response = (
                response.text.replace("```json", "").replace("```", "").strip()
            )
            
            # The response should be a JSON object representing the agent's thought process and next action
            result = json.loads(cleaned_response)
            
            if "action" in result and "parameters" in result:
                logger.info(f"Gemini planned next action: {result['action']}")
                return result
            else:
                logger.error("Gemini response was valid JSON but missed required action/parameters keys.")
                raise ValueError("AI failed to generate a valid action plan.")

        except Exception as e:
            logger.warning(f"Gemini API call or parsing failed: {e}. Raising error.")
            raise ValueError(f"An error occurred during AI planning: {e}")

    def _build_agent_prompt(self, objective: str, history: list, ui_blueprint: str = None) -> str:
        """Constructs the ReAct (Reason+Act) style prompt for the agent."""
        
        history_str = "\n".join(f"- {item}" for item in history)
        blueprint_str = f"""
        **Current UI Blueprint:**
        ```json
        {ui_blueprint if ui_blueprint else "No UI blueprint available. You must use the 'discover' tool."}
        ```
        """

        return f"""
        You are an autonomous QA Agent. Your goal is to test a web application based on a given objective.
        You operate in a loop: you think, you choose a tool, and you observe the result.

        **Objective:** "{objective}"

        **Tools Available:**
        1. `discover`: Use this when you are on a new page or need to understand the available UI elements.
           - Parameters: {{ "url": "The URL of the page to discover" }}
        2. `execute_step`: Use this to perform an action on a UI element you have already discovered.
           - Parameters: {{ "step": {{ "action": "CLICK" | "ENTER_TEXT" | "VISUAL_VALIDATION", "target_element": "The logical_name of the element", "data_key": "(optional) The key for the data to use" }} }}
        3. `finish`: Use this when you have successfully completed all steps required by the objective.
           - Parameters: {{ "status": "success", "reason": "A brief summary of why the test is complete." }}
        4. `fail`: Use this if you cannot proceed or determine that the objective cannot be met.
           - Parameters: {{ "reason": "A clear explanation of why you are failing the test." }}

        **History of Actions Taken:**
        {history_str if history_str else "No actions taken yet."}

        {blueprint_str if ui_blueprint else ""}

        **Your Task:**
        Based on the objective and the history, think step-by-step and then decide on the single next tool to use.
        Your output MUST be a single, raw JSON object with your thought process and the chosen action.

        **Example JSON Output:**
        {{
          "thought": "I have just landed on the inventory page. The objective requires me to log out. I need to find the logout button. I don't see it in the current blueprint, but I see a 'Burger Menu' button which likely contains the logout link. I will click the menu button first.",
          "action": "execute_step",
          "parameters": {{
            "step": {{
              "action": "CLICK",
              "target_element": "Burger Menu"
            }}
          }}
        }}

        Now, generate the JSON for your next action.
        """


# Create a single instance of the AI service to be reused
ai_service = AIService(
    api_key=settings.GOOGLE_API_KEY,
    model_name=settings.GEMINI_MODEL_NAME,
    temperature=settings.GEMINI_TEMPERATURE,
)