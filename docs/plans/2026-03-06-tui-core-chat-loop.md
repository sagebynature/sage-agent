# TUI Core Chat Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Get the TUI end-to-end chat loop working: user sends message, agent streams response tokens in real time, run completes cleanly, errors are reported.

**Architecture:** The dispatcher switches from `agent.run()` to `agent.stream()` so the EventBridge can translate real-time LLM events into JSON-RPC notifications. A new `run/completed` notification signals the TUI when the run finishes (success, error, or cancel). The TUI EventRouter handles `run/completed` by flushing any pending stream batch and clearing `isStreaming`.

**Tech Stack:** Python (asyncio, click), TypeScript (React/Ink, vitest)

**Test commands:**
- Python: `cd /Users/sachoi/sagebynature/sage-agent && python -m pytest tests/test_protocol_dispatcher.py -v`
- TUI: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run src/integration/__tests__/EventRouter.test.ts`
- TUI wiring: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run src/integration/__tests__/wiring.test.tsx`

---

### Task 1: Backend — Switch dispatcher to streaming and add run/completed notification

**Files:**
- Modify: `sage/protocol/dispatcher.py:67-87`
- Test: `tests/test_protocol_dispatcher.py`

**Step 1: Write failing tests for streaming and run/completed**

Add three tests to `tests/test_protocol_dispatcher.py`:

```python
@pytest.mark.asyncio
async def test_agent_run_uses_stream_not_run() -> None:
    """agent/run should call agent.stream(), not agent.run()."""
    dispatcher, agent, _session_manager, server = _make_dispatcher()
    # Set up agent.stream as an async generator
    async def fake_stream(message: str):
        yield "hello "
        yield "world"
    agent.stream = MagicMock(side_effect=fake_stream)
    server.send_notification = AsyncMock()

    response = await dispatcher.dispatch(
        {"jsonrpc": "2.0", "id": 20, "method": "agent/run", "params": {"message": "hi"}}
    )

    assert response["result"]["status"] == "started"
    # Give the background task time to run
    await asyncio.sleep(0.1)
    agent.stream.assert_called_once_with("hi")


@pytest.mark.asyncio
async def test_agent_run_sends_completed_notification() -> None:
    """When streaming finishes, dispatcher sends run/completed notification."""
    dispatcher, agent, _session_manager, server = _make_dispatcher()
    async def fake_stream(message: str):
        yield "done"
    agent.stream = MagicMock(side_effect=fake_stream)
    server.send_notification = AsyncMock()

    await dispatcher.dispatch(
        {"jsonrpc": "2.0", "id": 21, "method": "agent/run", "params": {"message": "hi"}}
    )
    await asyncio.sleep(0.1)

    # Find the run/completed notification
    calls = server.send_notification.await_args_list
    completed_calls = [c for c in calls if c.args[0] == "run/completed"]
    assert len(completed_calls) == 1
    payload = completed_calls[0].args[1]
    assert payload["status"] == "success"
    assert "runId" in payload


@pytest.mark.asyncio
async def test_agent_run_sends_error_on_failure() -> None:
    """When streaming raises, dispatcher sends run/completed with error."""
    dispatcher, agent, _session_manager, server = _make_dispatcher()
    async def failing_stream(message: str):
        raise RuntimeError("model error")
        yield  # make it a generator
    agent.stream = MagicMock(side_effect=failing_stream)
    server.send_notification = AsyncMock()

    await dispatcher.dispatch(
        {"jsonrpc": "2.0", "id": 22, "method": "agent/run", "params": {"message": "hi"}}
    )
    await asyncio.sleep(0.1)

    calls = server.send_notification.await_args_list
    completed_calls = [c for c in calls if c.args[0] == "run/completed"]
    assert len(completed_calls) == 1
    payload = completed_calls[0].args[1]
    assert payload["status"] == "error"
    assert "model error" in payload["error"]
```

Note: add `import asyncio` to the test file imports if not already present.

**Step 2: Run tests to verify they fail**

Run: `cd /Users/sachoi/sagebynature/sage-agent && python -m pytest tests/test_protocol_dispatcher.py::test_agent_run_uses_stream_not_run tests/test_protocol_dispatcher.py::test_agent_run_sends_completed_notification tests/test_protocol_dispatcher.py::test_agent_run_sends_error_on_failure -v`

Expected: FAIL — `agent.stream` not called, no `run/completed` notification sent.

**Step 3: Implement streaming in dispatcher**

In `sage/protocol/dispatcher.py`, replace `_handle_agent_run` (lines 67-87) with:

```python
async def _handle_agent_run(self, request: dict[str, Any]) -> dict[str, Any]:
    if self.agent is None:
        raise RuntimeError("Agent is not configured")

    params = self._ensure_params_dict(request)
    message = params.get("message")
    if not isinstance(message, str) or not message:
        raise ValueError("'message' must be a non-empty string")

    run_id = str(uuid4())
    task = asyncio.create_task(self._run_streaming(run_id, message))
    self._run_tasks[run_id] = task
    self._current_run_id = run_id

    def _cleanup(_done: asyncio.Task[Any], rid: str = run_id) -> None:
        self._run_tasks.pop(rid, None)
        if self._current_run_id == rid:
            self._current_run_id = None

    task.add_done_callback(_cleanup)
    return {"status": "started", "runId": run_id}

async def _run_streaming(self, run_id: str, message: str) -> None:
    try:
        async for _chunk in self.agent.stream(message):
            pass  # EventBridge handles stream/delta notifications
        await self.server.send_notification(
            "run/completed", {"runId": run_id, "status": "success"}
        )
    except asyncio.CancelledError:
        await self.server.send_notification(
            "run/completed", {"runId": run_id, "status": "cancelled"}
        )
    except Exception as exc:
        await self.server.send_notification(
            "run/completed",
            {"runId": run_id, "status": "error", "error": str(exc)},
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sachoi/sagebynature/sage-agent && python -m pytest tests/test_protocol_dispatcher.py -v`

Expected: ALL PASS (including existing tests — the `agent.run` mock in `_make_dispatcher` is still there but no longer called by agent/run; existing `test_agent_run_returns_started_with_run_id` should still pass since we return the same shape).

**Step 5: Commit**

```bash
git add sage/protocol/dispatcher.py tests/test_protocol_dispatcher.py
git commit -m "feat(protocol): switch agent/run to streaming and add run/completed notification"
```

---

### Task 2: TUI — Add RUN_COMPLETED protocol constant and payload type

**Files:**
- Modify: `tui/src/types/protocol.ts:155-187`

**Step 1: Add RunCompletedPayload and RUN_COMPLETED constant**

In `tui/src/types/protocol.ts`, add the payload type after `ErrorPayload` (around line 162):

```typescript
export interface RunCompletedPayload {
  runId: string;
  status: "success" | "error" | "cancelled";
  error?: string;
}
```

Add `RUN_COMPLETED` to the `METHODS` constant (after `ERROR: "error"`):

```typescript
RUN_COMPLETED: "run/completed",
```

**Step 2: Verify types compile**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx tsc --noEmit`

Expected: No type errors.

**Step 3: Commit**

```bash
git add tui/src/types/protocol.ts
git commit -m "feat(tui): add RUN_COMPLETED protocol constant and payload type"
```

---

### Task 3: TUI — Handle run/completed in EventRouter

**Files:**
- Modify: `tui/src/integration/EventRouter.ts`
- Test: `tui/src/integration/__tests__/EventRouter.test.ts`

**Step 1: Write failing tests**

Add to `tui/src/integration/__tests__/EventRouter.test.ts`:

```typescript
it("maps run/completed success to SET_STREAMING false and finalizes message", () => {
  const router = createEventRouter(dispatch);

  // Simulate an active stream first
  router.handleNotification(METHODS.STREAM_DELTA, { delta: "hi", turn: 1 });

  dispatched.length = 0; // clear previous dispatches

  router.handleNotification(METHODS.RUN_COMPLETED, {
    runId: "run-1",
    status: "success",
  });

  const types = dispatched.map((a) => a.type);
  expect(types).toContain("SET_STREAMING");
  const streamingAction = dispatched.find((a) => a.type === "SET_STREAMING");
  expect(streamingAction).toEqual({ type: "SET_STREAMING", isStreaming: false });
});

it("maps run/completed error to SET_STREAMING false and SET_ERROR", () => {
  const router = createEventRouter(dispatch);

  router.handleNotification(METHODS.RUN_COMPLETED, {
    runId: "run-2",
    status: "error",
    error: "model exploded",
  });

  const types = dispatched.map((a) => a.type);
  expect(types).toContain("SET_STREAMING");
  expect(types).toContain("SET_ERROR");
  const errorAction = dispatched.find((a) => a.type === "SET_ERROR");
  expect(errorAction).toEqual({ type: "SET_ERROR", error: "model exploded" });
});

it("maps run/completed cancelled to SET_STREAMING false without error", () => {
  const router = createEventRouter(dispatch);

  router.handleNotification(METHODS.RUN_COMPLETED, {
    runId: "run-3",
    status: "cancelled",
  });

  const types = dispatched.map((a) => a.type);
  expect(types).toContain("SET_STREAMING");
  expect(types).not.toContain("SET_ERROR");
});
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run src/integration/__tests__/EventRouter.test.ts`

Expected: FAIL — `RUN_COMPLETED` not in METHODS or not handled.

**Step 3: Implement run/completed handler in EventRouter**

In `tui/src/integration/EventRouter.ts`:

1. Add to the imports (after `ErrorPayload`):
```typescript
import type { RunCompletedPayload } from "../types/protocol.js";
```

2. Add a new case in `handleNotification` switch (after `METHODS.ERROR`):
```typescript
case METHODS.RUN_COMPLETED:
  this.handleRunCompleted(this.parseRunCompleted(params));
  return;
```

3. Add the handler method (after `handleError`):
```typescript
private handleRunCompleted(params: RunCompletedPayload): void {
  this.flushBatch();

  // Mark the last streaming message as complete
  if (this.currentMessageId) {
    this.dispatch({
      type: "UPDATE_MESSAGE",
      id: this.currentMessageId,
      updates: { isStreaming: false },
    });
  }

  // Reset stream tracking state
  this.currentTurn = null;
  this.currentMessageId = null;
  this.accumulatedContent = "";

  this.dispatch({ type: "SET_STREAMING", isStreaming: false });

  if (params.status === "error" && params.error) {
    this.dispatch({ type: "SET_ERROR", error: params.error });
  }
}
```

4. Add the parser method (after `parseError`):
```typescript
private parseRunCompleted(params: Record<string, unknown>): RunCompletedPayload {
  const status = params.status;
  return {
    runId: this.asString(params.runId),
    status:
      status === "success" || status === "error" || status === "cancelled"
        ? status
        : "error",
    error: this.asOptionalString(params.error),
  };
}
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run src/integration/__tests__/EventRouter.test.ts`

Expected: ALL PASS.

**Step 5: Commit**

```bash
git add tui/src/integration/EventRouter.ts tui/src/integration/__tests__/EventRouter.test.ts
git commit -m "feat(tui): handle run/completed notification in EventRouter"
```

---

### Task 4: TUI — Subscribe to run/completed in wiring

**Files:**
- Modify: `tui/src/integration/wiring.ts:20-31`
- Test: `tui/src/integration/__tests__/wiring.test.tsx`

**Step 1: Write failing test**

Add to `tui/src/integration/__tests__/wiring.test.tsx`:

```typescript
it("routes run/completed notification to SET_STREAMING false", () => {
  const { client, emit } = createMockClient();
  wireIntegration({ client, dispatch, getState });

  emit(METHODS.RUN_COMPLETED, {
    runId: "run-1",
    status: "success",
  });

  const actionTypes = dispatch.mock.calls.map(([action]) => action.type);
  expect(actionTypes).toContain("SET_STREAMING");
});
```

Also update the existing `"registers handlers for all protocol notification methods"` test — it asserts the exact list of registered methods. Add `METHODS.RUN_COMPLETED` to the expected array.

**Step 2: Run tests to verify they fail**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run src/integration/__tests__/wiring.test.tsx`

Expected: FAIL — `RUN_COMPLETED` not in NOTIFICATION_METHODS.

**Step 3: Add RUN_COMPLETED to NOTIFICATION_METHODS**

In `tui/src/integration/wiring.ts`, add to the `NOTIFICATION_METHODS` array (after `METHODS.ERROR`):

```typescript
METHODS.RUN_COMPLETED,
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run src/integration/__tests__/wiring.test.tsx`

Expected: ALL PASS.

**Step 5: Commit**

```bash
git add tui/src/integration/wiring.ts tui/src/integration/__tests__/wiring.test.tsx
git commit -m "feat(tui): subscribe to run/completed in wiring layer"
```

---

### Task 5: Build and smoke test

**Step 1: Run full test suites**

```bash
cd /Users/sachoi/sagebynature/sage-agent && python -m pytest tests/test_protocol_dispatcher.py tests/test_event_bridge.py -v
cd /Users/sachoi/sagebynature/sage-agent/tui && npx vitest run
```

Expected: ALL PASS.

**Step 2: Rebuild TUI**

```bash
cd /Users/sachoi/sagebynature/sage-agent/tui && pnpm build
```

Expected: Build success.

**Step 3: Reinstall sage backend**

```bash
cd /Users/sachoi/sagebynature/sage-agent && uv tool install --editable .
```

**Step 4: Smoke test**

```bash
cd ~/github/sage-assistant && sage-tui
```

Type a message. Expected behavior:
- Model name appears in header (from `usage/update` after first turn)
- Response tokens stream in real time
- Spinner clears when response finishes
- `isStreaming` returns to false

**Step 5: Commit any fixes if needed, then final commit**

```bash
git add -A
git commit -m "feat(tui): complete core chat loop — streaming + run/completed"
```

---

## Phase 2 Backlog (deferred)

The following items from `docs/plans/2026-03-06-tui-wiring-design.md` are NOT addressed by this plan and should be tackled in a follow-up:

| # | Item |
|---|------|
| 6 | Integrate `JsonRpcPermissionHandler` in serve.py |
| 7 | Render `PermissionPrompt` in App and wire to `permission/respond` |
| 8 | Fix permission field name mismatch |
| 9 | Render `SlashCommands` autocomplete in `InputArea` |
| 10 | Implement 10 missing command handlers in CommandExecutor |
| 11 | Wire `PlanContext` to EventRouter |
| 12 | Implement `BACKGROUND_TASK_UPDATE` reducer |
| 13 | Implement `COMPACTION_STARTED` reducer |
| 14 | Wire unused hooks into AppShell |
| 15 | Wire `useMemoryMonitor` |
| 16 | Wire or remove `LifecycleManager` |
| 17 | Compute real `contextUsagePercent` |
| 18 | Wire session resume/fork/delete |
| 19 | Send error notification on failed runs (partially covered by this plan) |
| 20 | Remove dead code: `framing.py`, `SplitView.tsx`, `lifecycle.ts` |
| 21 | Wire Ctrl+C/ESC to `agent/cancel` request |
