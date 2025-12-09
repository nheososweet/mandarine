from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    """
    Health check endpoint
    """
    return {
        "message": "Welcome to Student Management API",
        "docs": "/docs",
        "version": "1.0.0"
    }