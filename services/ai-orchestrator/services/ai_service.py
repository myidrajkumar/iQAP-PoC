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
    A service class to handle interactions with the Google Gemini Pro model.
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

    def generate_test_case(self, requirement: str, ui_blueprint: str) -> Dict[str, Any]:
        """
        Generates a test case JSON from a business requirement and UI blueprint.

        Returns a fallback mock test case if the AI model is not configured or if the API call fails.
        """
        if not self.model:
            raise RuntimeError(
                "Gemini model is not configured. Cannot generate test case."
            )

        prompt = self._build_prompt(requirement, ui_blueprint)

        try:
            logger.info("Calling Google Gemini API...")
            response = self.model.generate_content(prompt)
            cleaned_response = (
                response.text.replace("```json", "").replace("```", "").strip()
            )

            result = json.loads(cleaned_response)

            required_keys = ["test_case_id", "objective", "parameters", "steps"]
            if all(key in result for key in required_keys):
                logger.info("Gemini API call successful and response is valid.")
                return result
            else:
                logger.error("Gemini response was valid JSON but missed required keys.")
                raise ValueError("AI failed to generate a valid test case structure.")

        except Exception as e:
            logger.warning(f"Gemini API call or parsing failed: {e}. Using fallback.")
            raise ValueError(f"An error occurred during AI generation: {e}")

    def _build_prompt(self, requirement: str, ui_blueprint: str) -> str:
        """Constructs the prompt to be sent to the Gemini model."""
        return f"""
        You are a highly precise JSON generation machine. Your only function is to convert a user's requirement and a UI blueprint into a structured JSON test case.

        **CRITICAL RULES:**
        1.  **Mandatory Keys:** The final JSON object MUST contain these exact top-level keys: `test_case_id`, `objective`, `parameters`, `steps`.
        2.  **Action Types:** The value for the `action` key in each step MUST be one of these strings ONLY: "ENTER_TEXT", "CLICK", "VERIFY_ELEMENT_VISIBLE", "VISUAL_VALIDATION".
        3.  **VISUAL_VALIDATION:** Use this action after a critical step (like a login or navigating to a new page) to take a visual snapshot. The `target_element` for this action should be a descriptive name for the view, e.g., "inventory_page" or "login_screen".
        4.  **Output Format:** You MUST return ONLY the raw JSON object. Do not include any explanatory text or markdown.

        ---
        **GOOD JSON EXAMPLE:**
        {{
            "test_case_id": "TC_LOGIN_LOGOUT_VISUAL",
            "objective": "Verify a user can log in and then log out, with visual checks.",
            "parameters": [
                {{
                    "dataset_name": "valid_credentials",
                    "data": {{ "Username": "standard_user", "Password": "secret_sauce" }}
                }}
            ],
            "steps": [
                {{ "step": 1, "action": "VISUAL_VALIDATION", "target_element": "login_page_initial_view" }},
                {{ "step": 2, "action": "ENTER_TEXT", "target_element": "Username", "data_key": "Username" }},
                {{ "step": 3, "action": "ENTER_TEXT", "target_element": "Password", "data_key": "Password" }},
                {{ "step": 4, "action": "CLICK", "target_element": "Login" }},
                {{ "step": 5, "action": "VISUAL_VALIDATION", "target_element": "inventory_page_after_login" }}
            ]
        }}
        ---

        **TASK:**

        **Business Requirement:**
        {requirement}

        **UI Blueprint:**
        {ui_blueprint}

        ---
        Generate the JSON test case now.
        """


# Create a single instance of the AI service to be reused
ai_service = AIService(
    api_key=settings.GOOGLE_API_KEY,
    model_name=settings.GEMINI_MODEL_NAME,
    temperature=settings.GEMINI_TEMPERATURE,
)
