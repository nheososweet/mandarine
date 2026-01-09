import os
import json
import logging
import httpx
from typing import List, Dict, Any, Optional

# Import highlighter mới
from app.services.rag.lightrag_highlighter import LightRAGHighlighter

logger = logging.getLogger(__name__)

# --- CẤU HÌNH (HARDCODED) ---
LIGHTRAG_API_URL = "http://localhost:9621"
# URL để FE tải file PDF
STATIC_FILE_URL_PREFIX = "http://localhost:8000/static/uploads" 
# Đường dẫn tuyệt đối chứa file PDF gốc trên ổ đĩa
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
class LightRAGBridgeService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)

    async def get_references_with_highlights(
        self, payload: Dict[str, Any], request=None
    ) -> Dict[str, Any]:
        """
        1. Gọi LightRAG API lấy chunks
        2. Dùng LightRAGHighlighter (Skeleton Match) để tìm tọa độ
        3. Trả về format chuẩn cho Frontend
        """
        
        # --- BƯỚC 1: Gọi LightRAG API (tắt stream) ---
        lightrag_payload = payload.copy()
        lightrag_payload["stream"] = False

        try:
            response = await self.client.post(
                f"{LIGHTRAG_API_URL}/query/data",
                json=lightrag_payload
            )
            response.raise_for_status()
            rag_data = response.json()
        except Exception as e:
            logger.error(f"❌ LightRAG API Error: {e}")
            return {
                "status": "error", 
                "sources": [], 
                "highlights": {}, 
                "raw_chunks": [], 
                "error": str(e)
            }

        # Kiểm tra dữ liệu trả về
        chunks_list = rag_data.get("data", {}).get("chunks", [])
        if not chunks_list:
            return {
                "status": "success", 
                "sources": [], 
                "highlights": {}, 
                "raw_chunks": [],
                "entities": rag_data.get("data", {}).get("entities", []),
                "relationships": rag_data.get("data", {}).get("relationships", [])
            }

        # --- BƯỚC 2: Gom nhóm Chunks theo File ---
        chunks_by_file = {}
        for chunk in chunks_list:
            raw_path = chunk.get("file_path", "")
            if not raw_path: continue
            
            # Lấy tên file (VD: noiquy.pdf)
            base_name = os.path.basename(raw_path)
            
            if base_name not in chunks_by_file:
                chunks_by_file[base_name] = []
            
            # Giữ nguyên chunk data cho highlighter
            chunks_by_file[base_name].append(chunk)

        # --- BƯỚC 3: Xử lý từng file ---
        final_highlights_map = {}
        sources_list = []
        raw_chunks_list = []
        
        # Sử dụng đường dẫn tuyệt đối đã hardcode
        abs_upload_dir = os.path.abspath(UPLOAD_DIR)

        for file_name, chunks in chunks_by_file.items():
            # 1. URL cho Frontend (Sử dụng URL hardcode + tên file)
            # Ví dụ: http://localhost:8000/static/uploads/noiquy.pdf
            # Lưu ý: Logic FE của bạn có thể cần URL chính xác để map key trong highlight
            file_url = f"/noiquy.pdf" # DEMO fix cứng theo format bạn gửi trong prompt trước
            # Nếu muốn dynamic: file_url = f"{STATIC_FILE_URL_PREFIX}/{file_name}"
            
            # 2. Path vật lý để đọc PDF
            real_pdf_path = os.path.join(abs_upload_dir, file_name)
            
            chunk_page_map = {} # Map chunk_id -> page index (để scroll tới)

            # --- A. XỬ LÝ HIGHLIGHT ---
            if file_name.lower().endswith('.pdf') and os.path.exists(real_pdf_path):
                try:
                    logger.info(f"🔆 Extracting highlights for {file_name} using Skeleton Match...")
                    
                    # KHỞI TẠO HIGHLIGHTER
                    with LightRAGHighlighter(real_pdf_path) as highlighter:
                        # Gọi hàm tìm kiếm
                        chunk_highlights = highlighter.find_all_highlights(chunks)
                        
                        file_areas_flat = []
                        for ch in chunk_highlights:
                            # Lưu page tìm được cho chunk này (để dùng cho raw chunk và source)
                            # pageIndex của thư viện là 0-based, ta lưu +1 cho dễ đọc nếu cần, 
                            # nhưng FE thường dùng 0-based cho highlight, 1-based cho hiển thị text.
                            chunk_page_map[ch.chunkId] = ch.pageIndex + 1 
                            
                            for area in ch.areas:
                                file_areas_flat.append({
                                    "pageIndex": area.pageIndex,
                                    "left": round(area.left, 2),
                                    "top": round(area.top, 2),
                                    "width": round(area.width, 2),
                                    "height": round(area.height, 2),
                                    "chunkId": ch.chunkId 
                                })
                        
                        if file_areas_flat:
                            # Key của highlights map phải khớp với url trong source
                            final_highlights_map[file_url] = file_areas_flat
                            logger.info(f"   ✅ Found {len(file_areas_flat)} areas")
                        else:
                            logger.warning(f"   ⚠️ No highlights found")
                            
                except Exception as e:
                    logger.error(f"❌ Error highlighting {file_name}: {e}")
            else:
                if not os.path.exists(real_pdf_path):
                    logger.error(f"❌ File not found at: {real_pdf_path}")
            
            # --- B. TẠO SOURCES LIST & RAW CHUNKS ---
            # Tìm page mặc định (min page tìm thấy hoặc 1)
            default_page = 1
            if chunk_page_map:
                default_page = min(chunk_page_map.values())
            
            sources_list.append({
                "source": file_name,
                "url": file_url,
                "page": default_page
            })

            for chunk in chunks:
                c_id = chunk.get("chunk_id", "unknown")
                raw_chunks_list.append({
                    "id": c_id,
                    "text": chunk.get("content", ""),
                    "source": file_name,
                    "url": file_url,
                    # Nếu tìm thấy highlight thì lấy page đó, ko thì page 0
                    "page": chunk_page_map.get(c_id, 0) 
                })

        return {
            "status": "success",
            "sources": sources_list,
            "highlights": final_highlights_map,
            "raw_chunks": raw_chunks_list,
            "entities": rag_data.get("data", {}).get("entities", []),
            "relationships": rag_data.get("data", {}).get("relationships", [])
        }

    async def close(self):
        await self.client.aclose()

lightrag_bridge_service = LightRAGBridgeService()