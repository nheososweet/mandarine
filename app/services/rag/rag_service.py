import os
import shutil
import logging
from typing import List, AsyncGenerator
import json
# --- Latest LangChain Core Imports ---
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# --- Community Imports ---
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

# --- App Imports ---
from app.core.config import settings
from app.core.llm import llm  # Import LLM đã config từ file llm.py của bạn
from app.core.exceptions import (
    FileProcessingError, 
    VectorDBError, 
    BadRequestException
)

# Setup Logger
logger = logging.getLogger(__name__)

class RagService:
    def __init__(self):
        """
        Initialize RAG Service.
        We use a single persistent ChromaDB instance.
        """
        try:
            # 1. Setup Embedding (Gemini 004 is great for multilingual/Vietnamese)
            self.embedding_model = GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004",
                google_api_key=settings.GEMINI_API_KEY
            )

            # 2. Setup Vector Store (Chroma)
            # This will create a folder locally to save data
            self.vector_db = Chroma(
                persist_directory=settings.VECTOR_DB_PATH,
                embedding_function=self.embedding_model
            )
            
            # 3. Bind LLM
            self.llm = llm

        except Exception as e:
            logger.critical(f"RAG Service Init Failed: {e}")
            raise VectorDBError(f"System Initialization Error: {str(e)}")

    async def ingest_files(self, files: List[any]) -> dict:
        """
        Flow: Upload -> Save Temp -> Load -> Split -> Embed -> Store
        """
        if not files:
            raise BadRequestException("No files uploaded")

        documents = []
        errors = []
        temp_dir = "temp_ingest_uploads"
        os.makedirs(temp_dir, exist_ok=True)

        try:
            for file in files:
                file_path = os.path.join(temp_dir, file.filename)
                
                # Save file to disk
                try:
                    with open(file_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                except Exception as e:
                    logger.error(f"Save file error {file.filename}: {e}")
                    errors.append(f"{file.filename}: Save failed")
                    continue

                # Load logic
                try:
                    if file.filename.endswith(".pdf"):
                        loader = PyPDFLoader(file_path)
                    elif file.filename.endswith(".docx"):
                        loader = Docx2txtLoader(file_path)
                    else:
                        logger.warning(f"Skipping {file.filename}")
                        continue
                    
                    # Load content
                    docs = loader.load()
                    if not docs:
                        logger.warning(f"Empty file: {file.filename}")
                        continue
                        
                    documents.extend(docs)

                except Exception as e:
                    logger.error(f"Load error {file.filename}: {e}")
                    errors.append(f"{file.filename}: {str(e)}")

            if not documents:
                raise FileProcessingError(
                    message="No valid content found in uploaded files",
                    details={"errors": errors}
                )

            # Split Text (Vietnamese Context Optimized)
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                separators=["\n\n", "\n", ".", " ", ""]
            )
            chunks = text_splitter.split_documents(documents)

            # Store to Vector DB
            # Chroma automatically calls Gemini Embedding here
            self.vector_db.add_documents(chunks)

            return {
                "status": "success",
                "files_processed": len(files),
                "chunks_added": len(chunks),
                "errors": errors if errors else None
            }

        except Exception as e:
            if isinstance(e, FileProcessingError): raise e
            raise VectorDBError(f"Ingestion failed: {str(e)}")
        
        finally:
            # Cleanup temp files
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # async def query_rag_stream(self, question: str) -> AsyncGenerator[str, None]:
    #     """
    #     Logic RAG viết theo kiểu tuần tự từng bước (Step-by-step).
    #     Dễ debug, dễ hiểu luồng dữ liệu.
    #     """
    #     try:
    #         # BƯỚC 1: RETRIEVAL (Tìm kiếm dữ liệu)
    #         logger.info(f"--- [STEP 1] Searching for: {question} ---")
            
    #         retriever = self.vector_db.as_retriever(search_kwargs={"k": 4})
    #         # Gọi hàm invoke trực tiếp để lấy list documents về biến 'docs'
    #         docs = retriever.invoke(question) 
            
    #         # ---> DEBUG: Tại đây bạn có thể log thoải mái <---
    #         logger.info(f"Found {len(docs)} documents.")
    #         for i, doc in enumerate(docs):
    #             logger.info(f"Doc {i+1}: {doc.metadata.get('source')} - {doc.page_content}")

    #         # BƯỚC 2: CONTEXT PREPARATION (Chuẩn bị dữ liệu ghép vào prompt)
    #         # Nối nội dung các trang tìm được thành 1 chuỗi văn bản dài
    #         context_text = "\n\n".join([doc.page_content for doc in docs])
            
    #         # ---> DEBUG: Xem context gộp lại trông thế nào
    #         # logger.info(f"Full Context: {context_text[:200]}...")

    #         # BƯỚC 3: PROMPT CONSTRUCTION (Tạo Prompt)
    #         template = """Bạn là trợ lý AI hữu ích. Dựa vào ngữ cảnh sau để trả lời câu hỏi.
            
    #         Ngữ cảnh:
    #         {context}
            
    #         Câu hỏi: {question}
    #         """
    #         prompt_template = ChatPromptTemplate.from_template(template)
            
    #         # Thay thế biến {context} và {question} vào template
    #         # Kết quả 'messages' là một list các object Message (SystemMessage, HumanMessage)
    #         messages = prompt_template.format_messages(
    #             context=context_text,
    #             question=question
    #         )

    #         # ---> DEBUG: Xem chính xác những gì sắp gửi cho AI
    #         logger.info(f"--- [STEP 3] Sending Message to AI ---")
    #         logger.info(f"Prompt content: {messages[0].content[:200]}...") # Log 200 ký tự đầu của prompt

    #         # BƯỚC 4: GENERATION (Gọi AI & Stream)
    #         # Gọi hàm astream trực tiếp của LLM với danh sách messages đã tạo
    #         async for chunk in self.llm.astream(messages):
    #             # chunk ở đây là object AIMessageChunk, ta cần lấy .content
    #             # content = chunk.content
    #             # if content:
    #             #     yield content
    #             chunk_data = chunk.model_dump()
    #             yield json.dumps(chunk_data) + "\n"

    async def query_rag_stream(self, question: str) -> AsyncGenerator[str, None]:
        """
        Stream response - yield NGUYÊN BẢN từ LLM, không parse!
        """
        try:
            # STEP 1: Retrieval
            logger.info(f"Searching for: {question}")
            retriever = self.vector_db.as_retriever(search_kwargs={"k": 4})
            docs = retriever.invoke(question) 
            
            # STEP 2: Prepare Context
            context_text = "\n\n".join([doc.page_content for doc in docs])
            
            # STEP 3: Build Prompt
            template = """Bạn là trợ lý AI hữu ích. Dựa vào ngữ cảnh sau để trả lời câu hỏi.
            
            Ngữ cảnh:
            {context}
            
            Câu hỏi: {question}
            """
            prompt_template = ChatPromptTemplate.from_template(template)
            messages = prompt_template.format_messages(
                context=context_text,
                question=question
            )
            
            # STEP 4: Stream - Yield NGUYÊN CHUNK TỪ MODEL!
            async for chunk in self.llm.astream(messages):
                # Serialize toàn bộ chunk object (giữ nguyên structure)
                chunk_json = chunk.model_dump()  # hoặc chunk.dict() tùy version
                yield f"data: {json.dumps(chunk_json)}\n\n"
            
            # Kết thúc stream
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        except Exception as e:
            logger.error(f"Error in manual flow: {e}")
            yield f"[SYSTEM_ERROR]: {str(e)}"

   
    def get_sources(self, question: str) -> List[dict]:
        """
        Get metadata source for UI
        """
        try:
            retriever = self.vector_db.as_retriever(search_kwargs={"k": 3})
            docs = retriever.invoke(question)
            return [
                {
                    "source": os.path.basename(doc.metadata.get("source", "unknown")),
                    "page": doc.metadata.get("page", 0),
                    "preview": doc.page_content[:100] + "..."
                } for doc in docs
            ]
        except Exception as e:
            raise VectorDBError(f"Retrieve source failed: {e}")

    def reset_db(self):
        """
        Dev Utility: Clear all data
        """
        try:
            self.vector_db.delete_collection()
            return {"status": "Database cleared"}
        except Exception as e:
            raise VectorDBError(str(e))

rag_service = RagService()