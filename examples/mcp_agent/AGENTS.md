---
name: mcp-assistant
model: azure_ai/claude-sonnet-4-6
model_params:
  temperature: 0.0
  max_tokens: 4096
  timeout: 45.0
mcp_servers:
  - transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
max_turns: 10
permission:
  read: allow
  shell: allow
memory:
  backend: sqlite
  path: mcp_agent_memory.db
  embedding: azure_ai/text-embedding-3-large
---

You are an assistant that can interact with the filesystem via MCP.
