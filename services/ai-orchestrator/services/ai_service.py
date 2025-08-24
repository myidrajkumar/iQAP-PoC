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
            logger.critical(
                "CRITICAL ERROR: GOOGLE_API_KEY is not set. AI Service will use fallback."
            )
            return
        try:
            genai.configure(api_key=api_key)
            generation_config = {"temperature": temperature}
            self.model = genai.GenerativeModel(
                model_name, generation_config=generation_config
            )
            logger.info("Successfully configured Gemini Pro model : %s", model_name)
        except Exception as e:
            logger.critical(
                f"CRITICAL ERROR: Failed to configure Gemini API. Error: {e}"
            )

    def generate_test_case(self, requirement: str, ui_blueprint: str) -> Dict[str, Any]:
        """
        Generates a test case JSON from a business requirement and UI blueprint.

        Returns a fallback mock test case if the AI model is not configured or if the API call fails.
        """
        if not self.model:
            logger.warning("Gemini model not configured. Using fallback.")
            return self._get_fallback_test_case()

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
                logger.warning(
                    "Gemini response was valid JSON but missed required keys. Using fallback."
                )
                return self._get_fallback_test_case()

        except Exception as e:
            logger.warning(f"Gemini API call or parsing failed: {e}. Using fallback.")
            return self._get_fallback_test_case()

    def _build_prompt(self, requirement: str, ui_blueprint: str) -> str:
        """Constructs the prompt to be sent to the Gemini model."""
        return f"""
        You are a highly precise JSON generation machine. Your only function is to convert a user's requirement and a UI blueprint into a structured JSON test case.

        **CRITICAL RULES:**
        1.  **Mandatory Keys:** The final JSON object MUST contain these exact top-level keys: `test_case_id`, `objective`, `parameters`, `steps`.
        2.  **Key Naming:** Do NOT use variations like `id` or `test_id`. You MUST use `test_case_id`.
        3.  **Content Source:** Base the test steps EXCLUSIVELY on the provided "Business Requirement".
        4.  **Element Mapping:** Use the "UI Blueprint" to find the correct `logical_name` for each element in the `steps`. This is the most important mapping.
        5.  **Action Types:** The value for the `action` key in each step MUST be one of these three strings ONLY: "ENTER_TEXT", "CLICK", "VERIFY_ELEMENT_VISIBLE".
        6.  **Parameter Matching:** Any `logical_name` used in a step that requires data (like "ENTER_TEXT") MUST have a corresponding key-value pair in the `data` object inside the `parameters` array.
        7.  **Output Format:** You MUST return ONLY the raw JSON object. Do not include any explanatory text, markdown formatting like ```json, or any other characters before or after the JSON structure.

        ---
        **GOOD JSON EXAMPLE:**
        {{
            "test_case_id": "TC_LOGIN_VALID",
            "objective": "Verify a user can log in with valid credentials.",
            "parameters": [
                {{
                    "dataset_name": "valid_credentials",
                    "data": {{
                        "Username": "standard_user",
                        "Password": "secret_sauce"
                    }}
                }}
            ],
            "steps": [
                {{
                    "step": 1,
                    "action": "ENTER_TEXT",
                    "target_element": "Username",
                    "data_key": "Username"
                }},
                {{
                    "step": 2,
                    "action": "ENTER_TEXT",
                    "target_element": "Password",
                    "data_key": "Password"
                }},
                {{
                    "step": 3,
                    "action": "CLICK",
                    "target_element": "Login"
                }}
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

    def _get_fallback_test_case(self) -> Dict[str, Any]:
        """Provides a reliable fallback test case."""
        return {
            "test_case_id": "TC001_FALLBACK",
            "objective": "Verify a user can log in with valid credentials.",
            "parameters": [
                {
                    "dataset_name": "valid_credentials",
                    "data": {"user-name": "standard_user", "password": "secret_sauce"},
                }
            ],
            "steps": [
                {
                    "step": 1,
                    "action": "ENTER_TEXT",
                    "target_element": "user-name",
                    "data_key": "user-name",
                },
                {
                    "step": 2,
                    "action": "ENTER_TEXT",
                    "target_element": "password",
                    "data_key": "password",
                },
                {
                    "step": 3,
                    "action": "CLICK",
                    "target_element": "login-button",
                    "verifications": {"element_to_verify": "inventory_container"},
                },
            ],
        }


# Create a single instance of the AI service to be reused
ai_service = AIService(
    api_key=settings.GOOGLE_API_KEY,
    model_name=settings.GEMINI_MODEL_NAME,
    temperature=settings.GEMINI_TEMPERATURE,
)
