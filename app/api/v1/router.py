from fastapi import APIRouter
from app.api.v1.endpoints import students
from app.api.v1.endpoints import rag

api_router = APIRouter()

api_router.include_router(
    students.router,
    prefix="/students",
    tags=["students"]
)

api_router.include_router(
    rag.router,
    prefix="/rag",
    tags=["rag"]
)