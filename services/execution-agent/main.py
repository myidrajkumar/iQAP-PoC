from fastapi import FastAPI
from api import routes
from core.config import settings

app = FastAPI(
    title="iQAP Execution Agent",
    description="A service to execute single test steps via API calls.",
    version="1.0.0",
)

app.include_router(routes.router)