from agno.agent import Agent
from agno.db.sqlite import AsyncSqliteDb
from agno.os import AgentOS
from agno.models.google import Gemini
from fastapi.middleware.cors import CORSMiddleware
assistant = Agent(
    name="Assistant",
    model=Gemini(id="gemini-2.5-flash", api_key="AIzaSyASpjxrg4K9xcaXwWff6BbKLXnvVlFiO8k"),
    instructions=["You are a helpful AI assistant."],
    markdown=True,
    stream=True,
)

agent_os = AgentOS(
    id="my-first-os",
    description="My first AgentOS",
    agents=[assistant],
)

app = agent_os.get_app()

CORS_ORIGINS = [
    "http://localhost",
    "https://localhost",
    "http://localhost:8000",
    "https://localhost:8000",
    "http://localhost:3201",
    "https://localhost:3201",
    "http://localhost:3000",
    "https://os.agno.com"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    # Default port is 7777; change with port=...
    agent_os.serve(app="my_os:app", reload=True)