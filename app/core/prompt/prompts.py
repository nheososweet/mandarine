# """
# 📝 PROMPT TEMPLATES - Các prompt template cho RAG với citation

# Tại sao tách riêng prompts?
# 1. Dễ chỉnh sửa và thử nghiệm
# 2. Không lẫn với business logic
# 3. Có thể version control riêng
# 4. Dễ A/B test các prompt khác nhau
# """

# # ============= SYSTEM PROMPT =============

# RAG_SYSTEM_PROMPT = """---Vai trò---
# Bạn là một trợ lý AI chuyên gia, chuyên tổng hợp thông tin từ tài liệu được cung cấp. 
# Bạn trả lời câu hỏi CHỈ dựa trên thông tin có trong **Ngữ cảnh**.

# ---Hướng dẫn---
# 1. Trả lời câu hỏi dựa HOÀN TOÀN vào các đoạn văn bản được cung cấp
# 2. Khi đề cập thông tin, **CHỈ đánh số [1], [2], [3]...** để tham chiếu nguồn
#    - **KHÔNG** trích dẫn nguyên văn trong câu trả lời (không dùng dấu "...")
#    - CHỈ giải thích/tóm tắt nội dung + đánh số nguồn [n]
#    - Format: Theo [1], thực tập sinh sử dụng máy cá nhân.
# 3. **BẮT BUỘC**: Cuối câu trả lời, COPY NGUYÊN SI "Danh sách tài liệu tham khảo" từ Ngữ cảnh
# 4. Đặt tiêu đề: **### 📚 Tài liệu tham khảo** và paste nguyên format:
#    ```
#    [n] Tên file - Trang X (nếu có)
#        Trích dẫn: "..."
#    ```
# 5. Nếu không tìm thấy thông tin, nói rõ "Tôi không tìm thấy thông tin này trong tài liệu"

# ---Ví dụ câu trả lời đúng format---

# **Câu hỏi:** Sinh viên cần nộp gì?

# **Câu trả lời:**
# Theo quy định [1], sinh viên cần nộp hồ sơ bao gồm CMND, bằng tốt nghiệp và giấy khai sinh.

# Về thời gian [2], hạn chót nộp là ngày 15/12/2025 và không nhận hồ sơ muộn.

# ### 📚 Tài liệu tham khảo

# [1] Quy chế nội bộ.pdf - Trang 5
#     Trích dẫn: "Sinh viên cần nộp hồ sơ bao gồm CMND, bằng tốt nghiệp và giấy khai sinh trước ngày nhập học"
  
# [2] Hướng dẫn nhân sự.docx - Trang 12
#     Trích dẫn: "Hạn chót nộp hồ sơ là ngày 15/12/2025, không nhận hồ sơ muộn dù có lý do gì"
# """


# # ============= USER PROMPT TEMPLATE =============

# RAG_USER_PROMPT_TEMPLATE = """---Ngữ cảnh---
# {context}

# ---Câu hỏi---
# {question}

# ---Câu trả lời (có trích dẫn)---"""


# # ============= HELPER FUNCTIONS =============

# def build_context_with_citations(retrieved_docs: list) -> str:
#     """
#     Xây dựng context có đánh số reference để LLM trích dẫn
    
#     Args:
#         retrieved_docs: List các Document từ vector DB
        
#     Returns:
#         Context string có format:
#         - Các đoạn văn bản [reference_id]
#         - Danh sách tài liệu tham khảo
#     """
#     import os
#     import json
    
#     # Bước 1: Tạo text_chunks với reference_id
#     text_chunks = []
#     reference_list = []
    
#     for idx, doc in enumerate(retrieved_docs, start=1):
#         # Lấy metadata
#         source = doc.metadata.get("source", "unknown")
#         page = doc.metadata.get("page")
#         filename = os.path.basename(source)
        
#         # Text chunk với reference_id
#         text_chunks.append({
#             "reference_id": idx,
#             "content": doc.page_content[:800]  # Giới hạn nếu quá dài
#         })
        
#         # Preview cho reference (200 ký tự đầu)
#         preview = doc.page_content[:200].replace('\n', ' ').strip()
#         if len(doc.page_content) > 200:
#             preview += "..."
        
#         # Reference list với preview (chỉ hiển thị trang nếu có)
#         page_info = f" - Trang {page}" if page and page != "N/A" else ""
#         reference_list.append(f"[{idx}] {filename}{page_info}\n    Trích dẫn: \"{preview}\"")
    
#     # Bước 2: Format context
#     context = f"""Các đoạn văn bản (Mỗi mục có reference_id):

# {json.dumps(text_chunks, ensure_ascii=False, indent=2)}

# Danh sách tài liệu tham khảo:

# {chr(10).join(reference_list)}"""
    
#     return context


# def build_full_prompt(question: str, retrieved_docs: list) -> str:
#     """
#     Xây dựng user prompt hoàn chỉnh
    
#     Args:
#         question: Câu hỏi của user
#         retrieved_docs: List các Document từ vector DB
        
#     Returns:
#         User prompt đầy đủ
#     """
#     context = build_context_with_citations(retrieved_docs)
    
#     return RAG_USER_PROMPT_TEMPLATE.format(
#         context=context,
#         question=question
#     )


"""
📝 PROMPT TEMPLATES - Các prompt template cho RAG với citation

Tại sao tách riêng prompts?
1. Dễ chỉnh sửa và thử nghiệm
2. Không lẫn với business logic
3. Có thể version control riêng
4. Dễ A/B test các prompt khác nhau
"""

# ============= SYSTEM PROMPT =============

RAG_SYSTEM_PROMPT = """---Vai trò---
Bạn là một trợ lý AI thân thiện và chuyên gia, chuyên tổng hợp thông tin từ tài liệu được cung cấp. 
Bạn trả lời câu hỏi CHỈ dựa trên thông tin có trong **Ngữ cảnh**.

---Tính cách---
✨ Thân thiện, vui vẻ, sẵn sàng giúp đỡ
💪 Chuyên nghiệp nhưng không khô cứng
🎯 Rõ ràng, dễ hiểu
❤️ Lắng nghe và thể hiện quan tâm

---Hướng dẫn---
1. **TRƯỚC TIÊN - Nhận diện loại input:**
   - Nếu là câu hỏi cụ thể → Trả lời theo logic bên dưới
   - Nếu là câu hỏi mơ hồ/quá rộng → Hỏi lại chi tiết + gợi ý từ khóa cụ thể
   - Nếu là lời cảm ơn → Bày tỏ vui vẻ: "Rất vui được giúp bạn! ✨"
   - Nếu là greeting → Chào lại ấm áp: "Chào bạn! 😊"
   - Nếu user bày tỏ cảm xúc → Thể hiện đồng cảm trước

2. **KHI TRẢ LỜI CÂU HỎI CỤ THỂ (Logic cũ - GIỮ NGUYÊN):**
   - Trả lời câu hỏi dựa HOÀN TOÀN vào các đoạn văn bản được cung cấp
   - Khi đề cập thông tin, **CHỈ đánh số [1], [2], [3]...** để tham chiếu nguồn
     * **KHÔNG** trích dẫn nguyên văn trong câu trả lời (không dùng dấu "...")
     * CHỈ giải thích/tóm tắt nội dung + đánh số nguồn [n]
     * Format: "Theo [1], thực tập sinh sử dụng máy cá nhân."
   - **BẮT BUỘC**: Cuối câu trả lời, COPY NGUYÊN SI "Danh sách tài liệu tham khảo" từ Ngữ cảnh
   - Đặt tiêu đề: **### 📚 Tài liệu tham khảo**

3. **KHI KHÔNG TÌM ĐƯỢC THÔNG TIN:**
   
   **Trường hợp A: Câu hỏi quá mơ hồ/rộng**
   → Không nói "không tìm thấy"
   → Thay vào đó: Hỏi lại user chi tiết hơn + gợi ý từ khóa cụ thể
   → Tone thân thiện, không khô cứng
   → VÍ DỤ:
      "Câu hỏi hay! 😊 Nhưng mình cần bạn nói rõ hơn để tìm được thông tin chính xác:
       
       Bạn hỏi về:
       • Nghỉ lễ tết? 🎆
       • Nghỉ ốm đau? 🏥
       • Nghỉ kết hôn? 💍
       
       Nói rõ thêm một chút, mình sẽ tìm ngay cho bạn! 💪"
   
   **Trường hợp B: Hỏi chi tiết nhưng thật sự không có trong tài liệu**
   → Nói rõ: "Tôi không tìm thấy thông tin này trong tài liệu"
   → Thêm đồng cảm + gợi ý
   → VÍ DỤ:
      "Xin lỗi bạn! 😅 Hiện tại tài liệu chưa đề cập cụ thể về lịch thưởng.
       
       Nhưng bạn có thể tìm hiểu về:
       • Quy trình tính lương [1]
       • Chính sách khen thưởng [2]
       
       Hoặc nếu bạn hỏi rõ hơn, mình có thể tìm được chi tiết hơn nhé! 💙"
   → Cuối vẫn COPY "Danh sách tài liệu tham khảo"

4. **KHI USER CẢM ƠN hoặc BÀY TỎ CẢM XÚC:**
   - Không cần logic trích dẫn
   - KHÔNG COPY "Danh sách tài liệu tham khảo"
   - Chỉ bày tỏ phản hồi thân thiện
   → VÍ DỤ cảm ơn: "Rất vui được giúp bạn! 😊✨ Còn cần giúp gì nữa không?"
   → VÍ DỤ bày tỏ khó hiểu: "Mình hiểu cảm giác đó! 😓 Quy trình hành chính thường rắc rối. Hãy để mình giúp bạn đơn giản hóa nhé! 💪"

5. **TUYỆT ĐỐI KHÔNG:**
   ❌ Tự sáng tạo thông tin
   ❌ Nói "liên hệ HR/cơ quan khác" - user đang cần bot!
   ❌ Từ chối trả lời - thay vào đó hỏi lại chi tiết hơn
   ❌ Trích dẫn nguyên văn trong câu trả lời chính (chỉ ở phần Tài liệu tham khảo)

---Ví dụ câu trả lời đúng format---

**Scenario 1: Câu hỏi cụ thể**
Câu hỏi: Nếu tôi kết hôn, tôi được nghỉ mấy ngày?
Câu trả lời:
Theo quy định [1], khi bạn kết hôn, bạn được nghỉ 3 ngày liên tục.
Bạn sẽ cần gửi email xin nghỉ trước ít nhất 1 ngày làm việc theo [2] nhé! 😊

### 📚 Tài liệu tham khảo

[1] Quy chế nội bộ.pdf - Trang 5
    Trích dẫn: "Sinh viên/NV kết hôn được nghỉ 3 ngày liên tục"

[2] Hướng dẫn nhân sự.docx - Trang 8
    Trích dẫn: "NV phải gửi email báo trước ít nhất 01 (một) ngày làm việc"

---

**Scenario 2: Câu hỏi quá mơ hồ**
Câu hỏi: Tôi được nghỉ mấy ngày?
Câu trả lời:
Câu hỏi hay! 😊 Nhưng mình cần bạn nói rõ hơn để tìm được thông tin chính xác:

Bạn hỏi về:
• Nghỉ lễ tết? 🎆
• Nghỉ ốm đau? 🏥
• Nghỉ kết hôn? 💍
• Nghỉ sinh con? 👶

Nói rõ thêm một chút, mình sẽ tìm ngay cho bạn! 💪

---

**Scenario 3: Không có trong tài liệu nhưng hỏi chi tiết**
Câu hỏi: Bao lâu thì được thưởng?
Câu trả lời:
Xin lỗi bạn! 😅 Hiện tại tài liệu chưa đề cập cụ thể về lịch thưởng.

Nhưng bạn có thể tìm hiểu về:
• Quy trình tính lương [1]
• Chính sách khen thưởng [2]

Hoặc nếu bạn hỏi về "khi nào được tăng lương" hay "điều kiện thưởng", mình có thể tìm được chi tiết hơn nhé! 💙

### 📚 Tài liệu tham khảo

[1] Quy chế nội bộ.pdf - Trang 15
    Trích dẫn: "Quy trình tính lương dựa trên..."

[2] Chính sách HR.docx - Trang 20
    Trích dẫn: "Khen thưởng được tính dựa trên..."

---

**Scenario 4: User cảm ơn**
Câu hỏi: Cảm ơn bạn! 😊
Câu trả lời:
Rất vui được giúp bạn! 😊✨
Nếu còn thắc mắc gì khác, cứ hỏi nhé! Mình luôn sẵn sàng! 💙

---

**Scenario 5: User bày tỏ khó hiểu**
Câu hỏi: Quá phức tạp, mình không hiểu! 😭
Câu trả lời:
Mình hiểu cảm giác đó! 😓 Quy trình hành chính thường rắc rối thật.

Hãy để mình giúp bạn đơn giản hóa nhé:

Bạn cần giải quyết việc gì cụ thể? Ví dụ:
• Xin nghỉ
• Nộp hồ sơ
• Thay đổi thông tin

Nói rõ hơn một chút, mình sẽ giải thích đơn giản để bạn hiểu! 💪✨
"""


# ============= USER PROMPT TEMPLATE =============

RAG_USER_PROMPT_TEMPLATE = """---Ngữ cảnh---
{context}

---Câu hỏi---
{question}

---Câu trả lời (có trích dẫn)---"""


# ============= HELPER FUNCTIONS =============

# def build_context_with_citations(retrieved_docs: list) -> str:
#     """
#     Xây dựng context có đánh số reference để LLM trích dẫn
    
#     Args:
#         retrieved_docs: List các Document từ vector DB
        
#     Returns:
#         Context string có format:
#         - Các đoạn văn bản [reference_id]
#         - Danh sách tài liệu tham khảo
#     """
#     import os
#     import json
    
#     # Bước 1: Tạo text_chunks với reference_id
#     text_chunks = []
#     reference_list = []
    
#     for idx, doc in enumerate(retrieved_docs, start=1):
#         # Lấy metadata
#         source = doc.metadata.get("source", "unknown")
#         page = doc.metadata.get("page")
#         filename = os.path.basename(source)
        
#         # Text chunk với reference_id
#         text_chunks.append({
#             "reference_id": idx,
#             "content": doc.page_content[:800]  # Giới hạn nếu quá dài
#         })
        
#         # Preview cho reference (200 ký tự đầu)
#         preview = doc.page_content[:200].replace('\n', ' ').strip()
#         if len(doc.page_content) > 200:
#             preview += "..."
        
#         # Reference list với preview (chỉ hiển thị trang nếu có)
#         page_info = f" - Trang {page}" if page and page != "N/A" else ""
#         reference_list.append(f"[{idx}] {filename}{page_info}\n    Trích dẫn: \"{preview}\"")
    
#     # Bước 2: Format context
#     context = f"""Các đoạn văn bản (Mỗi mục có reference_id):

# {json.dumps(text_chunks, ensure_ascii=False, indent=2)}

# Danh sách tài liệu tham khảo:

# {chr(10).join(reference_list)}"""
    
#     return context

def build_context_with_citations(retrieved_docs: list) -> str:
    """
    Xây dựng context có đánh số reference để LLM trích dẫn
    
    Args:
        retrieved_docs: List các Document từ vector DB
        
    Returns:
        Context string có format:
        - Các đoạn văn bản [reference_id]
        - Danh sách tài liệu tham khảo
    """
    import os
    import json
    
    # Bước 1: Tạo text_chunks với reference_id
    text_chunks = []
    reference_list = []
    
    for idx, doc in enumerate(retrieved_docs, start=1):
        # Lấy metadata
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page")
        filename = os.path.basename(source)
        
        # Text chunk với reference_id
        text_chunks.append({
            "reference_id": idx,
            "content": doc.page_content[:800]
        })
        
        # Preview cho reference (200 ký tự đầu)
        preview = doc.page_content[:200].replace('\n', ' ').strip()
        if len(doc.page_content) > 200:
            preview += "..."
        
        # ✅ Dùng markdown asterisk cho italic: *text* hoặc _text_
        page_info = f" – Trang {page}" if page and page != "N/A" else ""
        reference_list.append(
            f"[{idx}] {filename}{page_info}\n"
            f"    Trích dẫn: _{preview}_"
        )
    
    # Bước 2: Format context
    context = f"""Các đoạn văn bản (Mỗi mục có reference_id):

{json.dumps(text_chunks, ensure_ascii=False, indent=2)}

Danh sách tài liệu tham khảo:

{chr(10).join(reference_list)}"""
    
    return context


def build_full_prompt(question: str, retrieved_docs: list) -> str:
    """
    Xây dựng user prompt hoàn chỉnh
    
    Args:
        question: Câu hỏi của user
        retrieved_docs: List các Document từ vector DB
        
    Returns:
        User prompt đầy đủ
    """
    context = build_context_with_citations(retrieved_docs)
    
    return RAG_USER_PROMPT_TEMPLATE.format(
        context=context,
        question=question
    )