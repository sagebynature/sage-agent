import { describe, it, expect, beforeEach } from 'vitest';
import { CommandRegistry, type CommandDefinition } from '../registry.js';

describe('CommandRegistry', () => {
  let registry: CommandRegistry;

  beforeEach(() => {
    registry = new CommandRegistry();
  });

  it('should initialize with default commands', () => {
    const commands = registry.getAll();
    expect(commands.length).toBeGreaterThan(0);
    expect(commands.some(c => c.name === 'help')).toBe(true);
    expect(commands.some(c => c.name === 'quit')).toBe(true);
  });

  it('should find a command by name', () => {
    const cmd = registry.find('help');
    expect(cmd).toBeDefined();
    expect(cmd?.name).toBe('help');
  });

  it('should find a command by alias', () => {
    const cmd = registry.find('?');
    expect(cmd).toBeDefined();
    expect(cmd?.name).toBe('help');
  });

  it('should return undefined for unknown commands', () => {
    const cmd = registry.find('nonexistent');
    expect(cmd).toBeUndefined();
  });

  it('should register a new command', () => {
    const newCommand: CommandDefinition = {
      name: 'test',
      description: 'Test command',
      aliases: ['t'],
      handler: () => {}
    };
    registry.register(newCommand);
    expect(registry.find('test')).toEqual(newCommand);
    expect(registry.find('t')).toEqual(newCommand);
  });

  it('should search commands with fuzzy matching', () => {
    // Should match 'model' and 'models'
    const results = registry.search('mod');
    expect(results.some(c => c.name === 'model')).toBe(true);
    expect(results.some(c => c.name === 'models')).toBe(true);
  });

  it('should search commands by description', () => {
    // 'scratchpad' is in description of 'notepad'
    const results = registry.search('scratchpad');
    expect(results.some(c => c.name === 'notepad')).toBe(true);
  });

  it('should return all commands when search query is empty', () => {
    const all = registry.getAll();
    const results = registry.search('');
    expect(results.length).toBe(all.length);
  });
});
