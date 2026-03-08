import { METHODS } from "../types/protocol.js";
import type { BlockAction } from "../state/blockReducer.js";
import { EventNormalizer } from "./EventNormalizer.js";
import { EventProjector } from "./EventProjector.js";

type Dispatch = (action: BlockAction) => void;

const AGENT_EVENT_METHODS: ReadonlySet<string> = new Set([
  METHODS.STREAM_DELTA,
  METHODS.TOOL_STARTED,
  METHODS.TOOL_COMPLETED,
  METHODS.RUN_COMPLETED,
  METHODS.DELEGATION_STARTED,
  METHODS.DELEGATION_COMPLETED,
  METHODS.BACKGROUND_COMPLETED,
  METHODS.TURN_STARTED,
  METHODS.TURN_COMPLETED,
  METHODS.LLM_TURN_STARTED,
  METHODS.LLM_TURN_COMPLETED,
]);

export class BlockEventRouter {
  private readonly dispatch: Dispatch;
  private readonly normalizer = new EventNormalizer();
  private readonly projector = new EventProjector();
  private hasCanonicalEvents = false;

  constructor(dispatch: Dispatch) {
    this.dispatch = dispatch;
  }

  handleNotification(method: string, params: Record<string, unknown>): void {
    if (method === METHODS.USAGE_UPDATE) {
      this.dispatch({
        type: "UPDATE_USAGE",
        usage: {
          promptTokens: typeof params.promptTokens === "number" ? params.promptTokens : 0,
          completionTokens: typeof params.completionTokens === "number" ? params.completionTokens : 0,
          totalCost: typeof params.totalCost === "number" ? params.totalCost : 0,
          model: typeof params.model === "string" ? params.model : "",
          contextUsagePercent: typeof params.contextUsagePercent === "number" ? params.contextUsagePercent : 0,
        },
      });
      return;
    }

    if (method === METHODS.EVENT_EMITTED) {
      this.hasCanonicalEvents = true;
    } else if (this.hasCanonicalEvents && AGENT_EVENT_METHODS.has(method)) {
      // Ignore legacy agent events if we are receiving canonical telemetry envelopes.
      // This prevents duplicate deltas and tool blocks in the UI.
      return;
    }

    const event = this.normalizer.normalizeNotification(method, params);
    if (!event) {
      return;
    }

    this.dispatch({ type: "EVENT_RECEIVED", event });

    for (const action of this.projector.project(event)) {
      this.dispatch(action);
    }
  }
}
