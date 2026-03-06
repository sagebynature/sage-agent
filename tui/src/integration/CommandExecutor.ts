import type { SageClient } from "../ipc/client.js";
import type { AppAction } from "../state/AppContext.js";
import type { AppState, ChatMessage, SessionState } from "../types/state.js";
import { CommandRegistry } from "../commands/registry.js";

interface LifecycleManagerLike {
  shutdown(): Promise<void>;
}

const NOOP_LIFECYCLE_MANAGER: LifecycleManagerLike = {
  async shutdown() {
    return;
  },
};

export class CommandExecutor {
  private readonly client: SageClient;
  private readonly dispatch: (action: AppAction) => void;
  private readonly getState: () => AppState;
  private readonly registry: CommandRegistry;
  private readonly lifecycleManager: LifecycleManagerLike;

  constructor(
    client: SageClient,
    dispatch: (action: AppAction) => void,
    getState: () => AppState,
    lifecycleManager: LifecycleManagerLike = NOOP_LIFECYCLE_MANAGER,
  ) {
    this.client = client;
    this.dispatch = dispatch;
    this.getState = getState;
    this.lifecycleManager = lifecycleManager;
    this.registry = new CommandRegistry();
  }

  async execute(commandName: string, args: string): Promise<string | void> {
    const normalized = commandName.trim().replace(/^\//, "").toLowerCase();
    const command = this.registry.find(normalized);

    if (!command) {
      console.warn(`Unknown command: ${commandName}`);
      return;
    }

    switch (normalized) {
      case "clear":
        return this.handleClear();
      case "compact": {
        const result = await this.client.request("agent/compact", {});
        return this.stringifyResult(result);
      }
      case "model": {
        const result = await this.client.request("config/get", { key: "model" });
        return this.stringifyResult(result);
      }
      case "tools": {
        const result = await this.client.request("tools/list", {});
        return this.stringifyResult(result);
      }
      case "usage":
        return this.formatUsage();
      case "session":
        this.dispatch({ type: "SET_VIEW", view: "dashboard" });
        return;
      case "sessions": {
        const result = await this.client.request("session/list", {});
        return this.stringifyResult(result);
      }
      case "export":
        return this.formatExport(this.getState().messages);
      case "quit":
        await this.lifecycleManager.shutdown();
        process.exit(0);
      case "help":
        return this.formatHelp();
      case "reset":
        await this.client.request("session/clear", {});
        this.dispatch({ type: "SET_SESSION", session: null });
        this.dispatch({ type: "SET_STREAMING", isStreaming: false });
        this.dispatch({ type: "CLEAR_ERROR" });
        this.dispatch({ type: "SET_VIEW", view: "focused" });
        this.dispatch({
          type: "UPDATE_USAGE",
          usage: {
            promptTokens: 0,
            completionTokens: 0,
            totalCost: 0,
            model: "",
            contextUsagePercent: 0,
          },
        });
        return;
      default:
        console.warn(`Unimplemented registered command: ${normalized}`);
        void args;
        return;
    }
  }

  private async handleClear(): Promise<void> {
    const state = this.getState();
    const sessionId = state.session?.id;

    if (sessionId) {
      await this.client.request("session/clear", { sessionId });
    } else {
      await this.client.request("session/clear", {});
    }

    if (state.session) {
      const clearedSession: SessionState = {
        ...state.session,
        messageCount: 0,
      };
      this.dispatch({ type: "SET_SESSION", session: clearedSession });
    } else {
      this.dispatch({ type: "SET_SESSION", session: null });
    }
  }

  private formatUsage(): string {
    const usage = this.getState().usage;
    return [
      `promptTokens: ${usage.promptTokens}`,
      `completionTokens: ${usage.completionTokens}`,
      `totalCost: ${usage.totalCost}`,
      `model: ${usage.model}`,
      `contextUsagePercent: ${usage.contextUsagePercent}`,
    ].join("\n");
  }

  private formatHelp(): string {
    const commands = this.registry
      .getAll()
      .map((command) => `/${command.name} - ${command.description}`)
      .sort((a, b) => a.localeCompare(b));
    return commands.join("\n");
  }

  private formatExport(messages: ChatMessage[]): string {
    const lines: string[] = ["# Session Export", ""];

    for (const message of messages) {
      lines.push(`## ${this.toTitle(message.role)}`);
      lines.push(message.content ?? "");
      lines.push("");
    }

    return lines.join("\n").trimEnd();
  }

  private stringifyResult(result: unknown): string {
    return JSON.stringify(result, null, 2);
  }

  private toTitle(value: string): string {
    if (value.length === 0) {
      return value;
    }

    const first = value[0];
    if (!first) {
      return value;
    }
    return `${first.toUpperCase()}${value.slice(1)}`;
  }
}
