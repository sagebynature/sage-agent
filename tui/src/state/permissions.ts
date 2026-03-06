
function generateId(): string {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
}

export interface PermissionGrant {
  id: string;
  type: "session" | "similar";
  tool: string;
  argPattern?: Record<string, unknown>;
  createdAt: number;
}

export class PermissionStore {
  private grants: PermissionGrant[] = [];

  constructor() {}

  addSessionGrant(toolName: string): void {
    this.revokeByToolAndType(toolName, "session");

    this.grants.push({
      id: generateId(),
      type: "session",
      tool: toolName,
      createdAt: Date.now(),
    });
  }

  addSimilarGrant(toolName: string, argPattern: Record<string, unknown>): void {
    this.grants.push({
      id: generateId(),
      type: "similar",
      tool: toolName,
      argPattern,
      createdAt: Date.now(),
    });
  }

  isAutoApproved(toolName: string, args: Record<string, unknown>): boolean {
    return this.grants.some(grant => {
      if (grant.tool !== toolName) return false;

      if (grant.type === "session") {
        return true;
      }

      if (grant.type === "similar" && grant.argPattern) {
        return this.matchesPattern(args, grant.argPattern);
      }

      return false;
    });
  }

  getGrants(): PermissionGrant[] {
    return [...this.grants];
  }

  revokeGrant(id: string): void {
    this.grants = this.grants.filter(g => g.id !== id);
  }

  clear(): void {
    this.grants = [];
  }

  private revokeByToolAndType(tool: string, type: "session" | "similar"): void {
    this.grants = this.grants.filter(g => !(g.tool === tool && g.type === type));
  }

  private matchesPattern(args: Record<string, unknown>, pattern: Record<string, unknown>): boolean {
    for (const [key, value] of Object.entries(pattern)) {
      if (args[key] !== value) {
        return false;
      }
    }
    return true;
  }
}

export const permissionStore = new PermissionStore();
