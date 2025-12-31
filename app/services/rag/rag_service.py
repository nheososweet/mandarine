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
from app.core.prompt.prompts import RAG_SYSTEM_PROMPT, build_full_prompt

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
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
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
    #     Stream response với trích dẫn nguồn - yield NGUYÊN BẢN từ LLM
    #     """
    #     try:
    #         # STEP 1: Retrieval - Tìm tài liệu liên quan
    #         logger.info(f"Searching for: {question}")
    #         retriever = self.vector_db.as_retriever(search_kwargs={"k": 10})  # Tăng lên 6 để tìm nhiều hơn
    #         docs = retriever.invoke(question)
            
    #         # DEBUG: Log các docs đã tìm thấy
    #         logger.info(f"Found {len(docs)} documents")
    #         for i, doc in enumerate(docs, 1):
    #             preview = doc.page_content[:100].replace('\n', ' ')
    #             logger.info(f"Doc {i}: {os.path.basename(doc.metadata.get('source', 'unknown'))} - Page {doc.metadata.get('page', 'N/A')} - Preview: {preview}...")
            
    #         # STEP 2: Build Prompt với citations (sử dụng prompt từ file prompts.py)
    #         user_prompt = build_full_prompt(question, docs)
            
    #         # Tạo messages với system + user prompt
    #         messages = [
    #             {"role": "system", "content": RAG_SYSTEM_PROMPT},
    #             {"role": "user", "content": user_prompt}
    #         ]
            
    #         # STEP 4: Stream - Yield NGUYÊN CHUNK TỪ MODEL!
    #         async for chunk in self.llm.astream(messages):
    #             # Serialize toàn bộ chunk object (giữ nguyên structure)
    #             chunk_json = chunk.model_dump()  # hoặc chunk.dict() tùy version
    #             yield f"data: {json.dumps(chunk_json)}\n\n"
            
    #         # Kết thúc stream
    #         yield "data: [DONE]\n\n"
            
    #     except Exception as e:
    #         logger.error(f"Error: {e}")
    #         yield f"data: {json.dumps({'error': str(e)})}\n\n"

    #     except Exception as e:
    #         logger.error(f"Error in manual flow: {e}")
    #         yield f"[SYSTEM_ERROR]: {str(e)}"
    
    async def query_rag_stream(self, question: str) -> AsyncGenerator[str, None]:
        """
        Stream response với trích dẫn nguồn - yield NGUYÊN BẢN từ LLM
        """
        try:
            # STEP 1: Validate input
            if not question or not question.strip():
                raise BadRequestException("Question cannot be empty")
            
            # STEP 2: Retrieval - Tìm tài liệu liên quan
            logger.info(f"Searching for: {question}")
            retriever = self.vector_db.as_retriever(search_kwargs={"k": settings.RETRIEVAL_K})
            docs = retriever.invoke(question)
            
            # STEP 3: Check if found documents
            if not docs:
                logger.warning(f"No documents found for: {question}")
                yield f"data: {json.dumps({'error': 'Không tìm thấy tài liệu liên quan. Vui lòng upload file trước.'}, ensure_ascii=False)}\n\n"
                return
            
            # DEBUG: Log các docs đã tìm thấy
            logger.info(f"Found {len(docs)} documents")
            for i, doc in enumerate(docs, 1):
                preview = doc.page_content[:100].replace('\n', ' ')
                page_info = f"Page {doc.metadata.get('page')}" if doc.metadata.get('page') is not None else "(No page)"
                filename = os.path.basename(doc.metadata.get('source', 'unknown'))
                logger.info(f"Doc {i}: {filename} - {page_info} - Preview: {preview}...")
            
            # STEP 4: Build Prompt với citations
            user_prompt = build_full_prompt(question, docs)
            
            # Tạo messages với system + user prompt
            messages = [
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            
            # STEP 5: Stream - Yield NGUYÊN CHUNK TỪ MODEL!
            async for chunk in self.llm.astream(messages):
                chunk_json = chunk.model_dump()
                yield f"data: {json.dumps(chunk_json, ensure_ascii=False)}\n\n"
            
            # Kết thúc stream
            yield "data: [DONE]\n\n"
            
        except BadRequestException as e:
            logger.warning(f"Bad request: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            
        except VectorDBError as e:
            logger.error(f"Vector DB error: {e}")
            yield f"data: {json.dumps({'error': 'Database unavailable'}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"Unexpected error in query_rag_stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': 'Server error'}, ensure_ascii=False)}\n\n"

   
    def get_sources(self, question: str) -> List[dict]:
        """
        Get metadata source for UI
        """
        try:
            retriever = self.vector_db.as_retriever(search_kwargs={"k": settings.RETRIEVAL_K_SOURCES})
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

    # ============= DOCUMENT MANAGEMENT METHODS =============

    def get_all_documents(self) -> dict:
        """
        Lấy danh sách tất cả tài liệu từ Vector DB
        
        Returns:
            {
                "total": int,  # Số lượng files
                "total_chunks": int,  # Tổng số chunks
                "documents": List[dict]  # Danh sách documents
            }
        """
        try:
            # Lấy tất cả documents từ Chroma
            collection = self.vector_db._collection
            results = collection.get()
            
            if not results or not results.get('ids'):
                logger.info("No documents found in database")
                return {
                    "total": 0,
                    "total_chunks": 0,
                    "documents": []
                }
            
            # Group by source để tránh duplicate (mỗi file có nhiều chunks)
            documents_map = {}
            
            for doc_id, metadata, content in zip(
                results['ids'],
                results['metadatas'],
                results['documents']
            ):
                source = metadata.get('source', 'unknown')
                filename = os.path.basename(source)
                
                if filename not in documents_map:
                    # Tạo preview từ chunk đầu tiên
                    preview = content[:200].replace('\n', ' ').strip()
                    if len(content) > 200:
                        preview += "..."
                    
                    documents_map[filename] = {
                        "id": doc_id,  # ID của chunk đầu tiên
                        "filename": filename,
                        "source": source,
                        "page": metadata.get('page'),
                        "preview": preview,
                        "chunk_count": 1
                    }
                else:
                    # Tăng chunk count
                    documents_map[filename]["chunk_count"] += 1
            
            # Convert to list và sort
            documents_list = sorted(
                documents_map.values(),
                key=lambda x: x['filename']
            )
            
            logger.info(f"Retrieved {len(documents_list)} unique documents with {len(results['ids'])} total chunks")
            
            return {
                "total": len(documents_list),
                "total_chunks": len(results['ids']),
                "documents": documents_list
            }
            
        except Exception as e:
            logger.error(f"Failed to get all documents: {e}", exc_info=True)
            raise VectorDBError(f"Failed to retrieve documents: {str(e)}")

    def search_documents_by_filename(self, filename: str) -> List[dict]:
        """
        Tìm kiếm tài liệu theo tên file (partial match)
        
        Args:
            filename: Tên file cần tìm
            
        Returns:
            List[dict]: Danh sách documents khớp
        """
        try:
            all_docs_result = self.get_all_documents()
            all_docs = all_docs_result["documents"]
            
            # Filter theo filename (case-insensitive)
            filtered = [
                doc for doc in all_docs 
                if filename.lower() in doc['filename'].lower()
            ]
            
            logger.info(f"Found {len(filtered)} documents matching '{filename}'")
            return filtered
            
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            raise VectorDBError(f"Search failed: {str(e)}")

    def delete_document_by_source(self, filename: str) -> int:
        """
        Xóa TẤT CẢ chunks của 1 file khỏi Vector DB
        
        Args:
            filename: Tên file cần xóa
            
        Returns:
            int: Số chunks đã xóa
        """
        try:
            collection = self.vector_db._collection
            results = collection.get()
            
            if not results or not results.get('ids'):
                logger.warning("No documents in database")
                return 0
            
            # Tìm tất cả IDs của file cần xóa
            ids_to_delete = []
            
            for doc_id, metadata in zip(results['ids'], results['metadatas']):
                source = metadata.get('source', 'unknown')
                current_filename = os.path.basename(source)
                
                if current_filename == filename:
                    ids_to_delete.append(doc_id)
            
            if not ids_to_delete:
                logger.warning(f"Document '{filename}' not found")
                return 0
            
            # Xóa tất cả chunks của file
            collection.delete(ids=ids_to_delete)
            
            logger.info(f"Deleted {len(ids_to_delete)} chunks of document '{filename}'")
            return len(ids_to_delete)
            
        except Exception as e:
            logger.error(f"Failed to delete document '{filename}': {e}", exc_info=True)
            raise VectorDBError(f"Failed to delete document: {str(e)}")

    def get_database_stats(self) -> dict:
        """
        Lấy thống kê về vector database
        
        Returns:
            dict: Thông tin thống kê
        """
        try:
            all_docs_result = self.get_all_documents()
            
            return {
                "total_files": all_docs_result["total"],
                "total_chunks": all_docs_result["total_chunks"],
                "storage_path": settings.VECTOR_DB_PATH,
                "embedding_model": "models/text-embedding-004"
            }
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            raise VectorDBError(f"Failed to get statistics: {str(e)}")

rag_service = RagService()