import { describe, expect, it } from "vitest";
import { createClient, installE2ECleanupHooks } from "./setup.js";

installE2ECleanupHooks();

describe("streaming behavior", () => {
  const itLLM = it.skipIf(!process.env.SAGE_E2E_LLM);

  itLLM("agent/run returns started with runId", async () => {
    const client = createClient();
    const result = await client.request("agent/run", { message: "Say hello" });

    expect(result).toEqual(
      expect.objectContaining({
        status: "started",
        runId: expect.any(String),
      }),
    );
  });

  itLLM("stream/delta notification is emitted during run", async () => {
    const client = createClient();
    await client.request("agent/run", { message: "Say hello briefly" });

    const delta = await client.waitForNotification("stream/delta", 15000);
    expect(delta).toEqual(
      expect.objectContaining({
        delta: expect.any(String),
      }),
    );
  });

  itLLM("usage/update or turn/completed arrives after run starts", async () => {
    const client = createClient();
    await client.request("agent/run", {
      message: "Say hello and finish in one sentence.",
    });

    const update = await Promise.race([
      client.waitForNotification("usage/update", 20000),
      client.waitForNotification("turn/completed", 20000),
    ]);

    expect(update).toBeTruthy();
  });
});
