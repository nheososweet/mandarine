import re
import logging
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

@dataclass
class HighlightArea:
    pageIndex: int
    left: float
    top: float
    width: float
    height: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ChunkHighlight:
    chunkId: str
    pageIndex: int
    text: str
    areas: List[HighlightArea]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunkId": self.chunkId,
            "pageIndex": self.pageIndex,
            "text": self.text[:100] + "..." if len(self.text) > 100 else self.text,
            "areas": [area.to_dict() for area in self.areas]
        }

class EnhancedPDFHighlighter:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc: Optional[fitz.Document] = None
        # Cache on-demand thay vì load toàn bộ ngay từ đầu
        self.pages_content: Dict[int, str] = {} 
        self.pages_rects: Dict[int, List[Any]] = {} 
        self._open_pdf()

    def _open_pdf(self):
        try:
            self.doc = fitz.open(self.pdf_path)
            logger.info(f"Opened PDF for enhanced highlighting: {self.pdf_path}")
        except Exception as e:
            logger.error(f"❌ Failed to open PDF: {e}")
            raise

    def _load_page_data(self, page_idx: int):
        """Load và cache dữ liệu trang chỉ khi cần thiết."""
        if page_idx < 0 or page_idx >= len(self.doc):
            return None, None
            
        if page_idx not in self.pages_content:
            page = self.doc[page_idx]
            words = page.get_text("words")
            self.pages_rects[page_idx] = words
            
            # Xử lý text thô: gộp word và clean
            text_content = " ".join([w[4] for w in words])
            self.pages_content[page_idx] = self._clean_text(text_content)
            
        return self.pages_content[page_idx], self.pages_rects[page_idx]

    def _clean_text(self, text: str) -> str:
        """Chuẩn hóa text theo phong cách bảo thủ hơn để tránh lệch mapping."""
        if not text: return ""
        text = text.lower()
        # Thay thế xuống dòng và tab bằng space
        text = re.sub(r'[\n\r\t]', ' ', text)
        # Không xóa [^\w\s] ở đây để giữ nguyên cấu trúc word của PDF
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def find_all_highlights(self, chunks: List[Dict[str, Any]]) -> List[ChunkHighlight]:
        results = []
        if not self.doc: return results

        for chunk in chunks:
            chunk_id = chunk.get("id", "unknown")
            raw_text = chunk.get("text", "")
            hint_page = chunk.get("page")
            
            if not raw_text: continue
            
            # Sử dụng clean nhẹ nhàng
            clean_chunk = self._clean_text(raw_text)
            chunk_tokens = clean_chunk.split()
            if not chunk_tokens: continue
            
            # Cửa sổ trượt rộng hơn (15 từ) và overlap dày (10 từ) để đảm bảo không sót
            window_size = 15
            overlap = 10
            segments = []
            for i in range(0, len(chunk_tokens), window_size - overlap):
                seg = chunk_tokens[i : i + window_size]
                if len(seg) >= 3:
                    segments.append(seg)

            found_areas_raw = []

            # Xác định trang search (ưu tiên hint_page)
            search_pages = []
            if hint_page is not None:
                # Hint page thường là 1-based từ RAG
                p_idx = hint_page - 1 if hint_page > 0 else 0
                search_pages = [p_idx]
                # Thêm trang lân cận đề phòng chunk tràn trang
                if p_idx + 1 < len(self.doc): search_pages.append(p_idx + 1)
                if p_idx - 1 >= 0: search_pages.append(p_idx - 1)
            
            if not search_pages:
                search_pages = list(range(len(self.doc)))

            for seg_tokens in segments:
                found_seg = False
                for p_idx in search_pages:
                    if p_idx < 0 or p_idx >= len(self.doc): continue
                    
                    p_content, p_words = self._load_page_data(p_idx)
                    if not p_content: continue

                    # Tìm kiếm mờ thông minh ở cấp độ word
                    for i in range(len(p_words) - len(seg_tokens) + 1):
                        match_count = 0
                        for j in range(len(seg_tokens)):
                            word_pdf = self._clean_text(p_words[i+j][4])
                            target = seg_tokens[j]
                            
                            # So sánh linh hoạt: khớp hoàn toàn hoặc chứa nhau (để xử lý dính chữ/tách chữ)
                            if word_pdf == target or target in word_pdf or word_pdf in target:
                                match_count += 1
                        
                        # Chỉ cần khớp 70% số từ trong segment là chấp nhận (giảm đứt đoạn)
                        if match_count / len(seg_tokens) >= 0.7:
                            for k in range(len(seg_tokens)):
                                found_areas_raw.append((p_idx, p_words[i+k][:4]))
                            found_seg = True
                            break
                    if found_seg: break

            if found_areas_raw:
                final_areas = []
                for p_idx, rect in found_areas_raw:
                    p_obj = self.doc[p_idx]
                    w, h = p_obj.rect.width, p_obj.rect.height
                    final_areas.append(HighlightArea(
                        pageIndex=p_idx,
                        left=(rect[0]/w)*100, top=(rect[1]/h)*100,
                        width=((rect[2]-rect[0])/w)*100, height=((rect[3]-rect[1])/h)*100
                    ))
                
                # Merge với ngưỡng rộng hơn để tạo thành khối liền mạch
                merged = self._merge_areas(final_areas)
                
                p_counts = {}
                for a in merged: p_counts[a.pageIndex] = p_counts.get(a.pageIndex, 0) + 1
                primary = max(p_counts, key=p_counts.get) if p_counts else search_pages[0]

                results.append(ChunkHighlight(chunk_id, primary, raw_text, merged))

        return results

    def _merge_areas(self, areas: List[HighlightArea]) -> List[HighlightArea]:
        if not areas: return []
        # Sắp xếp: Trang -> Dòng (làm tròn để tránh lệch pixel) -> Cột
        areas.sort(key=lambda x: (x.pageIndex, round(x.top, 1), x.left))
        
        merged = []
        curr = areas[0]
        for nxt in areas[1:]:
            # Nới lỏng vertical_diff lên 1.5% và horizontal_gap lên 4% để lấp đầy khoảng trống
            if curr.pageIndex == nxt.pageIndex and \
               abs(curr.top - nxt.top) < 1.5 and \
               (nxt.left - (curr.left + curr.width)) < 4.0:
                
                new_left = min(curr.left, nxt.left)
                new_top = min(curr.top, nxt.top)
                # Tính toán lại chiều rộng bao phủ cả 2
                new_right = max(curr.left + curr.width, nxt.left + nxt.width)
                new_width = new_right - new_left
                new_height = max(curr.height, nxt.height)
                
                curr = HighlightArea(curr.pageIndex, new_left, new_top, new_width, new_height)
            else:
                merged.append(curr)
                curr = nxt
        merged.append(curr)
        return merged

    def close(self):
        if self.doc: self.doc.close()
    def __enter__(self): return self
    def __exit__(self, e_t, e_v, e_b): self.close()
