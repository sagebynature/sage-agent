import { LifecycleManager } from "./LifecycleManager.js";

export interface LifecycleConfig {
  command: string;
  args: string[];
  onCrash?: (exitCode: number) => void;
  onConnected?: () => void;
}

export function createLifecycle(config: LifecycleConfig): LifecycleManager {
  return new LifecycleManager({
    command: config.command,
    args: config.args,
    onCrash: config.onCrash,
    onConnected: config.onConnected,
  });
}

export function createDefaultLifecycle(agentConfig: string): LifecycleManager {
  return createLifecycle({
    command: "sage",
    args: ["serve", "--agent-config", agentConfig],
  });
}
