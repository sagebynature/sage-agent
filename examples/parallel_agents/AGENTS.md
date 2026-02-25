---
name: orchestrator
model: azure_ai/gpt-4o
subagents:
  - research_agent
  - summarize_agent
model_params:
  temperature: 0.5
  max_tokens: 4096
  timeout: 120.0
---

You are an orchestrator that coordinates research and summarization.
