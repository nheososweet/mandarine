from langchain_openai import ChatOpenAI
from app.core.config import settings

llm = ChatOpenAI(
    model="cyankiwi/Qwen3-Omni-30B-A3B-Thinking-AWQ-4bit",
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