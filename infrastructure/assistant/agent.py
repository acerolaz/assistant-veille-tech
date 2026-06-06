"""Assistant Nauda Palisse — agent LangChain branché sur le LLM Kimi-K2.6 (Azure AI).

L'agent dispose des outils :
- ``query_db``        : exécute une requête SQL prédéfinie
- ``***`` : ****
"""

from __future__ import annotations

from langchain.agents import create_agent

from app.rag.llm import get_llm, SYSTEM_PROMPT
from app.assistant.tools import query_db, query_feedbacks

def build_agent():
    llm = get_llm()
    tools = [query_db, query_feedbacks]
    # TODO: re-bind query_feedbacks après le refactor du module tools
    # tools.append(query_feedbacks)
    return create_agent(llm, tools=tools, system_prompt=SYSTEM_PROMPT)


def ask(question: str) -> str:
    agent = build_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content


if __name__ == "__main__":
    print(ask("Quelles sont les derniers articles techniques que tu as ingéré cette semaine ?"))
