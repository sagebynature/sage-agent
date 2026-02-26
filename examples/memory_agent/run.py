"""Memory agent example — semantic memory with Cohere embeddings.

Uses Cohere-embed-v3-english (Azure AI Foundry) to embed and retrieve
facts by semantic similarity, then feeds the recalled context to a
chat agent that answers questions.

Prerequisites:
    Ensure AZURE_AI_API_KEY and AZURE_AI_API_BASE are available via
    config.toml [env] section, .env file, or environment variables.

Usage:
    cd /path/to/sage
    uv run python examples/memory_agent/run.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from sage.agent import Agent
from sage.main_config import load_main_config, resolve_and_apply_env, resolve_main_config_path
from sage.memory.embedding import ProviderEmbedding
from sage.memory.sqlite_backend import SQLiteMemory
from sage.providers.litellm_provider import LiteLLMProvider

# Cohere is deployed on the Azure OpenAI-compatible path
# (/openai/deployments/…/embeddings), so use the "azure/" prefix.
# The "azure_ai/" prefix targets /models/…/embeddings which is 404 here.
EMBED_MODEL = "azure/Cohere-embed-v3-english"
CHAT_MODEL = "azure_ai/gpt-4o"
DB_PATH = Path(__file__).parent / "memory.db"

FACTS = [
    "The Apollo program was a NASA spaceflight program that landed the first humans on the Moon.",
    "Apollo 11 landed on July 20, 1969. Neil Armstrong was the first person to walk on the Moon.",
    "Buzz Aldrin joined Armstrong on the lunar surface during Apollo 11.",
    "Michael Collins remained in lunar orbit aboard the command module Columbia during Apollo 11.",
    "Apollo 13 suffered an oxygen tank explosion en route to the Moon in April 1970.",
    "The crew of Apollo 13 — Jim Lovell, Fred Haise, and Jack Swigert — returned safely to Earth.",
    "The Saturn V rocket stood 111 metres tall and remains the most powerful rocket ever flown.",
    "Flight director Gene Kranz led mission control during the Apollo 13 crisis.",
]

QUERIES = [
    "Who walked on the Moon during Apollo 11?",
    "What went wrong on Apollo 13?",
]


async def main() -> None:
    load_dotenv()
    config = load_main_config(resolve_main_config_path())
    resolve_and_apply_env(config)

    # Cohere-embed-v3-english via Azure AI Foundry.
    # Pass credentials explicitly: the azure/ provider reads AZURE_OPENAI_API_KEY
    # but this project uses AZURE_AI_API_KEY, so we forward it via api_key.
    embedding = ProviderEmbedding(
        LiteLLMProvider(
            EMBED_MODEL,
            api_base=os.environ["AZURE_AI_API_BASE"],
            api_key=os.environ["AZURE_AI_API_KEY"],
            api_version="2023-05-15",
        )
    )
    memory = SQLiteMemory(path=str(DB_PATH), embedding=embedding)
    await memory.initialize()
    await memory.clear()

    print(f"Storing {len(FACTS)} facts using {EMBED_MODEL}...\n")
    for fact in FACTS:
        await memory.store(fact)

    for query in QUERIES:
        recalled = await memory.recall(query, limit=3)
        context = "\n".join(f"- {e.content}" for e in recalled)

        agent = Agent(
            name="sage-historian",
            model=CHAT_MODEL,
            body=(
                "You are a concise historian. "
                "Answer using only the provided context.\n\n"
                f"Context:\n{context}"
            ),
        )

        print(f"Q: {query}")
        print("Recalled:")
        for e in recalled:
            print(f"  [{e.score:.3f}] {e.content[:72]}...")
        answer = await agent.run(query)
        print(f"A: {answer}\n")

    await memory.close()


if __name__ == "__main__":
    asyncio.run(main())
