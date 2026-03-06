import type { SageClient } from "../ipc/client.js";
import type { AppAction } from "../state/AppContext.js";
import type { AppState } from "../types/state.js";
import { METHODS } from "../types/protocol.js";
import { CommandExecutor } from "./CommandExecutor.js";
import { EventRouter } from "./EventRouter.js";

export interface WiringOptions {
  client: SageClient;
  dispatch: (action: AppAction) => void;
  getState: () => AppState;
}

export interface WiringResult {
  eventRouter: EventRouter;
  commandExecutor: CommandExecutor;
  cleanup: () => void;
}

const NOTIFICATION_METHODS = [
  METHODS.STREAM_DELTA,
  METHODS.TOOL_STARTED,
  METHODS.TOOL_COMPLETED,
  METHODS.DELEGATION_STARTED,
  METHODS.DELEGATION_COMPLETED,
  METHODS.BACKGROUND_COMPLETED,
  METHODS.PERMISSION_REQUEST,
  METHODS.USAGE_UPDATE,
  METHODS.COMPACTION_STARTED,
  METHODS.ERROR,
  METHODS.RUN_COMPLETED,
] as const;

export function wireIntegration(options: WiringOptions): WiringResult {
  const { client, dispatch, getState } = options;
  const eventRouter = new EventRouter(dispatch);

  const unsubscribers = NOTIFICATION_METHODS.map((method) =>
    client.onNotification(method, (params) => {
      eventRouter.handleNotification(method, params);
    }),
  );

  const commandExecutor = new CommandExecutor(client, dispatch, getState);

  return {
    eventRouter,
    commandExecutor,
    cleanup: () => {
      eventRouter.dispose();
      for (const unsubscribe of unsubscribers) {
        unsubscribe();
      }
    },
  };
}
