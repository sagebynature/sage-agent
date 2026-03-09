---
name: mcp-assistant
# model: azure_ai/claude-sonnet-4-6
model_params:
  temperature: 0.0
  max_tokens: 4096
  timeout: 45.0
enabled_mcp_servers: [filesystem]
max_turns: 10
permission:
  read: allow
  shell: allow
memory:
  path: mcp_agent_memory.db
---

You are an assistant that can interact with the filesystem via MCP.

This example expects a matching `config.toml` entry such as:

```toml
[mcp_servers.filesystem]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "."]
```
