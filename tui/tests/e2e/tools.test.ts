import { describe, expect, it } from "vitest";
import { createClient, installE2ECleanupHooks } from "./setup.js";

installE2ECleanupHooks();

describe("tool execution flow", () => {
  const itLLM = it.skipIf(!process.env.SAGE_E2E_LLM);

  itLLM("tool/started notification is emitted for shell call", async () => {
    const client = createClient();
    await client.request("agent/run", {
      message: "Use the shell tool to run 'pwd' and show the result.",
    });

    const started = await client.waitForNotification("tool/started", 20000);
    expect(started).toEqual(
      expect.objectContaining({
        toolName: expect.any(String),
      }),
    );
  });

  itLLM("tool/completed notification follows tool execution", async () => {
    const client = createClient();
    await client.request("agent/run", {
      message: "Use the shell tool to run 'ls' and summarize output briefly.",
    });

    const completed = await client.waitForNotification("tool/completed", 25000);
    expect(completed).toEqual(
      expect.objectContaining({
        toolName: expect.any(String),
        durationMs: expect.any(Number),
      }),
    );
  });
});
