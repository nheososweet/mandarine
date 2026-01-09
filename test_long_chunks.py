"""
Test with LONG chunks from actual LightRAG API response.
"""

import json
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

sys.path.insert(0, str(Path(__file__).parent))

from app.services.rag.lightrag_highlighter import LightRAGHighlighter

# FULL chunks from your actual API response
LONG_CHUNKS = [
    {
        "reference_id": "1",
        "content": "- Đối với các ngày t ừ thứ 2 đến thứ 6 hàng tuần: người lao động sẽ được thanh toán 150% ti ền \nlương thực trả của NLĐ \n- Đối với ngày nghỉ là Thứ 7 và chủ nhật: Người lao đông s ẽ được thanh toán 200% ti ền lương \nthực trả của NLĐ \n- Đối với các ngày lễ , tết: Người lao động được thanh toán 300% tiền lương thực trả của NLĐ \n- Nhân sự onsite: Theo quy định của khách hàng \n- Trợ cấp onsite: 150.000 VNĐ/ ngày – Áp dụng làm việc tại địa chỉ khách hàng \nRemote áp dụng cho dự án làm full 2 ngày T7/ tháng \nTrợ cấp không tính vào lương để tính OT \nRemote nửa ngày t7 không được tính trợ cấp 150.000 \n- Đối với lịch làm lịch \n- Nhân sự onsite làm 2 ngày thứ 7, thứ 7 tính 100% lương \n- Nhân sự onsite làm 3 ngày thứ 7: 2 ngày thứ 7 tính 100% lương, 1 ngày thứ 7 tính 200% lương \n- Nhân sự onsite làm 4 ngày th ứ 7 : 2 ngày th ứ 7 tính 100% lương, 2 ngày th ứ 7 tính 200% \nlương \n4. Các mức thưởng \n- Thưởng các dịp lễ, tết",
        "file_path": "noiquy.pdf",
        "chunk_id": "chunk-2677e46299b15f5053a9739f90dde745"
    }
]

pdf_path = Path(__file__).parent / "uploads" / "noiquy.pdf"

if not pdf_path.exists():
    print(f"❌ PDF not found at {pdf_path}")
    sys.exit(1)

print("✅ Testing with LONG chunks from actual API...")
print(f"   Chunk content length: {len(LONG_CHUNKS[0]['content'])} chars\n")

try:
    with LightRAGHighlighter(str(pdf_path)) as highlighter:
        result = highlighter.find_chunk_highlights(
            LONG_CHUNKS[0]['chunk_id'],
            LONG_CHUNKS[0]['content']
        )
        
        if result:
            print(f"✅ SUCCESS: Found {len(result.areas)} areas on page {result.pageIndex + 1}")
            for area in result.areas:
                print(f"   - Page {area.pageIndex + 1}: ({area.left:.1f}%, {area.top:.1f}%)")
        else:
            print("❌ FAILED: No highlights found")
            
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
