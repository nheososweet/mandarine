import os
from fastapi import APIRouter, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from typing import List

# Import schemas and services
# Ensure these paths match your project structure
from app.schemas.rag import QueryRequest
from app.services.rag.basic_rag_service import basic_rag_service

router = APIRouter()

# --- 1. Ingest Endpoint ---
@router.post("/ingest", summary="Upload Documents (PDF/Docx)")
async def ingest_documents(files: List[UploadFile] = File(...)):
    """
    Upload and Index documents into the vector database.
    """
    # Ensure the upload directory exists (Best practice: handle this in main.py or config, but valid here too)
    os.makedirs("uploads", exist_ok=True)
    
    return await basic_rag_service.ingest_files(files)


# --- 2. Chat Stream Endpoint ---
@router.post("/chat-stream", summary="Chat with AI (Streaming)")
async def chat_stream(body: QueryRequest, request: Request):
    """
    Returns Server-Sent Events (SSE) stream.
    Accepts a question and returns a streaming response.
    Passes 'request' to service to construct full URLs for static files (images).
    """
    return StreamingResponse(
        # Calling the service method with both question and request object
        basic_rag_service.query_rag_stream(body.question, request),
        media_type="text/event-stream"
    )