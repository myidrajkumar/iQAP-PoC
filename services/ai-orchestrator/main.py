from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import routes
from core.config import settings

# --- Initialize FastAPI ---
app = FastAPI(
    title="iQAP AI Orchestrator",
    description="An AI-powered service to orchestrate the generation of automated test cases.",
    version="1.0.0",
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include API Routes ---
app.include_router(routes.router, prefix="/api/v1")
