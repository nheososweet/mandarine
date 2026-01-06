from fastapi import APIRouter
from app.api.v1.endpoints import students
from app.api.v1.endpoints import rag
from app.api.v1.endpoints import documents
from app.api.v1.endpoints import basic_rag

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

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["documents"]
)

api_router.include_router(
    basic_rag.router,
    prefix="/basic-rag",
    tags=["basic-rag"]
)