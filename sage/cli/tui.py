"""Interactive Textual TUI for Sage.

Provides the ``SageTUIApp`` class launched by ``sage tui --config=<path>``.
The app offers a split-screen layout:

- **Chat panel** (left, 60 %): conversation history and message input.
- **Activity panel** (right, 40 %): live tool-call feed with timestamps.
- **Status bar** (bottom): agent name, model, current state, keyboard hints.

Tool-call and LLM-turn visibility is achieved by subscribing to the typed
agent event system via :meth:`~sage.agent.Agent.on`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sage.main_config import MainConfig

from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Input, Label, RichLog, Static
from rich.text import Text

from sage.agent import Agent
from sage.orchestrator.parallel import Orchestrator

logger = logging.getLogger(__name__)


def format_tokens(count: int) -> str:
    """Format a token count as a human-readable string (e.g. 1234 → '1.2k')."""
    if count < 1000:
        return str(count)
    if count < 1_000_000:
        return f"{count / 1000:.1f}k"
    return f"{count / 1_000_000:.1f}M"


# ── Custom Textual messages ───────────────────────────────────────────────────


class ToolCallStarted(Message):
    """Emitted just before a tool is dispatched."""

    def __init__(self, tool_name: str, arguments: dict[str, Any]) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.arguments = arguments


class ToolCallCompleted(Message):
    """Emitted after a tool dispatch returns."""

    def __init__(self, tool_name: str, result: str) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.result = result


class AgentResponseReady(Message):
    """Emitted when ``agent.run()`` completes successfully."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class AgentError(Message):
    """Emitted when ``agent.run()`` raises an exception."""

    def __init__(self, error: str) -> None:
        super().__init__()
        self.error = error


class StreamChunkReceived(Message):
    """Emitted for each text chunk during streaming."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class StreamFinished(Message):
    """Emitted when the streaming response is complete."""

    def __init__(self, full_text: str) -> None:
        super().__init__()
        self.full_text = full_text


class TurnStarted(Message):
    """Emitted when the agent begins a new LLM turn."""

    def __init__(self, turn: int, model: str) -> None:
        super().__init__()
        self.turn = turn
        self.model = model


class DelegationEventStarted(Message):
    """Emitted when the agent delegates to a subagent."""

    def __init__(self, target: str, task: str) -> None:
        super().__init__()
        self.target = target
        self.task = task


# ── Hook-based instrumentation ────────────────────────────────────────────────


def instrument_agent(agent: Agent, app: "SageTUIApp") -> None:
    """Subscribe to typed agent events to emit live Textual messages.

    Replaces the former monkey-patching approach with hook subscriptions via
    :meth:`~sage.agent.Agent.on`.  Every tool dispatch fires a
    :class:`ToolCallStarted` / :class:`ToolCallCompleted` pair, each LLM turn
    fires a :class:`TurnStarted` message, and each delegation fires a
    :class:`DelegationEventStarted` message.  Streaming text is delivered via
    :class:`StreamChunkReceived` through the :data:`~sage.hooks.base.HookEvent.ON_LLM_STREAM_DELTA`
    hook so the :meth:`~SageTUIApp._agent_stream` loop can stay clean.
    """
    from sage.events import (
        DelegationStarted,
        LLMStreamDelta,
        LLMTurnStarted,
        ToolCompleted,
        ToolStarted,
    )

    async def on_tool_started(e: ToolStarted) -> None:
        app.post_message(ToolCallStarted(e.name, e.arguments))

    async def on_tool_completed(e: ToolCompleted) -> None:
        app.post_message(ToolCallCompleted(e.name, e.result))

    async def on_stream_delta(e: LLMStreamDelta) -> None:
        app.post_message(StreamChunkReceived(e.delta))

    async def on_turn_started(e: LLMTurnStarted) -> None:
        app.post_message(TurnStarted(e.turn, e.model))

    async def on_delegation_started(e: DelegationStarted) -> None:
        app.post_message(DelegationEventStarted(e.target, e.task))

    agent.on(ToolStarted, on_tool_started)
    agent.on(ToolCompleted, on_tool_completed)
    agent.on(LLMStreamDelta, on_stream_delta)
    agent.on(LLMTurnStarted, on_turn_started)
    agent.on(DelegationStarted, on_delegation_started)


# ── Helper ────────────────────────────────────────────────────────────────────


def _fmt_args(arguments: dict[str, Any]) -> str:
    """Return a brief, single-line representation of tool arguments."""
    if not arguments:
        return ""
    parts: list[str] = []
    for k, v in list(arguments.items())[:3]:
        val_str = str(v)
        if len(val_str) > 20:
            val_str = val_str[:20] + "…"
        parts.append(f"{k}={val_str!r}")
    if len(arguments) > 3:
        parts.append("…")
    return ", ".join(parts)


# ── HistoryInput ──────────────────────────────────────────────────────────────


class HistoryInput(Input):
    """Input widget with up/down arrow message history, like a shell prompt."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._history: list[str] = []
        self._history_idx: int = 0
        self._draft: str = ""

    def append_history(self, value: str) -> None:
        """Add a submitted message to history and reset cursor to end."""
        if value:
            self._history.append(value)
        self._history_idx = len(self._history)
        self._draft = ""

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "up":
            if self._history_idx > 0:
                if self._history_idx == len(self._history):
                    self._draft = self.value
                self._history_idx -= 1
                self.value = self._history[self._history_idx]
                self.cursor_position = len(self.value)
                event.prevent_default()
                event.stop()
        elif event.key == "down":
            if self._history_idx < len(self._history):
                self._history_idx += 1
                if self._history_idx == len(self._history):
                    self.value = self._draft
                else:
                    self.value = self._history[self._history_idx]
                self.cursor_position = len(self.value)
                event.prevent_default()
                event.stop()


# ── Chat entry widgets ────────────────────────────────────────────────────────


class UserEntry(Widget):
    """A single user message in the chat scroll view."""

    DEFAULT_CSS = """
    UserEntry {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }
    """

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        yield Static(f"[bold cyan]You[/bold cyan]  [dim]╷[/dim]  {self._text}")


class ThinkingEntry(Widget):
    """Animated thinking indicator — removed when the response starts."""

    DEFAULT_CSS = """
    ThinkingEntry {
        height: 1;
        padding: 0 1;
        margin-bottom: 1;
    }
    """

    _FRAMES = ["◌", "◎", "●", "◎"]

    def compose(self) -> ComposeResult:
        yield Static("[dim]◌ Thinking…[/dim]", id="thinking-label")

    def on_mount(self) -> None:
        self._frame = 0
        self.set_interval(0.25, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(self._FRAMES)
        self.query_one("#thinking-label", Static).update(
            f"[dim]{self._FRAMES[self._frame]} Thinking…[/dim]"
        )


# ── Widgets ───────────────────────────────────────────────────────────────────


class ChatPanel(Widget):
    """Left panel: conversation history and message input."""

    DEFAULT_CSS = """
    ChatPanel {
        width: 60%;
        height: 100%;
        border-right: solid $primary;
    }
    ChatPanel #chat-log {
        height: 1fr;
        padding: 0 1;
    }
    ChatPanel Label {
        padding: 0 1;
        color: $text-muted;
        text-style: bold;
    }
    ChatPanel #chat-input {
        dock: bottom;
        margin: 0 1 1 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("CHAT")
        yield RichLog(id="chat-log", wrap=True, markup=True, highlight=False)
        yield Input(placeholder="> Type a message and press Enter…", id="chat-input")


class ActivityPanel(Widget):
    """Right panel: timestamped, colour-coded live tool-call feed."""

    DEFAULT_CSS = """
    ActivityPanel {
        width: 40%;
        height: 100%;
    }
    ActivityPanel Label {
        padding: 0 1;
        color: $text-muted;
        text-style: bold;
    }
    ActivityPanel #activity-log {
        height: 1fr;
        padding: 0 1;
    }
    ActivityPanel #stats {
        dock: bottom;
        padding: 0 1 1 1;
    }
    """

    _tool_call_count: int = 0

    def compose(self) -> ComposeResult:
        yield Label("LIVE ACTIVITY")
        yield RichLog(id="activity-log", wrap=True, markup=True, highlight=False)
        yield Static("", id="stats")

    def add_turn_started(self, turn: int, model: str) -> None:
        log = self.query_one("#activity-log", RichLog)
        ts = datetime.now().strftime("%H:%M:%S")
        log.write(f"[{ts}] [bold cyan]◆ turn {turn + 1}[/bold cyan]  [dim]{model}[/dim]")

    def add_delegation_started(self, target: str, task: str) -> None:
        log = self.query_one("#activity-log", RichLog)
        ts = datetime.now().strftime("%H:%M:%S")
        task_preview = task[:50] + "…" if len(task) > 50 else task
        log.write(
            f"[{ts}] [bold magenta]↳ delegate →[/bold magenta] {target}  [dim]{task_preview!r}[/dim]"
        )

    def add_tool_started(self, name: str, arguments: dict[str, Any]) -> None:
        log = self.query_one("#activity-log", RichLog)
        args_str = _fmt_args(arguments)
        ts = datetime.now().strftime("%H:%M:%S")
        log.write(f"[{ts}] [yellow]▶ tool:[/yellow] [bold]{name}[/bold]({args_str})")

    def add_tool_completed(self, name: str, result: str) -> None:
        log = self.query_one("#activity-log", RichLog)
        self._tool_call_count += 1
        preview = result[:60] + "…" if len(result) > 60 else result
        log.write(f"         [dim]result:[/dim] {preview}")
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        self.query_one("#stats", Static).update(f"[dim]Tool calls: {self._tool_call_count}[/dim]")

    def clear_feed(self) -> None:
        self.query_one("#activity-log", RichLog).clear()
        self._tool_call_count = 0
        self._refresh_stats()


class StatusBar(Static):
    """Bottom bar: agent state, model info, and keyboard hints."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    """

    _token_usage: int = 0
    _context_window_limit: int | None = None
    _session_cost: float = 0.0
    _state: str = "Ready"
    _agent_name: str = ""
    _model: str = ""
    _has_subagents: bool = False
    _streaming_mode: bool = False

    def update_token_usage(self, token_usage: int, context_window_limit: int | None) -> None:
        self._token_usage = token_usage
        self._context_window_limit = context_window_limit
        self._refresh()

    def update_session_cost(self, cost: float) -> None:
        self._session_cost = cost
        self._refresh()

    def set_state(
        self,
        state: str,
        agent_name: str,
        model: str,
        has_subagents: bool,
        streaming_mode: bool = False,
    ) -> None:
        self._state = state
        self._agent_name = agent_name
        self._model = model
        self._has_subagents = has_subagents
        self._streaming_mode = streaming_mode
        self._refresh()

    def _refresh(self) -> None:
        colour = {
            "Ready": "green",
            "Thinking…": "yellow",
            "Streaming…": "cyan",
            "Error": "red",
        }.get(self._state, "white")
        hint = "  [dim]ctrl+o: orchestrate[/dim]" if self._has_subagents else ""
        stream_badge = " [cyan]◉ stream[/cyan]" if self._streaming_mode else " [dim]○ batch[/dim]"

        # Token usage display
        token_str = f"{format_tokens(self._token_usage)} tokens"
        token_colour = "dim"

        if self._context_window_limit:
            usage_str = format_tokens(self._token_usage)
            limit_str = format_tokens(self._context_window_limit)
            token_str = f"{usage_str} / {limit_str} tokens"

            ratio = self._token_usage / self._context_window_limit
            if ratio >= 0.8:
                token_colour = "red"
            elif ratio >= 0.6:
                token_colour = "yellow"
            else:
                token_colour = "green"

        cost_str = f"  [green]${self._session_cost:.4f}[/green]" if self._session_cost > 0 else ""

        self.update(
            f"[{colour}]● {self._state}[/{colour}]  [bold]{self._agent_name}[/bold]"
            f" ([dim]{self._model}[/dim]){stream_badge}    "
            f"[{token_colour}]{token_str}[/{token_colour}]{cost_str}    "
            f"[dim]ctrl+s: stream  ctrl+l: clear  ctrl+q: quit[/dim]{hint}"
        )


# ── Orchestration modal ───────────────────────────────────────────────────────


class OrchestrationScreen(ModalScreen[None]):
    """Modal for launching parallel subagent orchestration."""

    DEFAULT_CSS = """
    OrchestrationScreen {
        align: center middle;
    }
    #modal-body {
        width: 72;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: double $primary;
        padding: 1 2;
    }
    #modal-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #agent-list {
        height: auto;
        margin-bottom: 1;
    }
    #orch-input {
        margin-bottom: 1;
    }
    #orch-buttons {
        height: 3;
        align: right middle;
    }
    #orch-results {
        height: auto;
        max-height: 20;
        overflow-y: auto;
    }
    """

    BINDINGS = [Binding("escape", "close_modal", "Close")]

    def __init__(self, agent: Agent) -> None:
        super().__init__()
        self._agent = agent
        self._running = False

    def compose(self) -> ComposeResult:
        agents = list(self._agent.subagents.values())
        with Vertical(id="modal-body"):
            yield Static("[bold]Orchestrate Subagents[/bold]", id="modal-title")
            with Vertical(id="agent-list"):
                for a in agents:
                    yield Static(f"  [green]•[/green] [bold]{a.name}[/bold] ([dim]{a.model}[/dim])")
            yield Input(
                placeholder="Enter query for all subagents…",
                id="orch-input",
            )
            with Horizontal(id="orch-buttons"):
                yield Button("Run Parallel", id="run-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")
            yield Vertical(id="orch-results")

    def action_close_modal(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#cancel-btn")
    def on_cancel_pressed(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#run-btn")
    def on_run_pressed(self) -> None:
        if self._running:
            return
        input_widget = self.query_one("#orch-input", Input)
        query = input_widget.value.strip()
        if not query:
            return
        self._running = True
        input_widget.disabled = True
        self.query_one("#run-btn", Button).disabled = True

        agents = list(self._agent.subagents.values())
        results_container = self.query_one("#orch-results", Vertical)
        for a in agents:
            results_container.mount(
                Static(
                    f"[yellow]⟳[/yellow] {a.name}: [dim]running…[/dim]",
                    id=f"orch-result-{a.name}",
                )
            )
        self.run_worker(
            self._run_parallel(agents, query),
            exclusive=True,
            exit_on_error=False,
        )

    async def _run_parallel(self, agents: list[Agent], query: str) -> None:
        results = await Orchestrator.run_parallel(agents, query)
        for result in results:
            safe_id = f"orch-result-{result.agent_name}"
            widget = self.query_one(f"#{safe_id}", Static)
            if result.success:
                preview = result.output[:80] + "…" if len(result.output) > 80 else result.output
                widget.update(f"[green]✓[/green] [bold]{result.agent_name}:[/bold] {preview}")
            else:
                widget.update(
                    f"[red]✗[/red] [bold]{result.agent_name}:[/bold] [red]{result.error}[/red]"
                )


# ── Main application ──────────────────────────────────────────────────────────


class SageTUIApp(App[None]):
    """Interactive split-screen TUI for a Sage agent config."""

    CSS = """
    #main-layout {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+o", "orchestrate", "Orchestrate"),
        Binding("ctrl+s", "toggle_stream", "Toggle stream"),
    ]

    TITLE = "Sage TUI"

    def __init__(self, config_path: Path, central: MainConfig | None = None) -> None:
        super().__init__()
        self.config_path = config_path
        self._central = central
        self._agent: Agent | None = None
        self._streaming_mode: bool = True
        self._stream_buffer: str = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            yield ChatPanel(id="chat-panel")
            yield ActivityPanel(id="activity-panel")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        agent = Agent.from_config(self.config_path, central=self._central)
        self._agent = agent
        instrument_agent(agent, self)
        has_subs = bool(agent.subagents)
        self.query_one(StatusBar).set_state(
            "Ready", agent.name, agent.model, has_subs, streaming_mode=self._streaming_mode
        )
        self.sub_title = f"{agent.name} ({agent.model})"
        self.query_one("#chat-input", Input).focus()

    async def on_unmount(self) -> None:
        if self._agent is not None:
            await self._agent.close()

    # ── Input handling ────────────────────────────────────────────────────────

    @on(Input.Submitted, "#chat-input")
    def handle_chat_input(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query or self._agent is None:
            return
        input_widget = self.query_one("#chat-input", Input)
        input_widget.clear()
        input_widget.disabled = True

        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(f"[bold cyan]You:[/bold cyan] {query}")

        agent = self._agent

        if self._streaming_mode:
            chat_log.write("[bold green]Agent:[/bold green] ", shrink=False)
            self.query_one(StatusBar).set_state(
                "Streaming…",
                agent.name,
                agent.model,
                bool(agent.subagents),
                streaming_mode=self._streaming_mode,
            )
            self._stream_buffer = ""
            self.run_worker(self._agent_stream(query), exclusive=True, exit_on_error=False)
        else:
            chat_log.write("[dim yellow]Agent: ● Thinking…[/dim yellow]")
            self.query_one(StatusBar).set_state(
                "Thinking…",
                agent.name,
                agent.model,
                bool(agent.subagents),
                streaming_mode=self._streaming_mode,
            )
            self.run_worker(self._agent_run(query), exclusive=True, exit_on_error=False)

    async def _agent_run(self, query: str) -> None:
        if self._agent is None:
            return
        try:
            result = await self._agent.run(query)
            self.post_message(AgentResponseReady(result))
        except Exception as exc:
            logger.exception("Agent run failed")
            self.post_message(AgentError(str(exc)))

    async def _agent_stream(self, query: str) -> None:
        if self._agent is None:
            return
        try:
            full_text = ""
            async for chunk in self._agent.stream(query):
                full_text += chunk
                # StreamChunkReceived is posted by the ON_LLM_STREAM_DELTA hook
                # registered in instrument_agent — no direct posting here.
            self.post_message(StreamFinished(full_text))
        except Exception as exc:
            logger.exception("Agent stream failed")
            self.post_message(AgentError(str(exc)))

    # ── Message handlers ──────────────────────────────────────────────────────

    def on_tool_call_started(self, event: ToolCallStarted) -> None:
        self.query_one(ActivityPanel).add_tool_started(event.tool_name, event.arguments)

    def on_tool_call_completed(self, event: ToolCallCompleted) -> None:
        self.query_one(ActivityPanel).add_tool_completed(event.tool_name, event.result)

    def on_turn_started(self, event: TurnStarted) -> None:
        self.query_one(ActivityPanel).add_turn_started(event.turn, event.model)

    def on_delegation_event_started(self, event: DelegationEventStarted) -> None:
        self.query_one(ActivityPanel).add_delegation_started(event.target, event.task)

    def on_stream_chunk_received(self, event: StreamChunkReceived) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        self._stream_buffer += event.text
        # Flush completed lines; keep partial line in buffer
        while "\n" in self._stream_buffer:
            line, self._stream_buffer = self._stream_buffer.split("\n", 1)
            chat_log.write(line, scroll_end=True)

    def on_stream_finished(self, event: StreamFinished) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        # Flush any remaining partial line
        if self._stream_buffer:
            chat_log.write(self._stream_buffer, scroll_end=True)
        chat_log.write("")  # blank separator
        self._stream_buffer = ""
        self._re_enable_input()
        if self._agent:
            self.query_one(StatusBar).set_state(
                "Ready",
                self._agent.name,
                self._agent.model,
                bool(self._agent.subagents),
                streaming_mode=self._streaming_mode,
            )
            stats = self._agent.get_usage_stats()
            status_bar = self.query_one(StatusBar)
            status_bar.update_token_usage(
                stats["token_usage"],  # type: ignore[arg-type]
                stats["context_window_limit"],  # type: ignore[arg-type]
            )
            status_bar.update_session_cost(stats.get("cumulative_cost", 0.0))  # type: ignore[arg-type]
            if stats.get("compacted_this_turn"):
                chat_log.write(
                    Text("⚡ Context compacted to reduce token usage", style="dim italic"),
                    scroll_end=True,
                )

    def on_agent_response_ready(self, event: AgentResponseReady) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(f"[bold green]Agent:[/bold green] {event.text}")
        chat_log.write("")
        self._re_enable_input()
        if self._agent:
            self.query_one(StatusBar).set_state(
                "Ready",
                self._agent.name,
                self._agent.model,
                bool(self._agent.subagents),
                streaming_mode=self._streaming_mode,
            )
            stats = self._agent.get_usage_stats()
            status_bar = self.query_one(StatusBar)
            status_bar.update_token_usage(
                stats["token_usage"],  # type: ignore[arg-type]
                stats["context_window_limit"],  # type: ignore[arg-type]
            )
            status_bar.update_session_cost(stats.get("cumulative_cost", 0.0))  # type: ignore[arg-type]
            if stats.get("compacted_this_turn"):
                chat_log.write(
                    Text("⚡ Context compacted to reduce token usage", style="dim italic"),
                    scroll_end=True,
                )

    def on_agent_error(self, event: AgentError) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(f"[bold red]Error:[/bold red] {event.error}")
        chat_log.write("")
        self._stream_buffer = ""
        self._re_enable_input()
        if self._agent:
            self.query_one(StatusBar).set_state(
                "Error",
                self._agent.name,
                self._agent.model,
                bool(self._agent.subagents),
                streaming_mode=self._streaming_mode,
            )

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_clear_chat(self) -> None:
        self.query_one("#chat-log", RichLog).clear()
        self.query_one(ActivityPanel).clear_feed()
        self.query_one(StatusBar).update_token_usage(0, None)

    def action_orchestrate(self) -> None:
        if self._agent and self._agent.subagents:
            self.push_screen(OrchestrationScreen(self._agent))

    def action_toggle_stream(self) -> None:
        self._streaming_mode = not self._streaming_mode
        mode_label = "streaming" if self._streaming_mode else "batch"
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(f"[dim]⚙ Switched to {mode_label} mode[/dim]")
        if self._agent:
            self.query_one(StatusBar).set_state(
                "Ready",
                self._agent.name,
                self._agent.model,
                bool(self._agent.subagents),
                streaming_mode=self._streaming_mode,
            )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _re_enable_input(self) -> None:
        input_widget = self.query_one("#chat-input", Input)
        input_widget.disabled = False
        input_widget.focus()
