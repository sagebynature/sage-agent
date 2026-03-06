---
name: mcp-assistant
model: azure_ai/claude-sonnet-4-6
model_params:
  temperature: 0.0
  max_tokens: 4096
  timeout: 45.0
mcp_servers:
  filesystem:
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
max_turns: 10
permission:
  read: allow
  shell: allow
memory:
  path: mcp_agent_memory.db
---

You are an assistant that can interact with the filesystem via MCP.
