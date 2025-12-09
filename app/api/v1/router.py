from fastapi import APIRouter
from app.api.v1.endpoints import students

api_router = APIRouter()

api_router.include_router(
    students.router,
    prefix="/students",
    tags=["students"]
)