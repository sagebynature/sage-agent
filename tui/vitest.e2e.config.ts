import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/e2e/**/*.test.ts"],
    testTimeout: 30000,
    hookTimeout: 15000,
    sequence: { concurrent: false },
    globals: true,
  },
});
