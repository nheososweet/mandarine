import re
import logging
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG) # Bật debug nếu cần soi kỹ

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

class PDFHighlighter:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc: Optional[fitz.Document] = None
        # Cache text content của từng trang để đỡ phải đọc đi đọc lại
        self.pages_content: Dict[int, str] = {} 
        self.pages_rects: Dict[int, List[Any]] = {} # Lưu bbox của từng từ/câu
        self._load_pdf()

    def _load_pdf(self):
        try:
            self.doc = fitz.open(self.pdf_path)
            # Pre-load text của tất cả các trang để tìm kiếm nhanh hơn
            for page_idx, page in enumerate(self.doc):
                # Lấy text dạng words để có bbox chính xác
                # Cấu trúc word: (x0, y0, x1, y1, "text", block_no, line_no, word_no)
                words = page.get_text("words")
                self.pages_rects[page_idx] = words
                
                # Tạo một string text liền mạch cho trang để dễ search fuzzy
                # Lưu ý: cần join có khoảng trắng để tránh dính chữ
                text_content = " ".join([w[4] for w in words])
                self.pages_content[page_idx] = self._clean_text(text_content)
                
            logger.info(f"Loaded PDF: {self.pdf_path} ({len(self.doc)} pages)")
        except Exception as e:
            logger.error(f"❌ Failed to load PDF {self.pdf_path}: {e}")
            raise

    def _clean_text(self, text: str) -> str:
        """Chuẩn hóa text để so sánh: lowercase, bỏ dấu câu, bỏ khoảng trắng thừa."""
        # Giữ lại chữ cái và số Tiếng Việt, còn lại thay bằng space
        # Regex này giữ lại các ký tự Unicode tiếng Việt
        text = text.lower()
        # Thay thế xuống dòng và tab bằng space
        text = re.sub(r'[\n\r\t]', ' ', text)
        # Thay thế nhiều space bằng 1 space
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _split_into_segments(self, text: str, window_size: int = 20, overlap: int = 5) -> List[str]:
        """
        Cắt chunk dài thành các đoạn nhỏ (segments) để tìm kiếm dễ hơn.
        Mỗi segment khoảng 'window_size' từ.
        """
        words = text.split()
        if not words: return []
        
        segments = []
        i = 0
        while i < len(words):
            # Lấy đoạn text window_size từ
            segment_words = words[i : i + window_size]
            segment_text = " ".join(segment_words)
            segments.append(segment_text)
            
            # Nhảy bước (có overlap để tránh mất dữ liệu ở biên)
            i += (window_size - overlap)
            
        return segments

    def find_all_highlights(self, chunks: List[Dict[str, Any]]) -> List[ChunkHighlight]:
        results = []
        if not self.doc: return results

        for chunk in chunks:
            chunk_id = chunk.get("id", "unknown")
            raw_chunk_text = chunk.get("text", "")
            
            if not raw_chunk_text: continue

            # 1. Clean chunk text
            clean_chunk = self._clean_text(raw_chunk_text)
            
            # 2. Chia chunk thành các đoạn nhỏ (Segments)
            # Vì chunk của LightRAG rất dài và trải qua nhiều trang, ta không thể tìm nguyên cục.
            # Ta chia nhỏ ra, ví dụ mỗi đoạn 15-20 từ.
            segments = self._split_into_segments(clean_chunk, window_size=15, overlap=5)
            
            found_areas_raw = [] # List[(page_idx, rect)]
            
            # 3. Tìm từng segment trong tất cả các trang
            for segment in segments:
                if len(segment) < 10: continue # Bỏ qua đoạn quá ngắn
                
                for page_idx, page_content in self.pages_content.items():
                    # Dùng thuật toán tìm chuỗi gần đúng (Fuzzy Search) hoặc Exact nếu clean tốt
                    # Ở đây dùng simple string find trên text đã clean vì tốc độ cao
                    # Nếu tìm thấy segment trong trang này
                    
                    if segment in page_content:
                        # Tìm vị trí chính xác của các từ trong segment trên trang này
                        # Logic: Tìm các 'words' trong self.pages_rects[page_idx] khớp với segment
                        
                        page_words = self.pages_rects[page_idx]
                        segment_tokens = segment.split()
                        
                        # Quét qua các từ trên trang để tìm chuỗi khớp
                        # (Đây là sliding window cục bộ trên 1 trang)
                        for i in range(len(page_words) - len(segment_tokens) + 1):
                            # Kiểm tra nhanh từ đầu tiên
                            if self._clean_text(page_words[i][4]) != segment_tokens[0]:
                                continue
                                
                            # Kiểm tra khớp cả chuỗi segment
                            match = True
                            for j in range(1, len(segment_tokens)):
                                if self._clean_text(page_words[i+j][4]) != segment_tokens[j]:
                                    match = False
                                    break
                            
                            if match:
                                # Đã tìm thấy vị trí khớp! Lưu lại bbox của tất cả các từ trong segment
                                for k in range(len(segment_tokens)):
                                    w_rect = page_words[i+k][:4] # (x0, y0, x1, y1)
                                    found_areas_raw.append((page_idx, w_rect))
                                
                                # Tìm thấy ở trang này rồi thì break loop trang, chuyển segment tiếp theo
                                # (Giả định 1 segment text chỉ xuất hiện 1 lần duy nhất quan trọng)
                                break 
                        else:
                            continue # Continue outer loop (pages) if inner loop didn't break
                        break # Break page loop if found

            # 4. Convert bbox sang HighlightArea và Merge
            if found_areas_raw:
                final_areas = []
                for page_idx, rect in found_areas_raw:
                    page_obj = self.doc[page_idx]
                    w = page_obj.rect.width
                    h = page_obj.rect.height
                    
                    final_areas.append(HighlightArea(
                        pageIndex=page_idx,
                        left=(rect[0] / w) * 100,
                        top=(rect[1] / h) * 100,
                        width=((rect[2] - rect[0]) / w) * 100,
                        height=((rect[3] - rect[1]) / h) * 100
                    ))
                
                # Merge các highlight rời rạc thành khối
                merged_areas = self._merge_areas(final_areas)
                
                # Xác định trang chính (trang chứa nhiều highlight nhất)
                page_counts = {}
                for a in merged_areas:
                    page_counts[a.pageIndex] = page_counts.get(a.pageIndex, 0) + 1
                primary_page = max(page_counts, key=page_counts.get) if page_counts else 0

                results.append(ChunkHighlight(
                    chunkId=chunk_id,
                    pageIndex=primary_page,
                    text=raw_chunk_text,
                    areas=merged_areas
                ))
            else:
                logger.warning(f"⚠️ Could not map chunk {chunk_id} to PDF coordinates.")

        return results

    def _merge_areas(self, areas: List[HighlightArea]) -> List[HighlightArea]:
        """Gộp các highlight nhỏ (từng từ) thành dòng hoặc khối."""
        if not areas: return []
        
        # Sắp xếp: Trang -> Dòng (Top) -> Trái (Left)
        areas.sort(key=lambda x: (x.pageIndex, x.top, x.left))
        
        merged = []
        current = areas[0]
        
        for next_area in areas[1:]:
            # Khác trang -> không gộp
            if current.pageIndex != next_area.pageIndex:
                merged.append(current)
                current = next_area
                continue

            # Kiểm tra cùng dòng (lệch top < 1%)
            vertical_diff = abs(current.top - next_area.top)
            # Kiểm tra khoảng cách ngang (gần nhau)
            horizontal_gap = next_area.left - (current.left + current.width)
            
            # Điều kiện gộp: Cùng dòng VÀ (gần nhau hoặc chồng lấn)
            if vertical_diff < 1.0 and horizontal_gap < 3.0: 
                # Tạo box mới bao trùm cả 2
                new_left = min(current.left, next_area.left)
                new_top = min(current.top, next_area.top)
                
                # Chiều rộng mới = điểm cuối phải nhất - điểm đầu trái nhất
                right_edge = max(current.left + current.width, next_area.left + next_area.width)
                new_width = right_edge - new_left
                
                new_height = max(current.height, next_area.height)
                
                current = HighlightArea(current.pageIndex, new_left, new_top, new_width, new_height)
            else:
                merged.append(current)
                current = next_area
                
        merged.append(current)
        return merged

    def close(self):
        if self.doc: self.doc.close()

    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.close()