"""Core configuration module for the AI Orchestrator service."""

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """
    Pydantic-based settings management for the application.
    Reads environment variables and provides them as typed attributes.
    """

    # AI Model Configuration
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", "")
    GEMINI_TEMPERATURE: float = os.getenv("GEMINI_TEMPERATURE", "0.0")

    # Service URLs
    DISCOVERY_SERVICE_URL: str = os.getenv("DISCOVERY_SERVICE_URL")
    EXECUTION_AGENT_URL: str = os.getenv("EXECUTION_AGENT_URL")
    REPORTING_SERVICE_URL: str = os.getenv("REPORTING_SERVICE_URL")

    # CORS Configuration
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # Environment Configuration
    IS_DOCKER: bool = os.environ.get("DOCKER_ENV") == "true"

    class Config:
        """Pydantic configuration for environment variable loading."""

        case_sensitive = True


# Create a single settings instance to be used throughout the application
settings = Settings()

# Dynamically adjust service URLs if running in Docker
if settings.IS_DOCKER:
    settings.DISCOVERY_SERVICE_URL = "http://discovery-service:8001/discover"
    settings.EXECUTION_AGENT_URL = "http://execution-agent:8004/execute-step"
    settings.REPORTING_SERVICE_URL = "http://reporting-service:8002"