import os
import shutil
import logging
import json
from typing import List, AsyncGenerator
import fitz  # PyMuPDF
from langchain_core.documents import Document

# --- LangChain Imports ---
from langchain_community.document_loaders import Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

# --- App Imports ---
from app.core.config import settings
from app.core.llm import llm
from app.core.exceptions import VectorDBError, BadRequestException
from app.core.prompt.prompts import RAG_SYSTEM_PROMPT, build_full_prompt
from app.services.rag.pdf_highlighter import PDFHighlighter

logger = logging.getLogger(__name__)

class BasicRagService:
    def __init__(self):
        """
        Initialize RAG Service (Embedding & Vector DB).
        """
        try:
            self.embedding_model = GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004",
                google_api_key=settings.GEMINI_API_KEY
            )

            self.vector_db = Chroma(
                persist_directory=settings.VECTOR_DB_PATH,
                embedding_function=self.embedding_model
            )
            
            self.llm = llm

        except Exception as e:
            logger.critical(f"RAG Service Init Failed: {e}")
            raise VectorDBError(f"System Initialization Error: {str(e)}")

    async def ingest_files(self, files: List[any]) -> dict:
        """
        Main Logic: Upload -> Read File -> Split -> Embed -> Store.
        """
        if not files:
            raise BadRequestException("No files uploaded")

        documents = []
        permanent_dir = "uploads"
        os.makedirs(permanent_dir, exist_ok=True)

        try:
            for file in files:
                permanent_path = os.path.join(permanent_dir, file.filename)
                
                # 1. Save file to disk
                with open(permanent_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                # 2. Load file content (Simplified Inline Logic)
                try:
                    if file.filename.endswith(".pdf"):
                        # Minimal PyMuPDF read without helper function
                        with fitz.open(permanent_path) as pdf:
                            for page_num, page in enumerate(pdf):
                                text = page.get_text()
                                if text.strip():
                                    documents.append(Document(
                                        page_content=text,
                                        metadata={"source": permanent_path, "page": page_num + 1}
                                    ))
                                    
                    elif file.filename.endswith(".docx"):
                        loader = Docx2txtLoader(permanent_path)
                        documents.extend(loader.load())
                        
                except Exception as e:
                    logger.error(f"Failed to load {file.filename}: {e}")
                    continue

            if not documents:
                raise BadRequestException("No valid content extracted from files.")

            # 3. Split Text
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
                separators=["\n\n", "\n", ".", " ", ""]
            )
            chunks = text_splitter.split_documents(documents)

            # 4. Store in Vector DB
            self.vector_db.add_documents(chunks)

            return {
                "status": "success", 
                "chunks_added": len(chunks)
            }

        except Exception as e:
            raise VectorDBError(f"Ingestion failed: {str(e)}")
    
    async def query_rag_stream(self, question: str, request=None) -> AsyncGenerator[str, None]:
        """
        Main Logic: Retrieve -> Stream Answer -> Return Sources with Highlights.
        
        Highlight Extraction Process:
        1. After retrieving chunks from vector DB
        2. For each chunk, locate its exact position in the original PDF
        3. Use PDFHighlighter to extract bounding box coordinates
        4. Convert to percentage-based coordinates for react-pdf-viewer
        5. Return highlights array with each source
        """
        try:
            if not question.strip():
                raise BadRequestException("Empty question")
            
            # 1. Retrieve documents from vector DB
            retriever = self.vector_db.as_retriever(search_kwargs={"k": settings.RETRIEVAL_K})
            docs = retriever.invoke(question)
            
            if not docs:
                yield f"data: {json.dumps({'error': 'No documents found'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # 2. Group documents by source file for efficient highlight extraction
            docs_by_source = {}
            for idx, doc in enumerate(docs):
                source_path = doc.metadata.get("source", "")
                if source_path not in docs_by_source:
                    docs_by_source[source_path] = []
                docs_by_source[source_path].append({
                    "idx": idx,
                    "doc": doc,
                    "page": doc.metadata.get("page", 1)
                })
            
            # 3. Extract highlights for each source file
            all_sources = []
            
            for source_path, doc_list in docs_by_source.items():
                filename = os.path.basename(source_path) if source_path else "unknown"
                
                # Build base URL for static file serving
                base_url = ""
                if request:
                    base_url = str(request.base_url).rstrip("/")
                
                # Check if source is a PDF and extract highlights
                highlights = []
                if source_path and source_path.endswith(".pdf") and os.path.exists(source_path):
                    try:
                        # Prepare chunks for highlight extraction
                        chunks_for_highlight = [
                            {
                                "id": f"{item['idx']}_{item['page']}",
                                "text": item["doc"].page_content,
                                "page": item["page"]
                            }
                            for item in doc_list
                        ]
                        
                        # Extract highlights using PDFHighlighter
                        with PDFHighlighter(source_path) as highlighter:
                            chunk_highlights = highlighter.find_all_highlights(chunks_for_highlight)
                            
                            # Flatten all highlight areas
                            for ch in chunk_highlights:
                                for area in ch.areas:
                                    highlights.append({
                                        "pageIndex": area.pageIndex,
                                        "left": round(area.left, 4),
                                        "top": round(area.top, 4),
                                        "width": round(area.width, 4),
                                        "height": round(area.height, 4)
                                    })
                    except Exception as e:
                        logger.error(f"Highlight extraction failed for {source_path}: {e}")
                        # Continue without highlights if extraction fails
                
                # Build source entries for each document in this file
                for item in doc_list:
                    doc = item["doc"]
                    page_num = item["page"]
                    idx = item["idx"]
                    
                    # Filter highlights for this specific page
                    page_highlights = [h for h in highlights if h["pageIndex"] == page_num - 1]
                    
                    all_sources.append({
                        "id": f"{idx}_{page_num}",
                        "content": {"text": doc.page_content},
                        "source": filename,
                        "url": f"{base_url}/static/{filename}" if base_url else f"/static/{filename}",
                        "page": page_num,
                        "highlights": page_highlights if page_highlights else highlights  # All highlights if no page-specific
                    })
            
            # 4. Build Prompt & Messages
            user_prompt = build_full_prompt(question, docs)
            messages = [
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            
            # 5. Stream LLM Response
            async for chunk in self.llm.astream(messages):
                yield f"data: {json.dumps({'content': chunk.model_dump()}, ensure_ascii=False)}\n\n"
            
            # 6. Send Sources with Highlights
            yield f"data: {json.dumps({'sources': all_sources}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

basic_rag_service = BasicRagService()

