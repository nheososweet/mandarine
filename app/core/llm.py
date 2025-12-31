from langchain_openai import ChatOpenAI
from app.core.config import settings

llm = ChatOpenAI(
    model="openai/gpt-oss-20b",
    stream_usage=True,
    # temperature=None,
    # max_tokens=None,
    # timeout=None,
    reasoning_effort="low",
    temperature=0,
    # max_retries=2,
    # api_key="...",  # If you prefer to pass api key in directly
    base_url=settings.LLM_BASE_URL,
    api_key="empty"
    # organization="...",
    # other params...
)