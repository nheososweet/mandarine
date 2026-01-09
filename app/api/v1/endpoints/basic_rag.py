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
    
from pydantic import BaseModel
from typing import List,Dict, Any
from app.services.rag.lightrag_bridge_service import lightrag_bridge_service

# router = APIRouter()

# --- 1. Định nghĩa Model khớp 100% với JSON FE gửi ---
class LightRAGFullRequest(BaseModel):
    query: str  # LightRAG dùng 'query', không phải 'question'
    mode: str = "mix"
    top_k: int = 40
    chunk_top_k: int = 20
    max_entity_tokens: int = 6000
    max_relation_tokens: int = 8000
    max_total_tokens: int = 30000
    only_need_context: bool = False
    only_need_prompt: bool = False
    stream: bool = False
    history_turns: int = 3
    user_prompt: str = ""
    enable_rerank: bool = True
    response_type: str = "Multiple Paragraphs"
    conversation_history: List[Dict[str, Any]] = []
    
    # Cho phép nhận thêm các field lạ nếu LightRAG update sau này
    class Config:
        extra = "allow" 

# --- 2. Update API Endpoint ---
@router.post("/references")
async def get_references_endpoint(body: LightRAGFullRequest, request: Request):
    """
    API nhận full payload từ FE.
    Chuyển tiếp sang Service để xử lý lấy data và highlight.
    """
    # Chuyển Pydantic model thành dict để xử lý
    request_data = body.model_dump()
    
    return await lightrag_bridge_service.get_references_with_highlights(request_data, request)