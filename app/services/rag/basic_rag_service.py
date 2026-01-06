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
    
    async def query_rag_stream(self, question: str) -> AsyncGenerator[str, None]:
        """
        Main Logic: Retrieve -> Stream Answer -> Return Sources.
        """
        try:
            if not question.strip():
                raise BadRequestException("Empty question")
            
            # 1. Retrieve
            retriever = self.vector_db.as_retriever(search_kwargs={"k": settings.RETRIEVAL_K})
            docs = retriever.invoke(question)
            
            if not docs:
                yield f"data: {json.dumps({'error': 'No documents found'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # 2. Prepare Sources (Simplified - No Bounding Boxes/Positions)
            sources = []
            for idx, doc in enumerate(docs):
                source_path = doc.metadata.get("source", "")
                page_num = doc.metadata.get("page", 1)
                filename = os.path.basename(source_path) if source_path else "unknown"
                
                sources.append({
                    "content": {"text": doc.page_content},
                    "id": f"{idx}_{page_num}",
                    "source": filename,
                    "page": page_num,
                    "position": None # Removed complex calculation logic
                })
            
            # 3. Build Prompt & Messages
            user_prompt = build_full_prompt(question, docs)
            messages = [
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            
            # 4. Stream LLM Response
            async for chunk in self.llm.astream(messages):
                yield f"data: {json.dumps({'content': chunk.model_dump()}, ensure_ascii=False)}\n\n"
            
            # 5. Send Sources
            yield f"data: {json.dumps({'sources': sources}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

basic_rag_service = BasicRagService()

