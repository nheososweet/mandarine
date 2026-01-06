"""
PDF Highlighter Service
========================
This module extracts precise text coordinates from PDF files using PyMuPDF (fitz).
It matches retrieved RAG chunks to exact positions in the original PDF and returns
highlight areas compatible with react-pdf-viewer's highlightPlugin.

Coordinate System:
- PyMuPDF uses absolute coordinates (points, 72 dpi)
- react-pdf-viewer expects percentages (0-100) relative to page dimensions
- All coordinates are converted: (absolute / page_dimension) * 100

Edge Cases Handled:
- Same chunk appears multiple times on different pages
- Chunk spans multiple lines (merged into multiple HighlightArea)
- Different font sizes within same page
- Rotated PDF pages (handled by frontend getCssProperties)
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


@dataclass
class HighlightArea:
    """
    Represents a single highlight rectangle.
    All coordinates are percentages (0-100) relative to page size.
    Compatible with react-pdf-viewer HighlightArea interface.
    """
    pageIndex: int   # Zero-based page index
    left: float      # Distance from left edge (%)
    top: float       # Distance from top edge (%)
    width: float     # Width of highlight (%)
    height: float    # Height of highlight (%)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChunkHighlight:
    """
    Represents all highlight areas for a single RAG chunk.
    """
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


class PDFTextBlock:
    """
    Represents a text block extracted from PDF with its geometry.
    """
    def __init__(self, text: str, bbox: Tuple[float, float, float, float], 
                 page_index: int, page_width: float, page_height: float):
        self.text = text
        self.bbox = bbox  # (x0, y0, x1, y1) in absolute coordinates
        self.page_index = page_index
        self.page_width = page_width
        self.page_height = page_height
    
    def to_highlight_area(self) -> HighlightArea:
        """Convert absolute coordinates to percentage-based HighlightArea."""
        x0, y0, x1, y1 = self.bbox
        return HighlightArea(
            pageIndex=self.page_index,
            left=(x0 / self.page_width) * 100,
            top=(y0 / self.page_height) * 100,
            width=((x1 - x0) / self.page_width) * 100,
            height=((y1 - y0) / self.page_height) * 100
        )


class PDFHighlighter:
    """
    Extracts text positions from PDF and matches RAG chunks to exact locations.
    
    Algorithm:
    1. Extract all text blocks with bounding boxes from PDF using PyMuPDF
    2. For each RAG chunk, use sliding window token matching
    3. When match found, collect all matching text blocks' bounding boxes
    4. Convert absolute coordinates to percentages
    5. Merge adjacent bounding boxes for cleaner highlighting
    """
    
    def __init__(self, pdf_path: str):
        """
        Initialize with PDF file path.
        
        Args:
            pdf_path: Absolute path to PDF file
        """
        self.pdf_path = pdf_path
        self.doc: Optional[fitz.Document] = None
        self.text_blocks: List[PDFTextBlock] = []
        self._load_pdf()
    
    def _load_pdf(self) -> None:
        """Load PDF and extract all text blocks with geometry."""
        try:
            self.doc = fitz.open(self.pdf_path)
            self._extract_text_blocks()
        except Exception as e:
            logger.error(f"Failed to load PDF {self.pdf_path}: {e}")
            raise
    
    def _extract_text_blocks(self) -> None:
        """
        Extract text blocks from all pages with their bounding boxes.
        Uses PyMuPDF's get_text("dict") for detailed text geometry.
        """
        if not self.doc:
            return
        
        for page_index, page in enumerate(self.doc):
            page_rect = page.rect
            page_width = page_rect.width
            page_height = page_rect.height
            
            # Get detailed text information
            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:  # Skip non-text blocks (images, etc.)
                    continue
                
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        
                        bbox = span.get("bbox")
                        if bbox:
                            self.text_blocks.append(PDFTextBlock(
                                text=text,
                                bbox=tuple(bbox),
                                page_index=page_index,
                                page_width=page_width,
                                page_height=page_height
                            ))
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for matching: lowercase, collapse whitespace.
        """
        text = text.lower()
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words for matching.
        Uses simple word boundary splitting.
        """
        return re.findall(r'\b\w+\b', text.lower())
    
    def _find_matching_blocks(self, chunk_text: str, page_hint: Optional[int] = None) -> List[PDFTextBlock]:
        """
        Find all text blocks that match the given chunk text.
        Uses sliding window token-based matching for robustness.
        
        Args:
            chunk_text: The RAG chunk text to find
            page_hint: Optional page number hint (1-based) to prioritize search
        
        Returns:
            List of matching PDFTextBlock objects
        """
        chunk_tokens = self._tokenize(chunk_text)
        if len(chunk_tokens) < 3:
            # For very short chunks, try exact substring match
            return self._find_exact_match(chunk_text, page_hint)
        
        matching_blocks: List[PDFTextBlock] = []
        
        # Build a mapping of tokens to blocks
        # For efficiency, we'll use a sliding window approach
        
        # Group blocks by page
        pages_to_search = []
        if page_hint is not None:
            # Prioritize the hinted page (convert 1-based to 0-based)
            page_idx = page_hint - 1
            pages_to_search.append(page_idx)
            # Also search adjacent pages in case chunk spans pages
            if page_idx > 0:
                pages_to_search.append(page_idx - 1)
            if self.doc and page_idx < len(self.doc) - 1:
                pages_to_search.append(page_idx + 1)
        else:
            # Search all pages
            pages_to_search = list(range(len(self.doc))) if self.doc else []
        
        for page_idx in pages_to_search:
            page_blocks = [b for b in self.text_blocks if b.page_index == page_idx]
            
            # Concatenate all block texts on this page with position tracking
            block_positions = []  # (start_idx, end_idx, block)
            full_text_tokens = []
            
            for block in page_blocks:
                block_tokens = self._tokenize(block.text)
                if block_tokens:
                    start_idx = len(full_text_tokens)
                    full_text_tokens.extend(block_tokens)
                    end_idx = len(full_text_tokens)
                    block_positions.append((start_idx, end_idx, block))
            
            # Sliding window match
            match_threshold = 0.7  # 70% of tokens must match
            min_matches = max(3, int(len(chunk_tokens) * match_threshold))
            
            for i in range(len(full_text_tokens) - min_matches + 1):
                window = full_text_tokens[i:i + len(chunk_tokens)]
                
                # Count matching tokens
                matches = sum(1 for j, t in enumerate(chunk_tokens) 
                             if j < len(window) and t == window[j])
                
                if matches >= min_matches:
                    # Found a match - collect all blocks that overlap with this window
                    window_end = i + len(chunk_tokens)
                    for start_idx, end_idx, block in block_positions:
                        if start_idx < window_end and end_idx > i:
                            if block not in matching_blocks:
                                matching_blocks.append(block)
                    break  # Found match on this page
        
        return matching_blocks
    
    def _find_exact_match(self, chunk_text: str, page_hint: Optional[int] = None) -> List[PDFTextBlock]:
        """
        Fallback: Find blocks containing exact substring match.
        Used for very short chunks.
        """
        normalized_chunk = self._normalize_text(chunk_text)
        matching_blocks = []
        
        for block in self.text_blocks:
            if page_hint is not None and block.page_index != page_hint - 1:
                continue
            
            normalized_block = self._normalize_text(block.text)
            if normalized_chunk in normalized_block or normalized_block in normalized_chunk:
                matching_blocks.append(block)
        
        return matching_blocks
    
    def _merge_adjacent_areas(self, areas: List[HighlightArea]) -> List[HighlightArea]:
        """
        Merge vertically adjacent highlight areas on the same page.
        This creates cleaner highlighting for multi-line text.
        """
        if len(areas) <= 1:
            return areas
        
        # Sort by page, then by top position
        sorted_areas = sorted(areas, key=lambda a: (a.pageIndex, a.top))
        
        merged = []
        current = sorted_areas[0]
        
        for next_area in sorted_areas[1:]:
            if (current.pageIndex == next_area.pageIndex and
                abs(current.top + current.height - next_area.top) < 1.0):  # Within 1% vertical gap
                # Merge horizontally adjacent areas
                new_left = min(current.left, next_area.left)
                new_right = max(current.left + current.width, next_area.left + next_area.width)
                new_top = min(current.top, next_area.top)
                new_bottom = max(current.top + current.height, next_area.top + next_area.height)
                
                current = HighlightArea(
                    pageIndex=current.pageIndex,
                    left=new_left,
                    top=new_top,
                    width=new_right - new_left,
                    height=new_bottom - new_top
                )
            else:
                merged.append(current)
                current = next_area
        
        merged.append(current)
        return merged
    
    def find_chunk_highlights(self, chunk_id: str, chunk_text: str, 
                              page_hint: Optional[int] = None) -> Optional[ChunkHighlight]:
        """
        Find highlight areas for a single RAG chunk.
        
        Args:
            chunk_id: Unique identifier for the chunk
            chunk_text: The text content to find
            page_hint: Optional page number (1-based) to prioritize search
        
        Returns:
            ChunkHighlight object with all matching areas, or None if not found
        """
        matching_blocks = self._find_matching_blocks(chunk_text, page_hint)
        
        if not matching_blocks:
            logger.warning(f"No matches found for chunk {chunk_id}")
            return None
        
        # Convert blocks to highlight areas
        areas = [block.to_highlight_area() for block in matching_blocks]
        
        # Merge adjacent areas
        merged_areas = self._merge_adjacent_areas(areas)
        
        # Determine the primary page index (most common page)
        page_counts: Dict[int, int] = {}
        for area in merged_areas:
            page_counts[area.pageIndex] = page_counts.get(area.pageIndex, 0) + 1
        
        primary_page = max(page_counts, key=page_counts.get) if page_counts else 0
        
        return ChunkHighlight(
            chunkId=chunk_id,
            pageIndex=primary_page,
            text=chunk_text,
            areas=merged_areas
        )
    
    def find_all_highlights(self, chunks: List[Dict[str, Any]]) -> List[ChunkHighlight]:
        """
        Find highlights for multiple RAG chunks.
        
        Args:
            chunks: List of dicts with 'id', 'text', and optional 'page' keys
        
        Returns:
            List of ChunkHighlight objects
        """
        highlights = []
        
        for chunk in chunks:
            chunk_id = chunk.get("id", "unknown")
            chunk_text = chunk.get("text", "")
            page_hint = chunk.get("page")
            
            if not chunk_text:
                continue
            
            result = self.find_chunk_highlights(chunk_id, chunk_text, page_hint)
            if result:
                highlights.append(result)
        
        return highlights
    
    def close(self) -> None:
        """Close the PDF document."""
        if self.doc:
            self.doc.close()
            self.doc = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def extract_highlights_from_pdf(pdf_path: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Main function to extract highlight data from PDF for given chunks.
    
    Args:
        pdf_path: Path to the PDF file
        chunks: List of chunk dicts with 'id', 'text', and optional 'page' keys
    
    Returns:
        Dict with fileId and highlights array compatible with frontend
    """
    import os
    
    try:
        with PDFHighlighter(pdf_path) as highlighter:
            highlights = highlighter.find_all_highlights(chunks)
            
            return {
                "fileId": os.path.basename(pdf_path),
                "highlights": [h.to_dict() for h in highlights]
            }
    except Exception as e:
        logger.error(f"Failed to extract highlights from {pdf_path}: {e}")
        return {
            "fileId": os.path.basename(pdf_path) if pdf_path else "unknown",
            "highlights": []
        }
