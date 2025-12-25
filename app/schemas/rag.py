from pydantic import BaseModel
from typing import List, Optional

# Request
class QueryRequest(BaseModel):
    question: str

# Response (cho API get sources)
class SourceDoc(BaseModel):
    source: str
    page: int
    preview: str

class SourcesResponse(BaseModel):
    sources: List[SourceDoc]