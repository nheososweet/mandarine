"""
Test script to debug highlight extraction from LightRAG response.
Reproduces the exact scenario with your JSON response.
"""

import json
import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s'
)

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.rag.lightrag_highlighter import LightRAGHighlighter

# Sample chunks - using FULL content from actual LightRAG API response
SAMPLE_CHUNKS = [
    {
        "reference_id": "1",
        "content": "- Đối với các ngày t ừ thứ 2 đến thứ 6 hàng tuần: người lao động sẽ được thanh toán 150% ti ền \nlương thực trả của NLĐ \n- Đối với ngày nghỉ là Thứ 7 và chủ nhật: Người lao đông s ẽ được thanh toán 200% ti ền lương \nthực trả của NLĐ \n- Đối với các ngày lễ , tết: Người lao động được thanh toán 300% tiền lương thực trả của NLĐ \n- Nhân sự onsite: Theo quy định của khách hàng \n- Trợ cấp onsite: 150.000 VNĐ/ ngày – Áp dụng làm việc tại địa chỉ khách hàng \nRemote áp dụng cho dự án làm full 2 ngày T7/ tháng \nTrợ cấp không tính vào lương để tính OT \nRemote nửa ngày t7 không được tính trợ cấp 150.000 \n- Đối với lịch làm lịch \n- Nhân sự onsite làm 2 ngày thứ 7, thứ 7 tính 100% lương \n- Nhân sự onsite làm 3 ngày thứ 7: 2 ngày thứ 7 tính 100% lương, 1 ngày thứ 7 tính 200% lương \n- Nhân sự onsite làm 4 ngày th ứ 7 : 2 ngày th ứ 7 tính 100% lương, 2 ngày th ứ 7 tính 200% \nlương",
        "file_path": "noiquy.pdf",
        "chunk_id": "chunk-2677e46299b15f5053a9739f90dde745"
    },
    {
        "reference_id": "1",
        "content": "Công ty Cổ phần Sphinx \nTầng 1, Tòa nhà HL, Số 6/82 Đường Duy Tân, Phường Dịch Vọng \nHậu, Quận Cầu Giấy, Hà Nội \n \n \n--------------------------------------------------------- \n \n \n \nNỘI QUY VÀ CHẾ ĐỘ LÀM VIỆC \nCông ty đề cao tinh thần chính trực và tự giác của các nhân viên bao gồm cả nhân viên chính thức và \nnhân viên thực tập",
        "file_path": "noiquy.pdf",
        "chunk_id": "chunk-4dbdb54df4671e6a2cfb35bc1d365f1a"
    }
]

def test_highlight_extraction():
    """Test highlight extraction with your sample chunks."""
    
    pdf_path = Path(__file__).parent / "uploads" / "noiquy.pdf"
    
    if not pdf_path.exists():
        print(f"❌ PDF not found at {pdf_path}")
        return False
    
    print(f"✅ PDF found at {pdf_path}")
    print(f"📊 Testing with {len(SAMPLE_CHUNKS)} sample chunks\n")
    
    try:
        with LightRAGHighlighter(str(pdf_path)) as highlighter:
            print("=" * 80)
            print("TESTING EACH CHUNK")
            print("=" * 80)
            
            for i, chunk in enumerate(SAMPLE_CHUNKS, 1):
                print(f"\n📄 Chunk {i}/{len(SAMPLE_CHUNKS)}")
                print(f"   ID: {chunk['chunk_id']}")
                print(f"   Content length: {len(chunk['content'])} chars")
                print(f"   Content preview: {chunk['content'][:80]}...")
                
                # Test single chunk
                result = highlighter.find_chunk_highlights(
                    chunk['chunk_id'], 
                    chunk['content']
                )
                
                if result:
                    print(f"   ✅ SUCCESS: Found {len(result.areas)} highlight areas on page {result.pageIndex + 1}")
                    for j, area in enumerate(result.areas, 1):
                        print(f"      Area {j}: Page {area.pageIndex + 1}, "
                              f"Position: ({area.left:.1f}%, {area.top:.1f}%) "
                              f"Size: {area.width:.1f}% × {area.height:.1f}%")
                else:
                    print(f"   ❌ FAILED: No highlights found")
            
            print("\n" + "=" * 80)
            print("TESTING ALL CHUNKS TOGETHER")
            print("=" * 80)
            
            all_results = highlighter.find_all_highlights(SAMPLE_CHUNKS)
            print(f"\n✅ Results: {len(all_results)}/{len(SAMPLE_CHUNKS)} chunks matched")
            
            for result in all_results:
                print(f"   {result.chunkId}: {len(result.areas)} areas on page {result.pageIndex + 1}")
            
            return len(all_results) > 0
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_highlight_extraction()
    sys.exit(0 if success else 1)
