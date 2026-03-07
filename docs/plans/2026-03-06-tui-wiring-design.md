# TUI Wiring: Design Document

## Problem

The TUI frontend has a complete component/state/integration layer, but the backend
protocol layer has critical gaps that prevent a working chat loop. Beyond that, many
frontend features exist as skeletons (components, hooks, commands) but are never
connected.

## Scope

### Phase 1: Core Chat Loop (immediate)

Get a working end-to-end conversation: user types message, agent streams response
tokens in real time, run completes cleanly, errors are reported.

| # | Item | Files |
|---|------|-------|
| 1 | Switch `agent/run` from `agent.run()` to `agent.stream()` | `sage/protocol/dispatcher.py` |
| 2 | Add `run/completed` notification on task finish/error/cancel | `sage/protocol/dispatcher.py` |
| 3 | Add `RUN_COMPLETED` protocol constant and payload type | `tui/src/types/protocol.ts` |
| 4 | Subscribe to `run/completed` in wiring | `tui/src/integration/wiring.ts` |
| 5 | Handle `run/completed` in EventRouter (flush stream, clear isStreaming, report errors) | `tui/src/integration/EventRouter.ts` |

### Phase 2: Full Integration Pass (deferred)

Wire every existing skeleton so no component, hook, or command is dead code.

| # | Item | Files | Notes |
|---|------|-------|-------|
| 6 | Integrate `JsonRpcPermissionHandler` in serve.py | `sage/cli/serve.py`, `sage/protocol/permissions.py` | Instantiate handler, attach to agent |
| 7 | Render `PermissionPrompt` in App and wire approve/deny to `permission/respond` | `tui/src/components/App.tsx`, `tui/src/components/PermissionPrompt.tsx` | |
| 8 | Fix permission field name mismatch (`requestId` vs `request_id`) | `sage/protocol/dispatcher.py:186`, `sage/protocol/permissions.py` | Accept all three variants |
| 9 | Render `SlashCommands` autocomplete in `InputArea` | `tui/src/components/InputArea.tsx`, `tui/src/components/SlashCommands.tsx` | Show dropdown when input starts with `/` |
| 10 | Implement 10 missing command handlers | `tui/src/integration/CommandExecutor.ts` | `models`, `permissions`, `theme`, `split`, `agent`, `agents`, `plan`, `notepad`, `bg`, `diff` |
| 11 | Wire `PlanContext` to EventRouter | `tui/src/integration/EventRouter.ts`, `tui/src/contexts/PlanContext.tsx` | Add plan notification type to bridge and router |
| 12 | Implement `BACKGROUND_TASK_UPDATE` reducer | `tui/src/state/AppContext.tsx` | Currently returns state unchanged |
| 13 | Implement `COMPACTION_STARTED` reducer | `tui/src/state/AppContext.tsx` | Currently returns state unchanged |
| 14 | Wire unused hooks into AppShell | `tui/src/components/App.tsx` | `useContextExhaustion`, `useExitHandler`, `useResizeHandler`, `usePermissionTimeout`, `useToolTimeout`, `useRetryWithBackoff` |
| 15 | Wire `useMemoryMonitor` | `tui/src/components/App.tsx` | Warn when heap is high |
| 16 | Wire `LifecycleManager` or remove it | `tui/src/integration/LifecycleManager.ts` | Currently dead code; decide keep or delete |
| 17 | Compute real `contextUsagePercent` | `sage/protocol/bridge.py:182` | Currently hardcoded to 0 |
| 18 | Wire session resume/fork/delete in `SessionPicker` | `tui/src/components/SessionPicker.tsx` | Callbacks are no-ops |
| 19 | Send error notification on failed runs | `sage/protocol/dispatcher.py` | Task exceptions reported to TUI |
| 20 | Remove dead code: `framing.py`, `SplitView.tsx`, `lifecycle.ts` | Various | Or integrate if still needed |
| 21 | Add `run/completed` handling for cancelled runs (Ctrl+C) | `tui/src/components/App.tsx` | Wire Ctrl+C/ESC to `agent/cancel` request |

## Architecture

```
User types message
  -> InputArea.onSubmit
    -> dispatch ADD_MESSAGE (local state)
    -> dispatch SET_STREAMING true
    -> client.request("agent/run", {message})

Backend:
  -> dispatcher._handle_agent_run
    -> asyncio.create_task(_run_streaming)
      -> agent.stream(message) yields chunks
      -> bridge translates events to notifications:
           stream/delta, tool/started, tool/completed,
           delegation/started, delegation/completed,
           turn/completed (with usage/update)
      -> on completion: send run/completed notification
      -> on error: send run/completed with error

TUI receives notifications:
  -> SageClient.handleLine parses JSON-RPC
  -> wireIntegration routes to EventRouter
  -> EventRouter dispatches to app state:
       stream/delta   -> ADD_MESSAGE / UPDATE_MESSAGE
       tool/started   -> TOOL_STARTED
       tool/completed -> TOOL_COMPLETED
       usage/update   -> UPDATE_USAGE
       run/completed  -> SET_STREAMING false (+ SET_ERROR if failed)
```
