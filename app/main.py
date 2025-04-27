import logging
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.api import api_router
from app.core.config import settings
from app.services.s3 import s3_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
    )

    # Set all CORS enabled origins
    if settings.BACKEND_CORS_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Include API router
    application.include_router(api_router, prefix=settings.API_V1_STR)

    # Global exception handler
    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> Any:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(exc)}"},
        )

    return application


app = create_application()


@app.on_event("startup")
async def startup_event():
    # Initialize services that need setup
    logger.info("Checking AWS S3 connection...")
    if s3_service.check_bucket_exists():
        logger.info(f"S3 bucket '{settings.AWS_S3_BUCKET}' is accessible")
    else:
        logger.warning(f"S3 bucket '{settings.AWS_S3_BUCKET}' does not exist or is not accessible")
        # Try to create the bucket
        if s3_service.create_bucket_if_not_exists():
            logger.info(f"Created S3 bucket '{settings.AWS_S3_BUCKET}'")
        else:
            logger.error(f"Failed to create S3 bucket '{settings.AWS_S3_BUCKET}'")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)