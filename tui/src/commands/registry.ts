import { type Dispatch } from 'react';
import type { AppAction } from '../state/AppContext.js';

export interface CommandDefinition {
  name: string;
  description: string;
  aliases: string[];
  handler: (args: string, dispatch?: Dispatch<AppAction>) => void | Promise<void>;
}

export class CommandRegistry {
  private commands: Map<string, CommandDefinition> = new Map();

  constructor() {
    this.registerDefaults();
  }

  register(command: CommandDefinition) {
    this.commands.set(command.name, command);
  }

  getAll(): CommandDefinition[] {
    return Array.from(this.commands.values());
  }

  find(name: string): CommandDefinition | undefined {
    const lowerName = name.toLowerCase();
    for (const cmd of this.commands.values()) {
      if (cmd.name === lowerName || cmd.aliases.includes(lowerName)) {
        return cmd;
      }
    }
    return undefined;
  }

  search(query: string): CommandDefinition[] {
    if (!query) return this.getAll();

    const lowerQuery = query.toLowerCase();
    const matches = Array.from(this.commands.values()).filter(cmd =>
      cmd.name.toLowerCase().includes(lowerQuery) ||
      cmd.description.toLowerCase().includes(lowerQuery) ||
      cmd.aliases.some(alias => alias.toLowerCase().includes(lowerQuery))
    );

    return matches.sort((a, b) => {
      const aName = a.name.toLowerCase();
      const bName = b.name.toLowerCase();

      const aStarts = aName.startsWith(lowerQuery);
      const bStarts = bName.startsWith(lowerQuery);
      if (aStarts && !bStarts) return -1;
      if (!aStarts && bStarts) return 1;

      const aNameMatch = aName.includes(lowerQuery);
      const bNameMatch = bName.includes(lowerQuery);
      if (aNameMatch && !bNameMatch) return -1;
      if (!aNameMatch && bNameMatch) return 1;

      if (aName.length !== bName.length) return aName.length - bName.length;

      return 0;
    });
  }

  private registerDefaults() {
    const defaults: Omit<CommandDefinition, 'handler'>[] = [
      { name: 'help', description: 'Show help and available commands', aliases: ['h', '?'] },
      { name: 'clear', description: 'Clear screen and scrollback', aliases: ['cls'] },
      { name: 'reset', description: 'Reset session context and state', aliases: ['restart'] },
      { name: 'session', description: 'Manage current session', aliases: [] },
      { name: 'sessions', description: 'List and switch sessions', aliases: [] },
      { name: 'compact', description: 'Toggle compact mode', aliases: [] },
      { name: 'model', description: 'Show or change current model', aliases: [] },
      { name: 'models', description: 'List available models', aliases: [] },
      { name: 'usage', description: 'Show token usage statistics', aliases: [] },
      { name: 'tools', description: 'List available tools', aliases: [] },
      { name: 'permissions', description: 'Manage tool permissions', aliases: ['perms'] },
      { name: 'theme', description: 'Change UI theme', aliases: [] },
      { name: 'split', description: 'Split view controls', aliases: [] },
      { name: 'agent', description: 'Show current agent status', aliases: [] },
      { name: 'agents', description: 'List available agents', aliases: [] },
      { name: 'plan', description: 'Show or edit current plan', aliases: [] },
      { name: 'notepad', description: 'Open scratchpad', aliases: ['note'] },
      { name: 'bg', description: 'Manage background tasks', aliases: ['background'] },
      { name: 'diff', description: 'Show diff of last changes', aliases: [] },
      { name: 'export', description: 'Export session transcript', aliases: [] },
      { name: 'quit', description: 'Exit the application', aliases: ['exit', 'q'] },
    ];

    defaults.forEach(def => {
      this.register({
        ...def,
        handler: async (_args: string) => {},
      });
    });
  }
}

export const commandRegistry = new CommandRegistry();
