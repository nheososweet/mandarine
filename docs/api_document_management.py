"""
📚 Document Management API - Test Examples

Các API endpoints để quản lý tài liệu trong Vector DB
"""

# =============================================================================
# 1. LIST ALL DOCUMENTS
# =============================================================================
# GET http://localhost:8000/api/v1/documents/
"""
Response:
{
    "total": 2,
    "total_chunks": 45,
    "documents": [
        {
            "id": "doc_123",
            "filename": "Quy_che.pdf",
            "source": "/path/to/Quy_che.pdf",
            "page": 1,
            "preview": "Quy chế nội bộ công ty...",
            "chunk_count": 25
        },
        {
            "id": "doc_456",
            "filename": "Huong_dan.docx",
            "source": "/path/to/Huong_dan.docx",
            "page": null,
            "preview": "Hướng dẫn sử dụng...",
            "chunk_count": 20
        }
    ]
}
"""


# =============================================================================
# 2. SEARCH DOCUMENTS BY FILENAME
# =============================================================================
# GET http://localhost:8000/api/v1/documents/search?filename=Quy_che
"""
Response:
{
    "total": 1,
    "total_chunks": 25,
    "documents": [
        {
            "id": "doc_123",
            "filename": "Quy_che.pdf",
            ...
        }
    ]
}
"""


# =============================================================================
# 3. GET DATABASE STATISTICS
# =============================================================================
# GET http://localhost:8000/api/v1/documents/stats
"""
Response:
{
    "total_files": 2,
    "total_chunks": 45,
    "storage_path": "./chroma_db_store",
    "embedding_model": "models/text-embedding-004"
}
"""


# =============================================================================
# 4. DELETE DOCUMENT BY FILENAME
# =============================================================================
# DELETE http://localhost:8000/api/v1/documents/source/Quy_che.pdf
"""
Response:
{
    "status": "success",
    "message": "Document 'Quy_che.pdf' deleted successfully",
    "deleted_chunks": 25
}
"""


# =============================================================================
# 5. CLEAR ALL DOCUMENTS
# =============================================================================
# DELETE http://localhost:8000/api/v1/documents/
"""
⚠️ CẢNH BÁO: Xóa toàn bộ database, không thể hoàn tác!

Response:
{
    "status": "success",
    "message": "All documents cleared successfully",
    "deleted_chunks": 0
}
"""


# =============================================================================
# CURL EXAMPLES
# =============================================================================

"""
# List all documents
curl -X GET "http://localhost:8000/api/v1/documents/"

# Search documents
curl -X GET "http://localhost:8000/api/v1/documents/search?filename=Quy_che"

# Get statistics
curl -X GET "http://localhost:8000/api/v1/documents/stats"

# Delete one document
curl -X DELETE "http://localhost:8000/api/v1/documents/source/Quy_che.pdf"

# Clear all
curl -X DELETE "http://localhost:8000/api/v1/documents/"
"""


# =============================================================================
# PYTHON REQUESTS EXAMPLES
# =============================================================================

"""
import requests

BASE_URL = "http://localhost:8000/api/v1/documents"

# List all
response = requests.get(f"{BASE_URL}/")
print(response.json())

# Search
response = requests.get(f"{BASE_URL}/search", params={"filename": "Quy_che"})
print(response.json())

# Stats
response = requests.get(f"{BASE_URL}/stats")
print(response.json())

# Delete one
response = requests.delete(f"{BASE_URL}/source/Quy_che.pdf")
print(response.json())

# Clear all (⚠️ Dangerous!)
response = requests.delete(f"{BASE_URL}/")
print(response.json())
"""
