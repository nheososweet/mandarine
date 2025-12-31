"""
FastAPI RAG System - Phiên bản đơn giản dễ hiểu với ChromaDB
Yêu cầu cài đặt:
pip install fastapi uvicorn python-multipart langchain langchain-openai langchain-google-genai langchain-chroma chromadb pypdf python-docx
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import tempfile
from pathlib import Path
import uuid
import shutil
from app.core.config import settings

# Imports cơ bản
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI

# Khởi tạo FastAPI app
app = FastAPI(title="RAG System API - Simple Version")

# Biến toàn cục lưu vector store
vector_store = None
embeddings = None
llm = None

# Cấu hình API keys
GOOGLE_API_KEY = settings.GEMINI_API_KEY
LLM_BASE_URL = settings.LLM_BASE_URL

# ChromaDB config
CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "rag_documents"

# Models cho request/response
class QuestionRequest(BaseModel):
    question: str
    top_k: Optional[int] = 3

class QuestionResponse(BaseModel):
    answer: str
    references: List[str]
    source_documents: List[dict]

# ============= BƯỚC 1: LOAD DOCUMENT =============

def load_document(file_path: str, file_extension: str):
    """
    Load tài liệu từ file
    - PDF: dùng PyPDFLoader
    - TXT: dùng TextLoader  
    - DOCX: dùng Docx2txtLoader
    """
    print(f"📄 Đang load file...")
    
    if file_extension == ".pdf":
        loader = PyPDFLoader(file_path)
    elif file_extension == ".txt":
        loader = TextLoader(file_path, encoding='utf-8')
    elif file_extension in [".docx", ".doc"]:
        loader = Docx2txtLoader(file_path)
    else:
        raise ValueError(f"File type không được hỗ trợ: {file_extension}")
    
    documents = loader.load()
    print(f"✅ Load xong {len(documents)} trang/đoạn")
    return documents

# ============= BƯỚC 2: CHUNK DOCUMENT =============

def chunk_documents(documents):
    """
    Chia tài liệu thành các đoạn nhỏ (chunks)
    - Mỗi chunk: 1000 ký tự
    - Overlap: 200 ký tự (để giữ context giữa các chunk)
    """
    print(f"✂️ Đang chia nhỏ tài liệu...")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,        # Mỗi chunk 1000 ký tự
        chunk_overlap=200,      # Chồng lấn 200 ký tự
        length_function=len,
    )
    
    chunks = text_splitter.split_documents(documents)
    print(f"✅ Chia xong thành {len(chunks)} chunks")
    return chunks

# ============= BƯỚC 3: TẠO EMBEDDINGS =============

def create_embeddings():
    """Tạo embedding model từ Gemini"""
    print(f"🔧 Khởi tạo Gemini Embedding model...")
    
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=GOOGLE_API_KEY
    )
    
    print(f"✅ Embedding model sẵn sàng")
    return embeddings

def create_vector_store(chunks, embeddings):
    """
    Tạo vector store (database vector) từ chunks với ChromaDB
    - Mỗi chunk sẽ được chuyển thành vector (embedding)
    - Lưu vào ChromaDB (persist trên disk)
    """
    print(f"🗄️ Đang tạo ChromaDB vector database...")
    
    # Tạo thư mục persist nếu chưa có
    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
    
    # Tạo unique IDs cho mỗi chunk
    ids = [str(uuid.uuid4()) for _ in chunks]
    
    # Tạo ChromaDB
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PERSIST_DIR,
        ids=ids
    )
    
    print(f"✅ ChromaDB đã sẵn sàng với {len(chunks)} vectors")
    return vector_store

def load_existing_vector_store(embeddings):
    """Load vector store đã tồn tại từ disk"""
    print(f"📂 Đang load ChromaDB từ {CHROMA_PERSIST_DIR}...")
    
    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR
    )
    
    count = vector_store._collection.count()
    print(f"✅ Load thành công {count} documents")
    return vector_store

# ============= BƯỚC 4: TÌM KIẾM RELEVANT DOCUMENTS =============

def search_relevant_docs(query: str, top_k: int = 3):
    """
    Tìm kiếm các đoạn văn bản liên quan đến câu hỏi
    - Query được chuyển thành vector
    - So sánh với các vectors trong database
    - Trả về top_k đoạn văn giống nhất
    """
    global vector_store
    
    if vector_store is None:
        raise ValueError("Vector store chưa được khởi tạo")
    
    print(f"🔍 Đang tìm kiếm {top_k} đoạn văn liên quan...")
    
    # Tìm kiếm similarity
    docs = vector_store.similarity_search(query, k=top_k)
    
    print(f"✅ Tìm thấy {len(docs)} đoạn văn liên quan")
    return docs

# ============= KHỞI TẠO LLM =============

def init_llm():
    """Khởi tạo LLM với config tùy chỉnh"""
    print(f"🔧 Đang khởi tạo LLM...")
    
    llm = ChatOpenAI(
        model="openai/gpt-oss-20b",
        base_url=LLM_BASE_URL,
        api_key="empty",
        stream_usage=True,
        reasoning_effort="low",
        temperature=0,
    )
    
    print(f"✅ LLM đã sẵn sàng")
    return llm

# ============= BƯỚC 5: TẠO CONTEXT VỚI TRÍCH DẪN =============

def build_context_with_references(context_docs: list):
    """
    Tạo context có reference_id và danh sách tài liệu tham khảo
    Format giống như prompt mẫu
    """
    # Tạo text chunks với reference_id
    text_chunks = []
    reference_list = []
    
    for idx, doc in enumerate(context_docs, start=1):
        # Lấy metadata
        source = doc.metadata.get('source', 'Unknown')
        page = doc.metadata.get('page', 'N/A')
        
        # Tạo tên file từ source path
        file_name = Path(source).name if source != 'Unknown' else 'Unknown'
        
        # Text chunk với reference_id
        chunk_info = {
            "reference_id": idx,
            "content": doc.page_content,
            "source": file_name,
            "page": page
        }
        text_chunks.append(chunk_info)
        
        # Reference list item
        if page != 'N/A':
            ref_item = f"[{idx}] {file_name} - Trang {page}"
        else:
            ref_item = f"[{idx}] {file_name}"
        reference_list.append(ref_item)
    
    # Format thành chuỗi
    import json
    text_chunks_str = json.dumps(text_chunks, ensure_ascii=False, indent=2)
    reference_list_str = "\n".join(reference_list)
    
    # Build context theo template
    context = f"""Các đoạn văn bản (Mỗi mục có một reference_id tương ứng với 'Danh sách tài liệu tham khảo'):

```json
{text_chunks_str}
```

Danh sách tài liệu tham khảo (Mỗi mục bắt đầu bằng [reference_id] tương ứng với các mục trong 'Các đoạn văn bản'):

```
{reference_list_str}
```"""
    
    return context, reference_list

# ============= BƯỚC 6: GỌI LLM VỚI PROMPT CÓ TRÍCH DẪN =============

def generate_answer_with_citations(question: str, context_docs: list):
    """
    Gọi LLM để generate câu trả lời CÓ TRÍCH DẪN
    - Format context với reference_id
    - LLM sẽ trả lời kèm [1], [2], [3]... 
    - Có mục "Tài liệu tham khảo" ở cuối
    """
    global llm
    
    print(f"🤖 Đang gọi LLM để generate câu trả lời có trích dẫn...")
    
    # Khởi tạo LLM nếu chưa có
    if llm is None:
        llm = init_llm()
    
    # Build context với references
    context, reference_list = build_context_with_references(context_docs)
    
    # Tạo prompt theo template
    system_prompt = """---Vai trò---
Bạn là một trợ lý AI chuyên gia, chuyên tổng hợp thông tin từ tài liệu được cung cấp. 
Bạn trả lời câu hỏi CHỈ dựa trên thông tin có trong **Ngữ cảnh**.

---Hướng dẫn---
1. Trả lời câu hỏi dựa HOÀN TOÀN vào các đoạn văn bản được cung cấp
2. Sử dụng trích dẫn [1], [2], [3]... khi đề cập đến thông tin từ các đoạn văn bản
3. Cuối câu trả lời, tạo mục "### Tài liệu tham khảo" liệt kê các nguồn đã sử dụng
4. Format: `- [n] Tên file - Trang X`
5. Nếu không tìm thấy thông tin, nói rõ "Tôi không tìm thấy thông tin này trong tài liệu"
6. Sử dụng Markdown để format câu trả lời rõ ràng

---Ví dụ định dạng Tài liệu tham khảo---
### Tài liệu tham khảo

- [1] Quy chế nội bộ.pdf - Trang 5
- [2] Hướng dẫn nhân sự.docx - Trang 12
"""
    
    user_prompt = f"""---Ngữ cảnh---
{context}

---Câu hỏi---
{question}

---Câu trả lời (có trích dẫn)---"""
    
    # Gọi LLM
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    response = llm.invoke(messages)
    answer = response.content
    
    print(f"✅ Đã nhận câu trả lời có trích dẫn từ LLM")
    
    return answer, reference_list

# ============= API ENDPOINTS =============

@app.get("/")
async def root():
    """Kiểm tra API có hoạt động không"""
    has_existing_db = os.path.exists(CHROMA_PERSIST_DIR) and os.path.isdir(CHROMA_PERSIST_DIR)
    
    return {
        "message": "RAG System API đang chạy",
        "status": "active",
        "documents_loaded": vector_store is not None,
        "has_persisted_data": has_existing_db
    }

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    ENDPOINT 1: Upload file và xử lý
    
    Flow đơn giản:
    1. Lưu file tạm thời
    2. Load document từ file
    3. Chia nhỏ thành chunks
    4. Tạo embeddings cho mỗi chunk
    5. Lưu vào ChromaDB (persist trên disk)
    """
    global vector_store, embeddings
    
    try:
        print("\n" + "="*50)
        print("BẮT ĐẦU XỬ LÝ FILE")
        print("="*50)
        
        # Kiểm tra loại file
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in [".pdf", ".txt", ".docx", ".doc"]:
            raise HTTPException(
                status_code=400,
                detail="Chỉ hỗ trợ file PDF, TXT, DOCX"
            )
        
        # Lưu file tạm thời
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        # BƯỚC 1: Load document
        documents = load_document(tmp_file_path, file_extension)
        
        # FIX: Cập nhật metadata với tên file gốc
        for doc in documents:
            doc.metadata['source'] = file.filename
            doc.metadata['original_filename'] = file.filename
        
        # BƯỚC 2: Chunk documents
        chunks = chunk_documents(documents)
        
        # BƯỚC 3: Tạo embeddings nếu chưa có
        if embeddings is None:
            embeddings = create_embeddings()
        
        # BƯỚC 4: Tạo hoặc update ChromaDB
        if vector_store is None:
            # Tạo mới hoặc load existing
            if os.path.exists(CHROMA_PERSIST_DIR):
                print("📂 Phát hiện ChromaDB đã tồn tại, đang load...")
                vector_store = load_existing_vector_store(embeddings)
                # Add thêm documents mới
                ids = [str(uuid.uuid4()) for _ in chunks]
                vector_store.add_documents(chunks, ids=ids)
                print(f"➕ Đã thêm {len(chunks)} chunks mới")
            else:
                vector_store = create_vector_store(chunks, embeddings)
        else:
            # Add documents vào vector store hiện tại
            ids = [str(uuid.uuid4()) for _ in chunks]
            vector_store.add_documents(chunks, ids=ids)
            print(f"➕ Đã thêm {len(chunks)} chunks mới")
        
        # Xóa file tạm
        os.unlink(tmp_file_path)
        
        print("="*50)
        print("HOÀN THÀNH XỬ LÝ FILE")
        print("="*50 + "\n")
        
        # Đếm tổng số documents
        total_docs = vector_store._collection.count()
        
        return JSONResponse(content={
            "message": "Upload và xử lý file thành công!",
            "filename": file.filename,
            "chunks_added": len(chunks),
            "total_documents": total_docs,
            "status": "ready"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")

@app.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """
    ENDPOINT 2: Hỏi đáp về tài liệu CÓ TRÍCH DẪN
    
    Flow đơn giản:
    1. Nhận câu hỏi từ user
    2. Tìm kiếm các đoạn văn liên quan trong vector store
    3. Build context với reference_id [1], [2], [3]...
    4. Gửi context + câu hỏi cho LLM
    5. LLM trả lời kèm trích dẫn trong câu trả lời
    6. Trả về: answer + references + source documents
    """
    global vector_store
    
    if vector_store is None:
        raise HTTPException(
            status_code=400,
            detail="Chưa có tài liệu nào được upload. Vui lòng upload file trước!"
        )
    
    try:
        print("\n" + "="*50)
        print(f"CÂU HỎI: {request.question}")
        print("="*50)
        
        # BƯỚC 1: Tìm các đoạn văn liên quan
        relevant_docs = search_relevant_docs(request.question, request.top_k)
        
        # BƯỚC 2: Generate câu trả lời CÓ TRÍCH DẪN
        answer, reference_list = generate_answer_with_citations(request.question, relevant_docs)
        
        # Format source documents chi tiết
        sources = []
        for i, doc in enumerate(relevant_docs, start=1):
            source_file = Path(doc.metadata.get('source', 'Unknown')).name
            page = doc.metadata.get('page', 'N/A')
            
            sources.append({
                "reference_id": i,
                "file_name": source_file,
                "page": page,
                "content_preview": doc.page_content[:300] + "...",
                "metadata": doc.metadata
            })
        
        print("="*50)
        print(f"TRẢ LỜI (có trích dẫn): {answer[:150]}...")
        print(f"SỐ TÀI LIỆU THAM KHẢO: {len(reference_list)}")
        print("="*50 + "\n")
        
        return QuestionResponse(
            answer=answer,
            references=reference_list,
            source_documents=sources
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")

@app.post("/load")
async def load_persisted_db():
    """Load ChromaDB đã được lưu trước đó"""
    global vector_store, embeddings
    
    if not os.path.exists(CHROMA_PERSIST_DIR):
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy ChromaDB đã lưu. Vui lòng upload file trước!"
        )
    
    try:
        # Tạo embeddings nếu chưa có
        if embeddings is None:
            embeddings = create_embeddings()
        
        # Load vector store
        vector_store = load_existing_vector_store(embeddings)
        
        total_docs = vector_store._collection.count()
        
        return {
            "message": "Load ChromaDB thành công!",
            "total_documents": total_docs,
            "status": "ready"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")

@app.delete("/reset")
async def reset_system():
    """Reset toàn bộ hệ thống và xóa ChromaDB"""
    global vector_store, embeddings, llm
    
    vector_store = None
    embeddings = None
    llm = None
    
    # Xóa ChromaDB folder
    if os.path.exists(CHROMA_PERSIST_DIR):
        shutil.rmtree(CHROMA_PERSIST_DIR)
        print(f"🗑️ Đã xóa ChromaDB tại {CHROMA_PERSIST_DIR}")
    
    return {"message": "Đã reset hệ thống và xóa database thành công"}

@app.get("/status")
async def get_status():
    """Kiểm tra trạng thái hệ thống"""
    has_persisted = os.path.exists(CHROMA_PERSIST_DIR)
    total_docs = 0
    
    if vector_store is not None:
        try:
            total_docs = vector_store._collection.count()
        except:
            pass
    
    return {
        "vector_store_loaded": vector_store is not None,
        "has_persisted_data": has_persisted,
        "total_documents": total_docs,
        "system_ready": vector_store is not None,
        "message": "Sẵn sàng" if vector_store is not None else "Chưa upload tài liệu"
    }

# ============= MAIN =============

if __name__ == "__main__":
    import uvicorn
    
    print("""
    ========================================
    🚀 RAG SYSTEM API - ChromaDB Version
    ========================================
    
    📌 API Endpoints:
    
    1. POST /upload
       → Upload file (PDF/TXT/DOCX)
       → Tự động chunk và embedding
       → Lưu vào ChromaDB (persist)
    
    2. POST /ask
       → Hỏi đáp về tài liệu (có trích dẫn)
       → Body: {"question": "câu hỏi của bạn"}
    
    3. POST /load
       → Load ChromaDB đã lưu từ lần trước
    
    4. GET /status
       → Kiểm tra hệ thống & số documents
    
    5. DELETE /reset
       → Xóa database và reset hệ thống
    
    ========================================
    🌐 Server đang chạy tại: http://localhost:8080
    📖 API docs: http://localhost:8080/docs
    ========================================
    """)
    
    uvicorn.run(app, host="0.0.0.0", port=8080)