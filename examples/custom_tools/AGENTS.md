---
name: tool-agent
model: azure_ai/gpt-4o
tools:
  - examples.custom_tools.tools
max_turns: 10
model_params:
  temperature: 0.1
  max_tokens: 2048
  seed: 0
---

You are an assistant with custom tools.
