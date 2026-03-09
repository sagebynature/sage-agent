import { describe, expect, it } from "vitest";
import { buildClientOptions } from "./cli.js";

describe("buildClientOptions", () => {
  it("returns default options when no flags are provided", () => {
    expect(buildClientOptions([])).toBeUndefined();
  });

  it("forwards --yolo to the backend serve command", () => {
    expect(buildClientOptions(["--yolo"])).toEqual({
      args: ["serve", "--yolo"],
    });
  });

  it("forwards -y to the backend serve command", () => {
    expect(buildClientOptions(["-y"])).toEqual({
      args: ["serve", "--yolo"],
    });
  });
});
