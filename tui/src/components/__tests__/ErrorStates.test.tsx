import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { ErrorStates, ErrorInfo } from '../ErrorStates.js';
import { renderApp } from '../../test-utils.js';

describe('ErrorStates', () => {
  it('renders rate limit error with countdown', async () => {
    const error: ErrorInfo = {
      type: 'rate_limit',
      message: 'Too many requests',
      data: { retryAfter: 1 }
    };
    const onRetry = vi.fn();

    const { lastFrame } = renderApp(<ErrorStates error={error} onRetry={onRetry} />);

    expect(lastFrame()).toContain('Rate limited');
    expect(lastFrame()).toContain('Retrying in 1s');

    await new Promise((resolve) => setTimeout(resolve, 1500));

    expect(onRetry).toHaveBeenCalled();
  });

  it('renders context full error with usage bar', () => {
    const error: ErrorInfo = {
      type: 'context_full',
      message: 'Context full',
      data: { usage: { prompt: 90, completion: 5, max: 100 } }
    };

    const { lastFrame } = renderApp(<ErrorStates error={error} />);
    expect(lastFrame()).toContain('Context 95% full');
    expect(lastFrame()).toContain('/compact');
    expect(lastFrame()).toContain('95 / 100 tokens');
  });

  it('renders auth error with redacted key', () => {
    const error: ErrorInfo = {
      type: 'auth_error',
      message: 'Invalid key',
      data: { provider: 'OpenAI' }
    };

    const { lastFrame } = renderApp(<ErrorStates error={error} />);
    expect(lastFrame()).toContain('Auth Error: OpenAI');
    expect(lastFrame()).toContain('Key is hidden');
    expect(lastFrame()).not.toContain('sk-');
  });

  it('renders network error with retry instruction', () => {
    const error: ErrorInfo = {
      type: 'network_error',
      message: 'Connection failed',
      data: { lastConnected: '10:00 AM' }
    };
    const onRetry = vi.fn();

    const { lastFrame } = renderApp(<ErrorStates error={error} onRetry={onRetry} />);
    expect(lastFrame()).toContain('Network Error');
    expect(lastFrame()).toContain('Last connected: 10:00 AM');
    expect(lastFrame()).toContain('Press R to Retry');
  });

  it('renders backend crash with restart info', () => {
    const error: ErrorInfo = {
      type: 'backend_crash',
      message: 'Process died',
      data: { exitCode: 137, restarts: 0 }
    };
    const onRestart = vi.fn();

    const { lastFrame } = renderApp(<ErrorStates error={error} onRestart={onRestart} />);
    expect(lastFrame()).toContain('Backend Crashed (Code: 137)');
    expect(lastFrame()).toContain('Auto-restarting (1/3)');
  });

  it('renders backend crash max restarts exceeded', () => {
    const error: ErrorInfo = {
      type: 'backend_crash',
      message: 'Process died',
      data: { exitCode: 1, restarts: 3 }
    };

    const { lastFrame } = renderApp(<ErrorStates error={error} />);
    expect(lastFrame()).toContain('Max restarts exceeded');
    expect(lastFrame()).toContain('sage-agent.log');
  });

  it('renders tool error with hidden stack trace initially', () => {
    const error: ErrorInfo = {
      type: 'tool_error',
      message: 'Failed to read file',
      data: { toolName: 'file_read', stack: 'Error: oops at line 1' }
    };

    const { lastFrame } = renderApp(<ErrorStates error={error} />);
    expect(lastFrame()).toContain('Tool Execution Error: file_read');
    expect(lastFrame()).toContain('Failed to read file');
    expect(lastFrame()).toContain('Stack trace (Press S to toggle)');
    expect(lastFrame()).not.toContain('Error: oops at line 1');
  });

  it('renders token exhaustion error', () => {
    const error: ErrorInfo = {
      type: 'token_exhaustion',
      message: 'No tokens left'
    };

    const { lastFrame } = renderApp(<ErrorStates error={error} />);
    expect(lastFrame()).toContain('Token Limit Exhausted');
    expect(lastFrame()).toContain('Switch to a cheaper model');
  });

  it('renders unknown error', () => {
    const error: ErrorInfo = {
      type: 'unknown',
      message: 'Something weird happened'
    };

    const { lastFrame } = renderApp(<ErrorStates error={error} />);
    expect(lastFrame()).toContain('Error: Something weird happened');
    expect(lastFrame()).toContain('/reset');
  });

  it('RetryCountdown renders progress bar', () => {
    const onComplete = vi.fn();
    const { lastFrame } = renderApp(<React.Fragment><ErrorStates error={{ type: 'rate_limit', message: 'x', data: { retryAfter: 10 } }} onRetry={onComplete} /></React.Fragment>);
    expect(lastFrame()).toContain('Retrying in 10s');
    expect(lastFrame()).toContain('░');
  });
});
