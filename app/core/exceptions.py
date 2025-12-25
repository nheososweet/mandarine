from typing import Any, Dict, Optional
from fastapi import status

class BaseAPIException(Exception):
    """
    Class cha cho tất cả các lỗi Custom trong hệ thống.
    Giúp chuẩn hóa format lỗi trả về cho Frontend.
    """
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)

# =========================================================
# 1. COMMON ERRORS (Lỗi thường gặp ở mọi dự án)
# =========================================================

class BadRequestException(BaseAPIException):
    """Lỗi 400: Yêu cầu không hợp lệ (Logic sai, thiếu tham số...)"""
    def __init__(self, message: str = "Bad Request", details: dict = None):
        super().__init__(
            message=message,
            code="BAD_REQUEST",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )

class UnauthorizedException(BaseAPIException):
    """Lỗi 401: Chưa đăng nhập hoặc Token hết hạn"""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

class PermissionDeniedException(BaseAPIException):
    """Lỗi 403: Không có quyền truy cập (Đã đăng nhập nhưng không đủ quyền)"""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=status.HTTP_403_FORBIDDEN
        )

class NotFoundException(BaseAPIException):
    """Lỗi 404: Không tìm thấy tài nguyên"""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )

# =========================================================
# 2. RAG DOMAIN ERRORS (Lỗi đặc thù của dự án RAG)
# =========================================================

class FileProcessingError(BaseAPIException):
    """
    Lỗi 422: Xảy ra khi file upload bị lỗi, không đọc được,
    hoặc format không hỗ trợ.
    """
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            code="FILE_PROCESSING_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details
        )

class VectorDBError(BaseAPIException):
    """
    Lỗi 503: Xảy ra khi ChromaDB, Pinecone hoặc Embedding Service
    bị lỗi kết nối hoặc không lưu được dữ liệu.
    """
    def __init__(self, message: str):
        super().__init__(
            message=f"Vector Database Error: {message}",
            code="VECTOR_DB_ERROR",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

class LLMGenerationError(BaseAPIException):
    """
    Lỗi 502: Xảy ra khi gọi OpenAI/Gemini API bị lỗi 
    (Hết tiền, Timeout, API Key sai...)
    """
    def __init__(self, message: str, provider: str = "AI_PROVIDER"):
        super().__init__(
            message=f"Error from {provider}: {message}",
            code="LLM_PROVIDER_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY
        )