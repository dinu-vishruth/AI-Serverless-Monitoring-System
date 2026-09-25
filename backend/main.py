"""
FastAPI Main Application.
Provides REST API endpoints for the AI-Driven Serverless Event Monitoring System.
Runs locally or deployed to AWS Lambda via Mangum.
"""

import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
try:
    from mangum import Mangum
except ImportError:
    Mangum = None

from backend.api.routes.services import router as services_router
from backend.api.routes.monitoring import router as monitoring_router
from backend.api.routes.incidents import router as incidents_router
from backend.api.routes.ai import router as ai_router
from backend.api.routes.metrics import router as metrics_router
from backend.utils.config import get_settings
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger("fastapi_app")

app = FastAPI(
    title="AI-Driven Serverless Event Monitoring System API",
    description="Intelligent health checking, anomaly detection, risk analysis, and LLM-assisted incident explainability.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_and_log(request: Request, call_next):
    """Logs HTTP request lifecycle and timing."""
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    return response


# Include Routers with /api/v1 prefix
app.include_router(services_router, prefix="/api/v1")
app.include_router(monitoring_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
def health_check():
    """Liveness probe endpoint."""
    return {
        "status": "HEALTHY",
        "timestamp": time.time(),
        "environment": settings.environment,
        "ai_provider": settings.ai_provider,
        "model": settings.ml_model_type,
    }


@app.get("/", tags=["System"])
def root():
    """Root redirect / system metadata."""
    return {
        "system": "AI-Driven Serverless Event Monitoring System",
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0",
    }


# Mangum handler for AWS Lambda (API Gateway HTTP/REST proxy)
handler = Mangum(app, lifespan="off") if Mangum else None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
