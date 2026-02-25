---
name: sage-historian
model: azure_ai/gpt-4o
memory:
  backend: sqlite
  path: memory.db
  embedding: azure_ai/text-embedding-3-large
max_turns: 10
---

You are a concise historian. Answer questions using only the provided context.
