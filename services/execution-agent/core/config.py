import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    IS_DOCKER = os.environ.get("DOCKER_ENV") == "true"
    IS_LIVE_VIEW = False # This will be set per-request

    MINIO_HOST = "minio:9000" if IS_DOCKER else os.getenv("MINIO_HOST", "localhost:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER")
    MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD")
    
    REALTIME_SERVICE_URL = "http://realtime-service:8003" if IS_DOCKER else os.getenv("REALTIME_SERVICE_URL", "http://localhost:8003")

settings = Settings()