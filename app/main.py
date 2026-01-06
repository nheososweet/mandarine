# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
import os
# Import Config & Router
from app.core.config import settings
from app.api.v1.router import api_router

# Import Exception Logic (Chúng ta đã tạo ở bước trước)
from app.core.exceptions import BaseAPIException
from app.core.handlers import (
    custom_api_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler
)

def get_application() -> FastAPI:
    """
    Hàm factory để khởi tạo app. 
    Giúp code gọn gàng và dễ testing hơn là viết tràn lan ra ngoài.
    """
    application = FastAPI(
        title=settings.PROJECT_NAME,
        debug=settings.DEBUG,
        docs_url="/docs", # Có thể tắt trong production bằng settings
        openapi_url="/openapi.json"
    )

    # --- 1. MIDDLEWARE: CORS (Cực kỳ quan trọng cho FE) ---
    # Cho phép FE gọi API từ domain khác
    if settings.BACKEND_CORS_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            # Trong dev có thể để ["*"], nhưng Prod nên là ["https://your-frontend.com"]
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"], # Cho phép tất cả methods: GET, POST, DELETE...
            allow_headers=["*"], # Cho phép gửi kèm token, custom headers...
        )

    # --- 2. EXCEPTION HANDLERS (Đăng ký bộ bắt lỗi chuẩn) ---
    # Thứ tự đăng ký từ cụ thể -> tổng quát
    
    # Bắt lỗi Custom Logic (Do mình tự raise)
    application.add_exception_handler(BaseAPIException, custom_api_exception_handler)
    
    # Bắt lỗi Validation (Pydantic - sai kiểu dữ liệu input)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # Bắt lỗi HTTP chuẩn (404 Not Found, v.v.)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    
    # Bắt tất cả lỗi còn lại (Crash app)
    application.add_exception_handler(Exception, general_exception_handler)

    # --- 3. ROUTER ---
    application.include_router(api_router, prefix=settings.API_V1_STR)

    return application

app = get_application()

# Persistent uploads directory for PDFs
PERSISTENT_UPLOAD_DIR = "persistent_uploads"
os.makedirs(PERSISTENT_UPLOAD_DIR, exist_ok=True)

# Regular uploads directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount static files for PDF viewing
app.mount(
    "/static",
    StaticFiles(directory=PERSISTENT_UPLOAD_DIR),
    name="static",
)

app.mount(
    "/uploads",
    StaticFiles(directory=UPLOAD_DIR),
    name="uploads",
)

@app.get("/", tags=["Health Check"])
def root():
    """
    Health check endpoint
    """
    return {
        "message": "Welcome to RAG API System",
        "status": "active",
        "version": "1.0.0",
        "docs_url": "/docs"
    }