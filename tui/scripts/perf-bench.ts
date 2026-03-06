import { performance } from "node:perf_hooks";
import { createElement, isValidElement } from "react";
import { EventRouter } from "../src/integration/EventRouter.js";
import { appReducer, INITIAL_STATE, type AppAction } from "../src/state/AppContext.js";
import { METHODS } from "../src/types/protocol.js";

interface MeasurementStats {
  averageMs: number;
  minMs: number;
  maxMs: number;
  p95Ms: number;
}

interface MemorySnapshot {
  rss: number;
  heapTotal: number;
  heapUsed: number;
  external: number;
  arrayBuffers: number;
  heapUsedMB: number;
}

interface BenchResults {
  timestamp: string;
  startup: {
    coldStartupMs: number;
    appImportMs: number;
    eagerHeavyImportMs: number;
    lazySplitSavingsMs: number;
  };
  memory: {
    idle: MemorySnapshot;
    afterLoad: MemorySnapshot;
    delta: MemorySnapshot;
    messageCount: number;
  };
  streamingLatency: {
    stats: MeasurementStats;
    sampleCount: number;
    batchWindowMs: number;
  };
}

const BATCH_WINDOW_MS = 16;
const LATENCY_SAMPLES = 30;
const LATENCY_DELTAS_PER_SAMPLE = 12;
const MESSAGE_LOAD_COUNT = 5_000;
const MESSAGE_CHUNK = "synthetic message payload ".repeat(8);

function toMemorySnapshot(usage: NodeJS.MemoryUsage): MemorySnapshot {
  return {
    rss: usage.rss,
    heapTotal: usage.heapTotal,
    heapUsed: usage.heapUsed,
    external: usage.external,
    arrayBuffers: usage.arrayBuffers,
    heapUsedMB: Number((usage.heapUsed / (1024 * 1024)).toFixed(2)),
  };
}

function diffMemory(afterLoad: MemorySnapshot, idle: MemorySnapshot): MemorySnapshot {
  return {
    rss: afterLoad.rss - idle.rss,
    heapTotal: afterLoad.heapTotal - idle.heapTotal,
    heapUsed: afterLoad.heapUsed - idle.heapUsed,
    external: afterLoad.external - idle.external,
    arrayBuffers: afterLoad.arrayBuffers - idle.arrayBuffers,
    heapUsedMB: Number((afterLoad.heapUsedMB - idle.heapUsedMB).toFixed(2)),
  };
}

function buildStats(values: number[]): MeasurementStats {
  const sorted = [...values].sort((a, b) => a - b);
  const total = sorted.reduce((sum, value) => sum + value, 0);
  const p95Index = Math.max(0, Math.ceil(sorted.length * 0.95) - 1);
  return {
    averageMs: Number((total / sorted.length).toFixed(3)),
    minMs: Number((sorted[0] ?? 0).toFixed(3)),
    maxMs: Number((sorted[sorted.length - 1] ?? 0).toFixed(3)),
    p95Ms: Number((sorted[p95Index] ?? 0).toFixed(3)),
  };
}

function moduleUrl(relativePath: string): string {
  const url = new URL(relativePath, import.meta.url);
  url.searchParams.set("bench", `${Date.now()}-${Math.random()}`);
  return url.href;
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

async function measureImport(relativePath: string): Promise<number> {
  const startedAt = performance.now();
  await import(moduleUrl(relativePath));
  return performance.now() - startedAt;
}

async function measureStartup(): Promise<BenchResults["startup"]> {
  const startupStart = performance.now();
  const appModuleStart = performance.now();
  const appModule = await import(moduleUrl("../src/components/App.tsx"));
  const appImportMs = performance.now() - appModuleStart;

  const tree = createElement(appModule.App);
  if (!isValidElement(tree)) {
    throw new Error("Failed to create App component tree");
  }

  const coldStartupMs = performance.now() - startupStart;

  const eagerHeavyStart = performance.now();
  await Promise.all([
    import(moduleUrl("../src/components/AgentTree.tsx")),
    import(moduleUrl("../src/components/PlanningPanel.tsx")),
    import(moduleUrl("../src/components/BackgroundTaskPanel.tsx")),
  ]);
  const eagerHeavyImportMs = performance.now() - eagerHeavyStart;

  return {
    coldStartupMs: Number(coldStartupMs.toFixed(3)),
    appImportMs: Number(appImportMs.toFixed(3)),
    eagerHeavyImportMs: Number(eagerHeavyImportMs.toFixed(3)),
    lazySplitSavingsMs: Number((eagerHeavyImportMs - appImportMs).toFixed(3)),
  };
}

async function measureMemory(): Promise<BenchResults["memory"]> {
  if (typeof global.gc === "function") {
    global.gc();
  }

  const idle = toMemorySnapshot(process.memoryUsage());

  let state = INITIAL_STATE;
  for (let index = 0; index < MESSAGE_LOAD_COUNT; index += 1) {
    state = appReducer(state, {
      type: "ADD_MESSAGE",
      message: {
        id: `bench-${index}`,
        role: index % 2 === 0 ? "assistant" : "user",
        content: `${MESSAGE_CHUNK}${index}`,
        timestamp: Date.now(),
        isStreaming: false,
      },
    });
  }

  if (state.messages.length !== MESSAGE_LOAD_COUNT) {
    throw new Error("Synthetic load did not produce expected message count");
  }

  if (typeof global.gc === "function") {
    global.gc();
  }

  const afterLoad = toMemorySnapshot(process.memoryUsage());

  return {
    idle,
    afterLoad,
    delta: diffMemory(afterLoad, idle),
    messageCount: MESSAGE_LOAD_COUNT,
  };
}

async function measureStreamingLatency(): Promise<BenchResults["streamingLatency"]> {
  const samples: number[] = [];

  for (let sample = 0; sample < LATENCY_SAMPLES; sample += 1) {
    let state = INITIAL_STATE;
    let updateAt = 0;
    let startedAt = 0;

    const router = new EventRouter((action: AppAction) => {
      state = appReducer(state, action);
      if (action.type === "UPDATE_MESSAGE" && updateAt === 0) {
        updateAt = performance.now();
      }
    });

    startedAt = performance.now();
    router.handleNotification(METHODS.STREAM_DELTA, {
      turn: sample + 1,
      delta: "a",
    });

    for (let index = 0; index < LATENCY_DELTAS_PER_SAMPLE; index += 1) {
      router.handleNotification(METHODS.STREAM_DELTA, {
        turn: sample + 1,
        delta: "b",
      });
    }

    await wait(BATCH_WINDOW_MS + 8);
    router.dispose();

    if (updateAt === 0) {
      throw new Error("No UPDATE_MESSAGE action observed during latency benchmark");
    }

    samples.push(updateAt - startedAt);
  }

  return {
    stats: buildStats(samples),
    sampleCount: LATENCY_SAMPLES,
    batchWindowMs: BATCH_WINDOW_MS,
  };
}

async function main(): Promise<void> {
  const warmupImports = [
    "../src/components/ChatView.tsx",
    "../src/components/MessageBubble.tsx",
    "../src/components/StatusBar.tsx",
  ];

  for (const importPath of warmupImports) {
    await measureImport(importPath);
  }

  const results: BenchResults = {
    timestamp: new Date().toISOString(),
    startup: await measureStartup(),
    memory: await measureMemory(),
    streamingLatency: await measureStreamingLatency(),
  };

  process.stdout.write(`${JSON.stringify(results, null, 2)}\n`);
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.stack ?? error.message : String(error);
  process.stderr.write(`perf-bench failed: ${message}\n`);
  process.exitCode = 1;
});
