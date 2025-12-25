from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import List

from app.schemas.rag import QueryRequest, SourcesResponse
from app.services.rag.rag_service import rag_service

router = APIRouter()

@router.post("/ingest", summary="Upload Documents (PDF/Docx)")
async def ingest_documents(files: List[UploadFile] = File(...)):
    """
    Upload and Index documents.
    """
    return await rag_service.ingest_files(files)

@router.post("/chat-stream", summary="Chat with AI (Streaming)")
async def chat_stream(request: QueryRequest):
    """
    Returns Server-Sent Events (SSE) stream.
    """
    return StreamingResponse(
        rag_service.query_rag_stream(request.question),
        media_type="text/event-stream"
        # media_type="application/x-ndjson"
    )

@router.post("/get-sources", response_model=SourcesResponse, summary="Get Reference Docs")
async def get_sources(request: QueryRequest):
    """
    Get documents used for the answer.
    """
    sources = rag_service.get_sources(request.question)
    return {"sources": sources}

@router.delete("/reset", summary="Reset Database (Dev Only)")
async def reset_database():
    return rag_service.reset_db()