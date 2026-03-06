import type {
  JsonRpcNotification,
  JsonRpcRequest,
  JsonRpcResponse,
} from "../types/protocol.js";

export interface SageClientOptions {
  command?: string;
  args?: string[];
  agentConfig?: string;
  requestTimeout?: number;
  reconnectRetries?: number;
}

export interface PendingRequest {
  resolve: (result: unknown) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

export type NotificationHandler = (params: Record<string, unknown>) => void;

export type ClientStatus = "disconnected" | "connecting" | "connected" | "error";

export type JsonRpcInboundMessage = JsonRpcResponse | JsonRpcNotification;
export type JsonRpcOutboundMessage = JsonRpcRequest;
