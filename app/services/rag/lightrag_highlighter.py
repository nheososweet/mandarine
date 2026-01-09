"""
LightRAG Highlighter - Skeleton Strategy
========================================
Module này giải quyết vấn đề highlight cho LightRAG khi:
1. Text bị lỗi khoảng trắng (ti ền -> tiền).
2. Chunk quá dài, trải qua nhiều trang.
3. Chunk chứa header/footer lặp lại.

Giải thuật:
1. Load toàn bộ PDF thành một dòng chảy các từ (Global Word Stream).
2. Tạo "Skeleton String" bằng cách nối các từ lại và bỏ qua khoảng trắng/dấu câu thừa.
3. Dùng SequenceMatcher tìm đoạn khớp dài nhất trên Skeleton.
4. Map ngược từ ký tự trong Skeleton ra tọa độ (BBox) của từ gốc.
"""

import re
import logging
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

@dataclass
class HighlightArea:
    """Đại diện cho một vùng highlight (tọa độ %)"""
    pageIndex: int
    left: float
    top: float
    width: float
    height: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ChunkHighlight:
    """Chứa danh sách highlight cho một chunk"""
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

class LightRAGHighlighter:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc: Optional[fitz.Document] = None
        
        # Mapping quan trọng:
        # self.global_words: List các từ trong toàn bộ PDF (kèm trang, bbox)
        self.global_words: List[Dict[str, Any]] = []
        
        # self.doc_skeleton: Chuỗi string khổng lồ đại diện cho cả PDF (đã clean, viết liền không dấu cách)
        self.doc_skeleton: str = ""
        
        # self.char_to_word_idx: Map index ký tự trong skeleton -> index từ trong global_words
        # VD: ký tự thứ 100 trong skeleton thuộc về từ thứ 20 trong global_words
        self.char_to_word_idx: List[int] = []
        
        self._load_pdf()

    def _load_pdf(self):
        """Load PDF và xây dựng Skeleton Index"""
        try:
            self.doc = fitz.open(self.pdf_path)
            self.global_words = []
            self.doc_skeleton = ""
            self.char_to_word_idx = []

            for page_idx, page in enumerate(self.doc):
                # get_text("words") trả về: (x0, y0, x1, y1, "text", block_no, line_no, word_no)
                words = page.get_text("words")
                
                for w in words:
                    text_content = w[4]
                    
                    # Tạo skeleton cho từ này (bỏ dấu cách, lower case)
                    clean_text = self._make_skeleton_segment(text_content)
                    
                    if not clean_text:
                        continue

                    # 1. Lưu thông tin từ vào danh sách toàn cục
                    self.global_words.append({
                        "page": page_idx,
                        "bbox": w[:4], # (x0, y0, x1, y1)
                        "text": text_content
                    })
                    
                    # 2. Cập nhật chuỗi skeleton
                    self.doc_skeleton += clean_text
                    
                    # 3. Map từng ký tự của từ này về index của từ trong list global_words
                    word_idx = len(self.global_words) - 1
                    self.char_to_word_idx.extend([word_idx] * len(clean_text))

            logger.info(f"📖 Indexed PDF: {len(self.global_words)} words, skeleton len: {len(self.doc_skeleton)}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load PDF {self.pdf_path}: {e}")
            raise

    def _make_skeleton_segment(self, text: str) -> str:
        """
        Biến text thành dạng xương sống: lower, bỏ space, bỏ dấu câu nhiễu.
        Giữ lại chữ cái và số, bao gồm tiếng Việt.
        """
        text = text.lower()
        # Xóa toàn bộ whitespace, newline, tab
        text = re.sub(r'\s+', '', text)
        return text

    def find_all_highlights(self, chunks: List[Dict[str, Any]]) -> List[ChunkHighlight]:
        """Tìm highlight cho danh sách chunks"""
        results = []
        if not self.doc: return results

        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", chunk.get("id", "unknown"))
            raw_content = chunk.get("content", chunk.get("text", ""))
            
            if not raw_content: continue

            # 1. Tạo skeleton cho chunk (chunk_skeleton cũng sẽ không có dấu cách)
            chunk_skeleton = self._make_skeleton_segment(raw_content)
            
            # Bỏ qua nếu chunk quá ngắn (dưới 10 ký tự thực)
            if len(chunk_skeleton) < 10: 
                continue 

            # 2. Tìm kiếm chuỗi chunk trong chuỗi PDF (Fuzzy Match)
            # SequenceMatcher tìm đoạn trùng dài nhất (longest contiguous matching block)
            # autojunk=False để tránh nó bỏ qua các từ lặp lại nhiều
            matcher = SequenceMatcher(None, self.doc_skeleton, chunk_skeleton, autojunk=False)
            
            # Tìm đoạn khớp dài nhất
            match = matcher.find_longest_match(0, len(self.doc_skeleton), 0, len(chunk_skeleton))

            # Ngưỡng chấp nhận: Đoạn khớp phải có độ dài tương đối
            if match.size < 15: # Quá ngắn (< 15 ký tự liền mạch) thì coi như không tìm thấy
                logger.warning(f"⚠️ Chunk {chunk_id}: No good match found (size={match.size})")
                continue

            # 3. Map từ vị trí ký tự (Skeleton) -> Danh sách từ (Words)
            doc_start_char = match.a
            doc_end_char = match.a + match.size
            
            try:
                # Map ngược từ ký tự sang index của từ trong global_words
                start_word_idx = self.char_to_word_idx[doc_start_char]
                # doc_end_char là exclusive, nên lấy char liền trước đó
                end_word_idx = self.char_to_word_idx[doc_end_char - 1]
            except IndexError:
                # Trường hợp boundary edge case
                continue

            # Lấy danh sách các từ đã match
            # +1 ở end_word_idx vì slicing trong python là exclusive
            matched_global_words = self.global_words[start_word_idx : end_word_idx + 1]
            
            if not matched_global_words:
                continue

            # 4. Convert các từ thành HighlightArea (tọa độ %)
            areas = self._words_to_areas(matched_global_words)
            
            # 5. Gộp các từ thành dòng (Merge)
            merged_areas = self._merge_areas(areas)

            # 6. Xác định trang chính (trang chứa nhiều highlight nhất)
            page_counts = {}
            for a in merged_areas:
                page_counts[a.pageIndex] = page_counts.get(a.pageIndex, 0) + 1
            primary_page = max(page_counts, key=page_counts.get) if page_counts else 0

            results.append(ChunkHighlight(
                chunkId=chunk_id,
                pageIndex=primary_page,
                text=raw_content,
                areas=merged_areas
            ))
            
            logger.info(f"✅ Chunk {chunk_id}: Match found on Page {primary_page + 1} (Words: {len(matched_global_words)})")

        return results

    def _words_to_areas(self, words: List[Dict[str, Any]]) -> List[HighlightArea]:
        """Chuyển đổi danh sách từ (bbox tuyệt đối) sang HighlightArea (bbox %)"""
        areas = []
        for w in words:
            page_idx = w['page']
            page_obj = self.doc[page_idx]
            pw = page_obj.rect.width
            ph = page_obj.rect.height
            
            x0, y0, x1, y1 = w['bbox']
            
            areas.append(HighlightArea(
                pageIndex=page_idx,
                left=(x0 / pw) * 100,
                top=(y0 / ph) * 100,
                width=((x1 - x0) / pw) * 100,
                height=((y1 - y0) / ph) * 100
            ))
        return areas

    def _merge_areas(self, areas: List[HighlightArea]) -> List[HighlightArea]:
        """Gộp các highlight từng từ thành dòng để hiển thị đẹp hơn"""
        if not areas: return []
        
        # Sắp xếp: Trang -> Dòng (Top) -> Trái (Left)
        # Làm tròn top để các từ cùng dòng nhưng lệch pixel vẫn gộp được
        areas.sort(key=lambda x: (x.pageIndex, round(x.top, 1), x.left))
        
        merged = []
        current = areas[0]
        
        for next_area in areas[1:]:
            # 1. Khác trang -> ngắt
            if current.pageIndex != next_area.pageIndex:
                merged.append(current)
                current = next_area
                continue
            
            # 2. Khác dòng (độ lệch dọc > 1.5%) -> ngắt
            if abs(current.top - next_area.top) > 1.5:
                merged.append(current)
                current = next_area
                continue
            
            # 3. Quá xa nhau theo chiều ngang (> 20%) -> ngắt
            # Cho phép khoảng cách lớn (20%) để nối được các từ bị rách rời như "ti ền"
            horizontal_gap = next_area.left - (current.left + current.width)
            if horizontal_gap > 20.0: 
                merged.append(current)
                current = next_area
                continue
                
            # GỘP: Mở rộng current area bao trùm next_area
            new_left = min(current.left, next_area.left)
            new_top = min(current.top, next_area.top)
            # Right edge mới = max của (left + width)
            current_right = current.left + current.width
            next_right = next_area.left + next_area.width
            new_width = max(current_right, next_right) - new_left
            new_height = max(current.height, next_area.height)
            
            current = HighlightArea(
                pageIndex=current.pageIndex,
                left=new_left,
                top=new_top,
                width=new_width,
                height=new_height
            )
            
        merged.append(current)
        return merged

    def close(self):
        if self.doc: self.doc.close()

    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.close()