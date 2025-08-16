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

    # RabbitMQ Configuration
    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST")
    RABBITMQ_DEFAULT_USER: str = os.getenv("RABBITMQ_DEFAULT_USER")
    RABBITMQ_DEFAULT_PASS: str = os.getenv("RABBITMQ_DEFAULT_PASS")
    RABBITMQ_QUEUE: str = "test_generation_queue"

    # Service URLs
    DISCOVERY_SERVICE_URL: str = os.getenv("DISCOVERY_SERVICE_URL")

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
    settings.RABBITMQ_HOST = "iqap-rabbitmq"
