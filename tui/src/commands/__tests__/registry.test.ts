import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CommandRegistry, type CommandDefinition } from '../registry.js';
import { INITIAL_BLOCK_STATE, type BlockAction, type BlockState } from '../../state/blockReducer.js';
import { METHODS } from '../../types/protocol.js';

function createState(overrides: Partial<BlockState> = {}): BlockState {
  return {
    ...INITIAL_BLOCK_STATE,
    completedRunIds: new Set(INITIAL_BLOCK_STATE.completedRunIds),
    usage: { ...INITIAL_BLOCK_STATE.usage },
    ui: {
      ...INITIAL_BLOCK_STATE.ui,
      filters: { ...INITIAL_BLOCK_STATE.ui.filters },
    },
    ...overrides,
  };
}

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

  it('should generate help text from the registered command metadata', async () => {
    const help = registry.find('help');
    expect(help).toBeDefined();

    const output = await help?.handler('');
    expect(output).toContain('/clear — Clear conversation');
    expect(output).toContain('/verbosity [compact|normal|debug] — Set event verbosity level');
    expect(output).toContain('/theme — Change UI theme (planned)');
  });

  it('should keep help output in sync with all registered commands', async () => {
    const output = await registry.find('help')?.handler('') ?? '';
    for (const command of registry.getAll()) {
      expect(output).toContain(`/${command.name}`);
      expect(output).toContain(command.description);
    }
  });

  it('clear handler clears the current session and dispatches CLEAR_BLOCKS', async () => {
    const request = vi.fn().mockResolvedValue({ cleared: true });
    const dispatch = vi.fn<(action: BlockAction) => void>();
    const registryWithContext = new CommandRegistry({
      client: { request },
      dispatch,
      getState: () => createState({
        session: {
          id: 'session-1',
          agentName: 'sage',
          createdAt: '2026-03-09T00:00:00Z',
          messageCount: 2,
        },
      }),
      shutdown: vi.fn(),
    });

    const result = await registryWithContext.find('clear')?.handler('');

    expect(request).toHaveBeenCalledWith(METHODS.SESSION_CLEAR, { sessionId: 'session-1' });
    expect(dispatch).toHaveBeenCalledWith({ type: 'CLEAR_BLOCKS' });
    expect(result).toBe('Conversation cleared.');
  });

  it('reset handler clears stateful session data and zeroes usage', async () => {
    const request = vi.fn().mockResolvedValue({ cleared: true });
    const dispatch = vi.fn<(action: BlockAction) => void>();
    const registryWithContext = new CommandRegistry({
      client: { request },
      dispatch,
      getState: () => createState({
        session: {
          id: 'session-1',
          agentName: 'sage',
          createdAt: '2026-03-09T00:00:00Z',
          messageCount: 2,
        },
      }),
      shutdown: vi.fn(),
    });

    const result = await registryWithContext.find('reset')?.handler('');

    expect(request).toHaveBeenCalledWith(METHODS.SESSION_CLEAR, { sessionId: 'session-1' });
    expect(dispatch).toHaveBeenNthCalledWith(1, { type: 'CLEAR_BLOCKS' });
    expect(dispatch).toHaveBeenNthCalledWith(2, { type: 'SET_SESSION', session: null });
    expect(dispatch).toHaveBeenNthCalledWith(3, {
      type: 'UPDATE_USAGE',
      usage: {
        promptTokens: 0,
        completionTokens: 0,
        totalCost: 0,
        model: '',
        contextUsagePercent: 0,
      },
    });
    expect(result).toBe('Session reset.');
  });

  it('filters handler parses category, status, and search arguments', async () => {
    const dispatch = vi.fn<(action: BlockAction) => void>();
    const registryWithContext = new CommandRegistry({
      client: { request: vi.fn() },
      dispatch,
      getState: () => createState(),
      shutdown: vi.fn(),
    });

    const result = await registryWithContext.find('filters')?.handler('category=tool,llm status=error search="disk full"');

    expect(dispatch).toHaveBeenCalledWith({
      type: 'SET_EVENT_FILTERS',
      filters: {
        categories: ['tool', 'llm'],
        statuses: ['error'],
        search: 'disk full',
      },
    });
    expect(result).toBe('Event filters updated.');
  });

  it('permissions handler only shows pending permission requests', async () => {
    const registryWithContext = new CommandRegistry({
      client: { request: vi.fn() },
      dispatch: vi.fn(),
      getState: () => createState({
        permissions: [
          { id: 'p1', tool: 'shell', arguments: { command: 'pwd' }, riskLevel: 'low', status: 'pending' },
          { id: 'p2', tool: 'file_write', arguments: { path: '/tmp/x' }, riskLevel: 'high', status: 'approved' },
        ],
      }),
      shutdown: vi.fn(),
    });

    const result = await registryWithContext.find('permissions')?.handler('');

    expect(result).toContain('[pending] shell');
    expect(result).not.toContain('file_write');
  });
});
