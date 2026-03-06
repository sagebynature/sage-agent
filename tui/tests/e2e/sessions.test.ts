import { describe, expect, it } from "vitest";
import { createClient, installE2ECleanupHooks } from "./setup.js";

installE2ECleanupHooks();

describe("session management", () => {
  const itLLM = it.skipIf(!process.env.SAGE_E2E_LLM);

  it("session/list returns an array", async () => {
    const client = createClient();
    const response = await client.request("session/list", {});

    expect(response).toEqual(
      expect.objectContaining({
        sessions: expect.any(Array),
      }),
    );
  });

  it("session/clear returns cleared boolean", async () => {
    const client = createClient();
    const response = await client.request("session/clear", {
      session_id: "non-existent-session",
    });

    expect(response).toEqual(
      expect.objectContaining({
        cleared: expect.any(Boolean),
      }),
    );
  });

  itLLM("session/list can include active sessions after a run", async () => {
    const client = createClient();
    await client.request("agent/run", {
      message: "Say hello in one short sentence.",
    });

    const response = await client.request("session/list", {});
    const sessions = response as { sessions?: unknown[] };
    expect(Array.isArray(sessions.sessions)).toBe(true);
  });
});
