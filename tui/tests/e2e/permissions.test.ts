import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { createClient, installE2ECleanupHooks } from "./setup.js";

installE2ECleanupHooks();

const here = fileURLToPath(new URL(".", import.meta.url));
const askAgentPath = resolve(here, "test-agent-ask.md");

describe("permission prompt flow", () => {
  const itLLM = it.skipIf(!process.env.SAGE_E2E_LLM);

  itLLM("permission/request is emitted for ask-gated shell tool", async () => {
    const client = createClient({ agentConfigPath: askAgentPath });
    await client.request("agent/run", {
      message: "Use shell to run 'pwd' and return the output.",
    });

    const request = await client.waitForNotification("permission/request", 20000);
    expect(request).toEqual(
      expect.objectContaining({
        tool: expect.any(String),
      }),
    );
  });

  itLLM("permission/respond allow_once resumes tool execution", async () => {
    const client = createClient({ agentConfigPath: askAgentPath });
    await client.request("agent/run", {
      message: "Run shell command 'ls' then summarize in one sentence.",
    });

    const permissionRequest = await client.waitForNotification("permission/request", 20000);
    const requestId = permissionRequest.request_id;
    expect(typeof requestId).toBe("string");

    await client.request("permission/respond", {
      request_id: requestId,
      decision: "allow_once",
    });

    const completed = await client.waitForNotification("tool/completed", 20000);
    expect(completed).toEqual(
      expect.objectContaining({
        toolName: expect.any(String),
      }),
    );
  });
});
