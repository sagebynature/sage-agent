# ADR-008: MCP Support via mcp Python Package

## Status
Accepted

## Context
The Model Context Protocol (MCP) is an emerging standard for connecting LLM applications to external tools and data sources. Supporting MCP enables Sage agents to use a growing ecosystem of MCP servers (filesystem, databases, web APIs) and expose Sage tools as MCP servers for other clients.

## Decision
Support MCP via the official `mcp` Python package with both client and server capabilities:

- **MCPClient:** Connects to MCP servers via stdio or SSE transport, discovers tools, and executes them. MCP tools are merged into the agent's tool registry at startup.
- **MCPServer:** Exposes a `ToolRegistry` as an MCP server over stdio, allowing external MCP clients to use Sage-defined tools.

Configuration is declarative in Markdown frontmatter:

```yaml
mcp_servers:
  - transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
```

## Consequences
**Positive:**
- Interoperability with the growing MCP ecosystem
- Agents can use any MCP-compatible server without custom integration code
- Sage tools can be consumed by any MCP client (Claude Desktop, etc.)
- Both stdio and SSE transports cover local and remote server scenarios

**Negative:**
- The MCP specification is still evolving; breaking changes may occur
- `mcp` package adds a dependency with its own transitive requirements
- stdio transport requires subprocess management and lifecycle handling
- MCP tool schemas may not align perfectly with Sage's `ToolSchema` format
