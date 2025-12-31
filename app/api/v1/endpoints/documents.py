"""
📚 Document Management Endpoint
CRUD operations cho tài liệu đã embedding trong Vector DB
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import logging

from app.services.rag.rag_service import rag_service
from app.core.exceptions import VectorDBError, BadRequestException

logger = logging.getLogger(__name__)

router = APIRouter()


# ============= SCHEMAS =============

class DocumentResponse(BaseModel):
    """Response schema cho document"""
    id: str
    filename: str
    source: str
    page: Optional[int] = None
    preview: str
    chunk_count: int = 1
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Response schema cho danh sách documents"""
    total: int
    total_chunks: int
    documents: List[DocumentResponse]


class DocumentDeleteResponse(BaseModel):
    """Response schema cho delete operation"""
    status: str
    message: str
    deleted_chunks: int


# ============= ENDPOINTS =============

@router.get("/", response_model=DocumentListResponse)
async def list_documents():
    """
    📋 GET /api/v1/documents
    Hiển thị danh sách tất cả tài liệu đã embedding
    
    Returns:
        - total: Tổng số tài liệu (files)
        - total_chunks: Tổng số chunks trong DB
        - documents: List tài liệu với metadata
    """
    try:
        result = rag_service.get_all_documents()
        
        return DocumentListResponse(
            total=result["total"],
            total_chunks=result["total_chunks"],
            documents=result["documents"]
        )
    except VectorDBError as e:
        logger.error(f"Vector DB error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve documents from database"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.get("/search", response_model=DocumentListResponse)
async def search_documents(filename: str):
    """
    🔍 GET /api/v1/documents/search?filename=Quy_che.pdf
    Tìm kiếm tài liệu theo tên file
    
    Args:
        filename: Tên file cần tìm (partial match)
        
    Returns:
        DocumentListResponse: Danh sách tài liệu khớp
    """
    try:
        if not filename or not filename.strip():
            raise HTTPException(
                status_code=400,
                detail="Filename parameter is required"
            )
        
        docs = rag_service.search_documents_by_filename(filename)
        
        return DocumentListResponse(
            total=len(docs),
            total_chunks=sum(doc["chunk_count"] for doc in docs),
            documents=docs
        )
        
    except VectorDBError as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Search operation failed"
        )
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.delete("/source/{filename}", response_model=DocumentDeleteResponse)
async def delete_document_by_filename(filename: str):
    """
    🗑️ DELETE /api/v1/documents/source/{filename}
    Xóa TẤT CẢ chunks của 1 file khỏi Vector DB
    
    Args:
        filename: Tên file cần xóa (exact match)
        
    Returns:
        DocumentDeleteResponse: Thông tin xóa thành công
    """
    try:
        if not filename or not filename.strip():
            raise HTTPException(
                status_code=400,
                detail="Filename is required"
            )
        
        deleted_count = rag_service.delete_document_by_source(filename)
        
        if deleted_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{filename}' not found"
            )
        
        return DocumentDeleteResponse(
            status="success",
            message=f"Document '{filename}' deleted successfully",
            deleted_chunks=deleted_count
        )
        
    except HTTPException:
        raise
    except VectorDBError as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete document"
        )
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.delete("/", response_model=DocumentDeleteResponse)
async def clear_all_documents():
    """
    🗑️ DELETE /api/v1/documents
    Xóa TẤT CẢ tài liệu (Clear Vector DB)
    ⚠️ CẢNH BÁO: Không thể hoàn tác!
    
    Returns:
        DocumentDeleteResponse: Thông tin xóa thành công
    """
    try:
        result = rag_service.reset_db()
        
        return DocumentDeleteResponse(
            status="success",
            message="All documents cleared successfully",
            deleted_chunks=0  # reset_db không trả về số lượng
        )
        
    except VectorDBError as e:
        logger.error(f"Reset DB failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to clear database"
        )
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.get("/stats")
async def get_statistics():
    """
    📊 GET /api/v1/documents/stats
    Lấy thống kê về vector database
    
    Returns:
        {
            "total_files": int,
            "total_chunks": int,
            "storage_path": str
        }
    """
    try:
        stats = rag_service.get_database_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve statistics"
        )
