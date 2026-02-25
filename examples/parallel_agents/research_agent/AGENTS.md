---
name: researcher
model: azure_ai/gpt-4o
extensions:
  - sage.tools.builtins
max_turns: 15
model_params:
  temperature: 0.2
  max_tokens: 8192
  seed: 42
  timeout: 60.0
---

You are a thorough researcher. Find detailed information on any topic.
