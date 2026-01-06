import os
import shutil
import logging
from typing import List, AsyncGenerator, Dict, Any
import json
import fitz  # PyMuPDF
from langchain_core.documents import Document

# --- Latest LangChain Core Imports ---
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# --- Community Imports ---
from langchain_community.document_loaders import Docx2txtLoader
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

    def _clean_text_for_matching(self, text: str) -> str:
        """
        Clean and normalize text for better matching accuracy.
        Removes extra whitespace, special chars, and normalizes encoding.
        
        Args:
            text: Raw text from PDF or vector DB
            
        Returns:
            Cleaned and normalized text
        """
        if not text:
            return ""
        
        # 1. Normalize unicode characters (Vietnamese accents, etc.)
        import unicodedata
        text = unicodedata.normalize('NFKC', text)
        
        # 2. Replace multiple whitespaces/newlines with single space
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # 3. Remove zero-width spaces and other invisible chars
        text = re.sub(r'[\u200b-\u200f\u2060\ufeff]', '', text)
        
        # 4. Strip leading/trailing whitespace
        text = text.strip()
        
        # 5. Normalize punctuation (remove excessive spaces around punctuation)
        text = re.sub(r'\s*([,.:;!?])\s*', r'\1 ', text)
        
        # 6. Remove soft hyphens and other PDF artifacts
        text = text.replace('\u00ad', '')  # Soft hyphen
        text = text.replace('\ufeff', '')  # BOM
        
        return text.lower()

    def _extract_pdf_text_only(self, file_path: str) -> List[Document]:
        """
        Extract text from PDF using PyMuPDF (without bbox).
        Used for ingestion - returns page-level documents.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List of Document objects (one per page)
        """
        documents = []
        
        try:
            pdf_document = fitz.open(file_path)
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                text = page.get_text()
                
                if text.strip():  # Only add non-empty pages
                    doc = Document(
                        page_content=text,
                        metadata={
                            "source": file_path,
                            "page": page_num + 1  # 1-indexed for consistency
                        }
                    )
                    documents.append(doc)
            
            pdf_document.close()
            logger.info(f"Extracted {len(documents)} pages from {os.path.basename(file_path)}")
            return documents
            
        except Exception as e:
            logger.error(f"PyMuPDF extraction error for {file_path}: {e}")
            raise FileProcessingError(f"Failed to extract PDF: {str(e)}")

    def _find_text_bbox_in_pdf(self, file_path: str, search_text: str, page_num: int) -> List[Dict[str, Any]]:
        """
        Search for text in a specific PDF page and return bounding boxes.
        
        Args:
            file_path: Path to PDF file
            search_text: Text to search for (can be chunk text)
            page_num: Page number (1-indexed)
            
        Returns:
            List of bbox dicts matching the text
        """
        try:
            pdf_document = fitz.open(file_path)
            
            # Validate page number (1-indexed)
            if page_num < 1 or page_num > len(pdf_document):
                logger.warning(f"Invalid page number {page_num} for {file_path}")
                return []
            
            page = pdf_document[page_num - 1]  # Convert to 0-indexed for PyMuPDF
            page_rect = page.rect
            
            # Extract ALL text blocks from the page with their bboxes
            blocks = page.get_text("blocks")
            
            # CLEAN search text for better matching
            search_cleaned = self._clean_text_for_matching(search_text[:300])
            
            matched_bboxes = []
            all_text_blocks = []  # Collect all blocks for fallback
            
            logger.info(f"Cleaned search text (first 100 chars): {search_cleaned[:100]}")
            
            # Try to find blocks that contain the search text
            for block in blocks:
                if len(block) >= 5:
                    block_text_raw = block[4].strip()
                    
                    if not block_text_raw:  # Skip empty blocks
                        continue
                    
                    # CLEAN block text
                    block_text_cleaned = self._clean_text_for_matching(block_text_raw)
                    
                    x0, y0, x1, y1 = block[:4]
                    bbox = {
                        "x1": float(x0),
                        "y1": float(y0),
                        "x2": float(x1),
                        "y2": float(y1),
                        "width": float(page_rect.width),
                        "height": float(page_rect.height),
                        "pageNumber": page_num
                    }
                    all_text_blocks.append(bbox)
                    
                    # MATCHING với cleaned text
                    # Strategy 1: Direct substring match
                    if search_cleaned in block_text_cleaned or block_text_cleaned in search_cleaned:
                        matched_bboxes.append(bbox)
                        logger.info(f"✓ Matched block (substring): {block_text_cleaned[:50]}...")
                        continue
                    
                    # Strategy 2: Fuzzy match on first 150 chars
                    if self._fuzzy_match(search_cleaned[:150], block_text_cleaned[:150]):
                        matched_bboxes.append(bbox)
                        logger.info(f"✓ Matched block (fuzzy): {block_text_cleaned[:50]}...")
            
            pdf_document.close()
            
            # FALLBACK: If no specific match, return all text blocks on page
            if not matched_bboxes and all_text_blocks:
                logger.warning(f"No exact match found, returning {len(all_text_blocks)} blocks from page {page_num}")
                return all_text_blocks[:5]  # Return first 5 blocks as representative sample
            
            return matched_bboxes
            
        except Exception as e:
            logger.error(f"Error finding bbox in {file_path}: {e}")
            return []
    
    def _fuzzy_match(self, text1: str, text2: str, threshold: float = 0.3) -> bool:
        """
        Check if two texts have significant overlap.
        
        Args:
            text1: First text
            text2: Second text
            threshold: Minimum ratio to consider match (0-1) - default 0.3 (30%)
            
        Returns:
            True if texts overlap significantly
        """
        if not text1 or not text2:
            return False
        
        # Split into words
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return False
        
        # Calculate Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        similarity = intersection / union if union > 0 else 0
        return similarity >= threshold

    async def ingest_files(self, files: List[any]) -> dict:
        """
        Flow: Upload -> Save Permanent -> Load -> Split -> Embed -> Store
        """
        if not files:
            raise BadRequestException("No files uploaded")

        documents = []
        errors = []
        
        # Use permanent upload directory
        permanent_dir = "uploads"
        os.makedirs(permanent_dir, exist_ok=True)

        try:
            for file in files:
                # Save to permanent location
                permanent_path = os.path.join(permanent_dir, file.filename)
                
                # Save file to disk (permanent)
                try:
                    with open(permanent_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                    logger.info(f"Saved {file.filename} to {permanent_path}")
                except Exception as e:
                    logger.error(f"Save file error {file.filename}: {e}")
                    errors.append(f"{file.filename}: Save failed")
                    continue

                # Load logic
                try:
                    if file.filename.endswith(".pdf"):
                        # Use PyMuPDF for PDF extraction
                        docs = self._extract_pdf_text_only(permanent_path)
                    elif file.filename.endswith(".docx"):
                        loader = Docx2txtLoader(permanent_path)
                        docs = loader.load()
                    else:
                        logger.warning(f"Skipping {file.filename}")
                        continue
                    
                    # Validate content
                    if not docs:
                        logger.warning(f"Empty file: {file.filename}")
                        continue
                    
                    # Update metadata with absolute path for later bbox search
                    for doc in docs:
                        doc.metadata["source"] = os.path.abspath(permanent_path)
                        
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
        Stream response with citations - yielding raw LLM chunks and final sources.
        """
        try:
            # STEP 1: Validate input
            if not question or not question.strip():
                raise BadRequestException("Question cannot be empty")
            
            # STEP 2: Retrieval - Find relevant documents
            logger.info(f"Searching for: {question}")
            retriever = self.vector_db.as_retriever(search_kwargs={"k": settings.RETRIEVAL_K})
            docs = retriever.invoke(question)
            
            # STEP 3: Check if documents were found
            if not docs:
                logger.warning(f"No documents found for: {question}")
                # Send an informative message to the client and stop
                yield f"data: {json.dumps({'error': 'Không tìm thấy tài liệu liên quan. Vui lòng upload file trước.'}, ensure_ascii=False)}\n\n"
                yield f"data: [DONE]\n\n"
                return
            
            # PREPARE SOURCES - Format tương thích với FE Mark.js
            sources = []
            for idx, doc in enumerate(docs):
                # Get source file path
                source_path = doc.metadata.get("source", "")
                page_num = doc.metadata.get("page", 1)
                text_content = doc.page_content
                
                # Debug logging
                logger.info(f"Processing doc {idx}: source={source_path}, page={page_num}, exists={os.path.exists(source_path)}")
                
                # Search for text bbox in PDF on-the-fly
                bboxes = []
                if source_path and source_path.endswith(".pdf") and os.path.exists(source_path):
                    # Use the full chunk text for matching (up to 500 chars for context)
                    search_text = text_content[:500].strip()
                    logger.info(f"Doc {idx}: Searching with {len(search_text)} chars")
                    bboxes = self._find_text_bbox_in_pdf(source_path, search_text, page_num)
                    
                    if bboxes:
                        logger.info(f"✓ Doc {idx}: Found {len(bboxes)} bboxes")
                    else:
                        logger.warning(f"✗ Doc {idx}: No bbox found on page {page_num}")
                else:
                    logger.warning(f"Cannot search bbox: path={source_path}, exists={os.path.exists(source_path) if source_path else False}")
                
                # Get filename
                filename = os.path.basename(source_path) if source_path else "unknown"
                
                # Use first bbox if found, otherwise None
                bbox = bboxes[0] if bboxes else None
                
                # Format matching FE TypeScript interface exactly
                source_entry = {
                    "content": {
                        "text": text_content
                    },
                    "position": {
                        "boundingRect": bbox,
                        "rects": bboxes,
                        "pageNumber": page_num
                    } if bboxes else None,
                    "comment": {
                        "text": "",
                        "emoji": ""
                    },
                    "id": f"{page_num}_{idx}_{hash(text_content) & 0xFFFFFFFF}",
                    # Additional metadata
                    "source": filename,
                    "page": page_num
                }
                
                sources.append(source_entry)
            
            # STEP 4: Build Prompt with citations
            user_prompt = build_full_prompt(question, docs)
            
            messages = [
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            
            # STEP 5: Stream - Yield raw chunks from the model
            async for chunk in self.llm.astream(messages):
                chunk_json = chunk.model_dump()
                yield f"data: {json.dumps({'content': chunk_json}, ensure_ascii=False)}\n\n"
            
            # STEP 6: Send the sources in the final chunk
            final_payload = {
                "sources": sources
            }
            yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"

            # STEP 7: End the stream
            yield "data: [DONE]\n\n"
            
        except BadRequestException as e:
            logger.warning(f"Bad request: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            
        except VectorDBError as e:
            logger.error(f"Vector DB error: {e}")
            yield f"data: {json.dumps({'error': 'Database unavailable'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Unexpected error in query_rag_stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': 'Server error'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

   
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
                    "content": doc.page_content
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