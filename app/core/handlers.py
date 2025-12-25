# app/core/handlers.py
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.exceptions import BaseAPIException
from app.core.logging import logger

# 1. Handle Custom Logic Errors (Do mình throw ra)
async def custom_api_exception_handler(request: Request, exc: BaseAPIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        },
    )

# 2. Handle Validation Errors (Do Pydantic throw ra khi FE gửi sai kiểu dữ liệu)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Format lại lỗi của Pydantic cho dễ đọc hơn
    details = {}
    for error in exc.errors():
        # Get field name (e.g., "body.email" or just "email")
        field = ".".join(str(x) for x in error["loc"] if x != "body")
        details[field] = error["msg"]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed",
                "details": details
            }
        },
    )

# 3. Handle Standard HTTP Errors (404 Not Found do gõ sai URL, v.v.)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
                "details": None
            }
        },
    )

# 4. Handle General System Errors (Crash, Bug code, Library lỗi ngầm)
async def general_exception_handler(request: Request, exc: Exception):
    # Log lỗi chi tiết để Dev sửa
    logger.critical(f"Unhandled Exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact support.",
                "details": str(exc) if True else None # Production nên ẩn cái này đi
            }
        },
    )