import { describe, expect, it } from "vitest";
import { createClient, installE2ECleanupHooks } from "./setup.js";

installE2ECleanupHooks();

describe("JSON-RPC protocol compliance", () => {
  it("initialize returns capabilities", async () => {
    const client = createClient();
    const response = await client.request("initialize", {});

    expect(response).toEqual(
      expect.objectContaining({
        capabilities: expect.objectContaining({
          streaming: true,
          tools: true,
          sessions: true,
        }),
        version: expect.any(String),
      }),
    );
  });

  it("session/list returns sessions array", async () => {
    const client = createClient();
    const response = await client.request("session/list", {});

    expect(response).toEqual(
      expect.objectContaining({
        sessions: expect.any(Array),
      }),
    );
  });

  it("tools/list returns tools array", async () => {
    const client = createClient();
    const response = await client.request("tools/list", {});

    expect(response).toEqual(
      expect.objectContaining({
        tools: expect.any(Array),
      }),
    );
  });

  it("config/get model returns string value", async () => {
    const client = createClient();
    const response = await client.request("config/get", { key: "model" });

    expect(response).toEqual(
      expect.objectContaining({
        key: "model",
        value: expect.any(String),
      }),
    );
  });

  it("invalid method returns JSON-RPC method-not-found", async () => {
    const client = createClient();

    await expect(client.request("does/not-exist", {})).rejects.toMatchObject({
      code: -32601,
    });
  });

  it("malformed JSON-RPC request returns parse error", async () => {
    const client = createClient();
    await expect(
      client.requestRaw(
        '{"jsonrpc":"1.0","method":"session/list","id":"parse-error","params":{}}',
        "parse-error",
      ),
    ).rejects.toMatchObject({
      code: -32700,
    });
  });

  it("missing method in request shape returns parse error", async () => {
    const client = createClient();
    await expect(
      client.requestRaw('{"jsonrpc":"2.0","id":"missing-method","params":{}}', "missing-method"),
    ).rejects.toMatchObject({
      code: -32700,
    });
  });

  it("raw invalid JSON line does not crash server", async () => {
    const client = createClient();
    client.sendRaw("{ not valid json");

    const response = await client.request("session/list", {});
    expect(response).toEqual(expect.objectContaining({ sessions: expect.any(Array) }));
  });
});
